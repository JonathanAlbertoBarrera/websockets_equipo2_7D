from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional
import base64
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Crypto
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from base64 import b64encode, b64decode


# --- Modelos ---
class LoginRequest(BaseModel):
    password: str

class Message(BaseModel):
    id: str
    content: str
    timestamp: str
    user_id: str
    user_ip: Optional[str] = None
    user_port: Optional[int] = None

# --- Firma digital colaborativa ---
class FileUploadRequest(BaseModel):
    filename: str
    file_type: str
    allowed_signers: List[str]  # ['user123', 'admin456'] o ['all'] o ['admins']
    require_all_signers: bool = True

class FileSignatureStatus(BaseModel):
    file_id: str
    original_uploader: str
    allowed_signers: List[str]
    completed_signers: List[str]
    pending_signers: List[str]
    status: str  # 'pending', 'partially_signed', 'fully_signed'

class SignatureAction(BaseModel):
    file_id: str
    signer_id: str
    timestamp: datetime
    signature_data: str  # Firma criptográfica


# --- Estructuras en memoria ---
file_permissions: Dict[str, dict] = {}  # {file_id: {allowed_signers: [...]}}
file_signature_status: Dict[str, FileSignatureStatus] = {}
file_signature_history: Dict[str, List[SignatureAction]] = {}

# --- Notificaciones WebSocket de firmas ---
import asyncio
async def notify_signers_invitation(file_id: str, filename: str, invited_by: str, allowed_signers: list):
    """
    Notifica a los firmantes seleccionados que tienen un documento pendiente de firma.
    """
    payload = {
        "type": "signature_invitation",
        "file_id": file_id,
        "filename": filename,
        "invited_by": invited_by,
        "allowed_signers": allowed_signers
    }
    # Notificar solo a los usuarios conectados y autorizados
    for user_id in allowed_signers:
        ws = chat_manager.connections.get(user_id) or chat_manager.admin_connections.get(user_id)
        if ws:
            try:
                await ws.send_text(json.dumps(payload))
            except Exception as e:
                debug_log(f"Error notificando invitación de firma a {user_id}: {e}")

async def notify_signature_performed(file_id: str, signed_by: str, remaining_signers: list):
    """
    Notifica a todos los firmantes y al subidor sobre una nueva firma realizada.
    """
    status = file_signature_status[file_id]
    filename = file_permissions[file_id]["filename"]
    original_uploader = file_permissions[file_id]["original_uploader"]
    payload = {
        "type": "signature_performed",
        "file_id": file_id,
        "filename": filename,
        "signed_by": signed_by,
        "remaining_signers": remaining_signers,
        "status": status.status
    }
    # Notificar a todos los firmantes y al uploader
    notified = set()
    for user_id in status.allowed_signers + [original_uploader]:
        if user_id in notified:
            continue
        ws = chat_manager.connections.get(user_id) or chat_manager.admin_connections.get(user_id)
        if ws:
            try:
                await ws.send_text(json.dumps(payload))
                notified.add(user_id)
            except Exception as e:
                debug_log(f"Error notificando firma a {user_id}: {e}")

import shutil
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO

# --- Funciones de Firma Real ---
def add_signature_page_to_pdf(input_path: str, output_path: str, signatures: List[SignatureAction], file_id: str):
    """
    Agrega una página final al PDF con todas las firmas digitales.
    """
    try:
        # Leer PDF original
        reader = PdfReader(input_path)
        writer = PdfWriter()
        
        # Copiar todas las páginas originales
        for page in reader.pages:
            writer.add_page(page)
        
        # Crear página de firmas con ReportLab
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        width, height = letter
        
        # Título
        can.setFont("Helvetica-Bold", 16)
        can.drawString(50, height - 50, "PÁGINA DE FIRMAS DIGITALES")
        can.setFont("Helvetica", 10)
        can.drawString(50, height - 70, f"ID del Documento: {file_id}")
        
        # Línea separadora
        can.line(50, height - 80, width - 50, height - 80)
        
        # Listar todas las firmas
        y_position = height - 110
        can.setFont("Helvetica-Bold", 12)
        can.drawString(50, y_position, "Firmantes:")
        y_position -= 25
        
        can.setFont("Helvetica", 10)
        for idx, sig in enumerate(signatures, 1):
            if y_position < 100:  # Si no hay espacio, crear nueva página
                can.showPage()
                y_position = height - 50
            
            can.setFont("Helvetica-Bold", 11)
            can.drawString(50, y_position, f"{idx}. {sig.signer_id}")
            y_position -= 18
            
            can.setFont("Helvetica", 9)
            can.drawString(70, y_position, f"Fecha: {sig.timestamp.strftime('%d/%m/%Y %H:%M:%S')}")
            y_position -= 15
            can.drawString(70, y_position, f"Firma Digital: {sig.signature_data[:60]}...")
            y_position -= 25
        
        # Footer
        can.setFont("Helvetica-Oblique", 8)
        can.drawString(50, 30, f"Documento firmado digitalmente - Total de firmas: {len(signatures)}")
        can.drawString(50, 20, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        
        can.save()
        packet.seek(0)
        
        # Agregar página de firmas al PDF
        signature_page = PdfReader(packet)
        writer.add_page(signature_page.pages[0])
        
        # Guardar PDF con firmas
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        return True
    except Exception as e:
        debug_log(f"Error agregando página de firmas al PDF: {e}")
        return False

def add_signatures_to_txt(input_path: str, output_path: str, signatures: List[SignatureAction], file_id: str):
    """
    Agrega un bloque de firmas al final del archivo TXT.
    """
    try:
        # Leer contenido original
        with open(input_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # Crear bloque de firmas
        signature_block = "\n\n" + "="*80 + "\n"
        signature_block += "FIRMAS DIGITALES\n"
        signature_block += "="*80 + "\n"
        signature_block += f"ID del Documento: {file_id}\n\n"
        
        for idx, sig in enumerate(signatures, 1):
            signature_block += f"{idx}. Firmante: {sig.signer_id}\n"
            signature_block += f"   Fecha: {sig.timestamp.strftime('%d/%m/%Y %H:%M:%S')}\n"
            signature_block += f"   Firma Digital: {sig.signature_data}\n\n"
        
        signature_block += "="*80 + "\n"
        signature_block += f"Total de firmas: {len(signatures)}\n"
        signature_block += f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        
        # Guardar archivo con firmas
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(original_content + signature_block)
        
        return True
    except Exception as e:
        debug_log(f"Error agregando firmas al TXT: {e}")
        return False
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO

# Configuración desde variables de entorno
def get_required_env(key: str):
    """Obtiene una variable de entorno requerida. Falla si no existe."""
    value = os.getenv(key)
    
    if value is None:
        raise ValueError(
            f"ERROR: Variable de entorno '{key}' no configurada.\n"
            f"   Por favor, configura el archivo .env con todas las variables requeridas.\n"
            f"   Consulta .env.example para ver el formato correcto."
        )
    
    return value

# Cargar variables de entorno requeridas
ENVIRONMENT = get_required_env("ENVIRONMENT")
ADMIN_PASSWORD = get_required_env("ADMIN_PASSWORD")
SECRET_KEY = get_required_env("SECRET_KEY")
RSA_KEY_SIZE = int(get_required_env("RSA_KEY_SIZE"))
ALLOWED_ORIGINS = get_required_env("ALLOWED_ORIGINS").split(",")

# SSL/TLS Configuration
USE_SSL = os.getenv("USE_SSL", "false").lower() == "true"
SSL_CERT_FILE = os.getenv("SSL_CERT_FILE", "ssl_cert.pem")
SSL_KEY_FILE = os.getenv("SSL_KEY_FILE", "ssl_cert.key")

# Función para logs condicionales
def debug_log(*args, **kwargs):
    """Imprime logs solo en modo development"""
    if ENVIRONMENT == "development":
        print(*args, **kwargs)

debug_log(f" Configuración cargada correctamente")
debug_log(f" Entorno: {ENVIRONMENT}")
debug_log(f" RSA Key Size: {RSA_KEY_SIZE}")
debug_log(f" CORS Origins permitidos: {ALLOWED_ORIGINS}")
debug_log(f" SSL/TLS: {'Habilitado' if USE_SSL else 'Deshabilitado'}")
if USE_SSL:
    debug_log(f" Certificado: {SSL_CERT_FILE}")
    debug_log(f" Clave privada: {SSL_KEY_FILE}")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ChatManager con RSA ---
class ChatManager:
    def __init__(self):
        # Generar claves RSA al crear la instancia del servidor usando el tamaño configurado
        self.server_private_key = rsa.generate_private_key(
            public_exponent=65537, 
            key_size=RSA_KEY_SIZE
        )
        self.server_public_key = self.server_private_key.public_key()

        self.connections: Dict[str, WebSocket] = {}
        self.admin_connections: Dict[str, WebSocket] = {}
        self.messages: List[Message] = []
        # user_info guarda ip, port, is_admin, connected_at, y opcionalmente 'public_key' (PEM)
        self.user_info: Dict[str, dict] = {}

    # --- Utilidades RSA ---
    def get_public_key_pem(self) -> str:
        return self.server_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

    def decrypt_with_private_key(self, encrypted_base64: str) -> str:
        """Descifra texto cifrado (base64) con la clave privada del servidor."""
        ciphertext = base64.b64decode(encrypted_base64)
        plaintext = self.server_private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return plaintext.decode()

    def encrypt_with_public_key_pem(self, public_pem: str, plaintext: str) -> str:
        """Cifra plaintext con la clave pública en PEM, devuelve base64."""
        public_key = load_pem_public_key(public_pem.encode())
        ciphertext = public_key.encrypt(
            plaintext.encode(),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return base64.b64encode(ciphertext).decode()

    def register_client_public_key(self, user_id: str, public_pem: str):
        """Almacena la clave pública PEM del cliente en user_info."""
        if user_id in self.user_info:
            self.user_info[user_id]["public_key"] = public_pem
        else:
            self.user_info[user_id] = {
                "ip": "unknown",
                "port": 0,
                "is_admin": False,
                "connected_at": datetime.now().isoformat(),
                "public_key": public_pem
            }

    # --- Conexiones / mensajería ---
    async def connect(self, websocket: WebSocket, user_id: str, is_admin: bool = False):
        try:
            # Limpiar conexión anterior si existe
            if is_admin:
                if user_id in self.admin_connections:
                    await self.disconnect(user_id)
            else:
                if user_id in self.connections:
                    await self.disconnect(user_id)

            # Aceptar nueva conexión
            await websocket.accept()
            
            # Mostrar claves para debug
            debug_log("Clave pública del servidor (PEM):")
            debug_log(self.get_public_key_pem())

            # info cliente
            client_host = websocket.client.host if websocket.client else "unknown"
            client_port = websocket.client.port if websocket.client else 0
            
            # Registrar nueva conexión
            if is_admin:
                self.admin_connections[user_id] = websocket
            else:
                self.connections[user_id] = websocket
            
            self.user_info[user_id] = {
                "ip": client_host,
                "port": client_port,
                "is_admin": is_admin,
                "connected_at": datetime.now().isoformat()
            }
            
            debug_log(f"Usuario {'admin' if is_admin else 'regular'} conectado: {user_id} desde {client_host}:{client_port}")
            
            try:
                # Enviar historial de mensajes al usuario que se conecta
                for message in self.messages[-50:]:
                    await self.send_message_to_user(websocket, message, is_admin)
            except Exception as e:
                debug_log(f"Error enviando historial a {user_id}: {e}")
                
            return True
        except Exception as e:
            debug_log(f"Error en conexión de {user_id}: {e}")
            try:
                await websocket.close(code=1011)  # 1011 = Internal Error
            except:
                pass
            return False

    async def disconnect(self, user_id: str):
        """Desconecta un usuario y limpia todas sus referencias"""
        # Si el usuario ya no existe en ninguna colección, no hacer nada
        if (user_id not in self.connections and 
            user_id not in self.admin_connections and 
            user_id not in self.user_info):
            return

        ws_to_close = None
        
        # Obtener el websocket antes de eliminar las referencias
        if user_id in self.connections:
            ws_to_close = self.connections[user_id]
            del self.connections[user_id]
            
        admin_id = f"admin_{user_id}" if not user_id.startswith("admin_") else user_id
        if admin_id in self.admin_connections:
            ws_to_close = self.admin_connections[admin_id]
            del self.admin_connections[admin_id]
            
        # Limpiar info de usuario
        if user_id in self.user_info:
            del self.user_info[user_id]
        if admin_id in self.user_info:
            del self.user_info[admin_id]
            
        # Cerrar el websocket al final, después de limpiar las referencias
        if ws_to_close:
            try:
                await ws_to_close.close(code=1000)
            except Exception as e:
                debug_log(f"Error al cerrar websocket de {user_id}: {e}")
                
        debug_log(f"Usuario desconectado: {user_id}")
    
    async def send_message_to_user(self, websocket: WebSocket, message: Message, is_admin: bool):
        """Envía message (obj Message) ya preparado. Aquí se asume content en texto claro."""
        message_data = {
            "id": message.id,
            "content": message.content,
            "timestamp": message.timestamp,
            "user_id": message.user_id
        }
        if is_admin:
            message_data.update({
                "user_ip": message.user_ip,
                "user_port": message.user_port
            })
        await websocket.send_text(json.dumps(message_data))

    async def broadcast_message(self, plaintext: str, original_hash: str, origin_user_id: str):
        """Broadcast message using asymmetric encryption with SHA-256 verification.
        
        Args:
            plaintext: The decrypted message content
            original_hash: The decrypted SHA-256 hash to verify message integrity
            origin_user_id: The ID of the user who sent the message
        """
        message_obj = Message(
            id=str(uuid.uuid4()),
            content=plaintext,
            timestamp=datetime.now().isoformat(),
            user_id=origin_user_id,
            user_ip=self.user_info.get(origin_user_id, {}).get("ip"),
            user_port=self.user_info.get(origin_user_id, {}).get("port")
        )
        self.messages.append(message_obj)

        # Lista para mantener las conexiones a desconectar
        to_disconnect = set()

        # Preparar mensajes para usuarios regulares
        regular_messages = []
        for uid, ws in list(self.connections.items()):
            if uid == origin_user_id:  # Skip sender
                continue
                
            try:
                recipient_info = self.user_info.get(uid, {})
                if not recipient_info:
                    continue

                recipient_pub = recipient_info.get("public_key")
                if recipient_pub:
                    encrypted_content = self.encrypt_with_public_key_pem(recipient_pub, plaintext)
                    encrypted_hash = self.encrypt_with_public_key_pem(recipient_pub, original_hash)
                    payload = {
                        "id": message_obj.id,
                        "content": encrypted_content,
                        "hash": encrypted_hash,
                        "encrypted": True,
                        "timestamp": message_obj.timestamp,
                        "user_id": origin_user_id
                    }
                else:
                    payload = {
                        "id": message_obj.id,
                        "content": plaintext,
                        "encrypted": False,
                        "timestamp": message_obj.timestamp,
                        "user_id": origin_user_id
                    }
                regular_messages.append((uid, ws, json.dumps(payload)))
            except Exception as e:
                debug_log(f"Error preparando mensaje para {uid}: {e}")
                to_disconnect.add(uid)

        # Preparar mensajes para admins
        admin_messages = []
        for uid, ws in list(self.admin_connections.items()):
            if uid == origin_user_id:  # Skip sender
                continue
                
            try:
                recipient_info = self.user_info.get(uid, {})
                if not recipient_info:
                    continue

                recipient_pub = recipient_info.get("public_key")
                if recipient_pub:
                    encrypted_content = self.encrypt_with_public_key_pem(recipient_pub, plaintext)
                    encrypted_hash = self.encrypt_with_public_key_pem(recipient_pub, original_hash)
                    payload = {
                        "id": message_obj.id, 
                        "content": encrypted_content,
                        "hash": encrypted_hash,
                        "encrypted": True, 
                        "timestamp": message_obj.timestamp, 
                        "user_id": origin_user_id,
                        "user_ip": message_obj.user_ip,
                        "user_port": message_obj.user_port
                    }
                else:
                    payload = {
                        "id": message_obj.id, 
                        "content": plaintext, 
                        "encrypted": False, 
                        "timestamp": message_obj.timestamp, 
                        "user_id": origin_user_id,
                        "user_ip": message_obj.user_ip,
                        "user_port": message_obj.user_port
                    }
                admin_messages.append((uid, ws, json.dumps(payload)))
            except Exception as e:
                debug_log(f"Error preparando mensaje para admin {uid}: {e}")
                to_disconnect.add(uid)

        # Enviar mensajes
        for uid, ws, msg in regular_messages:
            try:
                await ws.send_text(msg)
            except Exception as e:
                debug_log(f"Error enviando a {uid}: {e}")
                to_disconnect.add(uid)

        for uid, ws, msg in admin_messages:
            try:
                await ws.send_text(msg)
            except Exception as e:
                debug_log(f"Error enviando a admin {uid}: {e}")
                to_disconnect.add(uid)

        # Desconectar usuarios con error al final
        for uid in to_disconnect:
            try:
                await self.disconnect(uid)
            except Exception as e:
                debug_log(f"Error al desconectar {uid}: {e}")# --- Instancia global ---
chat_manager = ChatManager()

# --- Endpoints HTTP ---

# --- Endpoints de Firma Digital ---
@app.post("/api/upload-file")
async def upload_file(
    file: UploadFile = File(...),
    allowed_signers: str = Form(...),  # JSON stringified list
    require_all_signers: bool = Form(True),
    user_id: str = Form(...)
):
    """
    Sube un archivo y define los firmantes permitidos.
    allowed_signers: JSON string (['user1', 'user2'] o ['all'] o ['admins'])
    """
    import json as _json
    allowed_signers_list = _json.loads(allowed_signers)
    file_id = str(uuid.uuid4())
    filename = file.filename
    file_type = filename.split('.')[-1].lower()
    save_path = f"uploaded_files/{file_id}_{filename}"
    os.makedirs("uploaded_files", exist_ok=True)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Permisos y estado inicial
    file_permissions[file_id] = {
        "allowed_signers": allowed_signers_list,
        "require_all_signers": require_all_signers,
        "filename": filename,
        "file_type": file_type,
        "original_uploader": user_id
    }
    file_signature_status[file_id] = FileSignatureStatus(
        file_id=file_id,
        original_uploader=user_id,
        allowed_signers=allowed_signers_list,
        completed_signers=[],
        pending_signers=allowed_signers_list.copy(),
        status="pending"
    )
    file_signature_history[file_id] = []

    # Notificar a firmantes (WebSocket)
    asyncio.create_task(notify_signers_invitation(file_id, filename, user_id, allowed_signers_list))

    return {"file_id": file_id, "filename": filename, "allowed_signers": allowed_signers_list}


@app.post("/api/sign-file/{file_id}")
async def sign_file(file_id: str, signer_id: str = Form(...)):
    """
    Permite a un usuario autorizado firmar un archivo.
    """
    # Validar permisos
    perms = file_permissions.get(file_id)
    if not perms:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    allowed = perms["allowed_signers"]
    if signer_id not in allowed and "all" not in allowed and not ("admins" in allowed and chat_manager.user_info.get(signer_id, {}).get("is_admin")):
        raise HTTPException(status_code=403, detail="No autorizado para firmar este archivo")

    # Generar firma digital real
    timestamp = datetime.now()
    # Crear hash de la firma (SHA-256 del signer_id + timestamp + file_id)
    signature_hash = hashes.Hash(hashes.SHA256())
    signature_hash.update(f"{signer_id}{timestamp.isoformat()}{file_id}".encode())
    signature_data = signature_hash.finalize().hex()
    
    action = SignatureAction(
        file_id=file_id,
        signer_id=signer_id,
        timestamp=timestamp,
        signature_data=signature_data
    )
    file_signature_history[file_id].append(action)

    # Actualizar estado
    status = file_signature_status[file_id]
    if signer_id not in status.completed_signers:
        status.completed_signers.append(signer_id)
    if signer_id in status.pending_signers:
        status.pending_signers.remove(signer_id)
    if not status.pending_signers:
        status.status = "fully_signed"
    elif status.completed_signers:
        status.status = "partially_signed"
    else:
        status.status = "pending"

    # Agregar firma al archivo físico
    filename = perms["filename"]
    file_type = perms["file_type"]
    original_path = f"uploaded_files/{file_id}_{filename}"
    signed_path = f"uploaded_files/{file_id}_signed_{filename}"
    
    if file_type == "pdf":
        # Agregar página de firmas al PDF
        success = add_signature_page_to_pdf(
            original_path,
            signed_path,
            file_signature_history[file_id],
            file_id
        )
        if success:
            # Reemplazar original con versión firmada
            os.replace(signed_path, original_path)
    elif file_type == "txt":
        # Agregar bloque de firmas al TXT
        success = add_signatures_to_txt(
            original_path,
            signed_path,
            file_signature_history[file_id],
            file_id
        )
        if success:
            os.replace(signed_path, original_path)

    # Notificar a participantes (WebSocket)
    asyncio.create_task(notify_signature_performed(file_id, signer_id, status.pending_signers))

    return {"file_id": file_id, "signed_by": signer_id, "status": status.status, "remaining_signers": status.pending_signers}

@app.get("/api/file-signature-status/{file_id}")
async def get_file_signature_status(file_id: str):
    status = file_signature_status.get(file_id)
    if not status:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return status

@app.get("/api/list-files")
async def list_files(user_id: str = None):
    """
    Lista todos los archivos o filtra por usuario.
    """
    all_files = []
    for file_id, perms in file_permissions.items():
        status = file_signature_status.get(file_id)
        file_info = {
            "file_id": file_id,
            "filename": perms["filename"],
            "file_type": perms["file_type"],
            "original_uploader": perms["original_uploader"],
            "allowed_signers": perms["allowed_signers"],
            "status": status.status if status else "unknown",
            "completed_signers": status.completed_signers if status else [],
            "pending_signers": status.pending_signers if status else []
        }
        
        if user_id:
            # Filtrar: mostrar si el usuario es uploader o firmante
            if perms["original_uploader"] == user_id or user_id in perms["allowed_signers"]:
                all_files.append(file_info)
        else:
            all_files.append(file_info)
    
    return {"files": all_files}

@app.get("/api/download-file/{file_id}")
async def download_file(file_id: str):
    """
    Descarga o visualiza un archivo.
    """
    perms = file_permissions.get(file_id)
    if not perms:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    filename = perms["filename"]
    file_path = f"uploaded_files/{file_id}_{filename}"
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Archivo físico no encontrado")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )

@app.get("/api/preview-file/{file_id}")
async def preview_file(file_id: str):
    """
    Vista previa de archivo (PDF o TXT) para mostrar en navegador.
    """
    perms = file_permissions.get(file_id)
    if not perms:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    filename = perms["filename"]
    file_type = perms["file_type"]
    file_path = f"uploaded_files/{file_id}_{filename}"
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Archivo físico no encontrado")
    
    # Determinar media type
    media_type = "application/octet-stream"
    if file_type == "pdf":
        media_type = "application/pdf"
    elif file_type == "txt":
        media_type = "text/plain; charset=utf-8"
    
    return FileResponse(
        path=file_path,
        media_type=media_type,
        headers={
            "Content-Disposition": f"inline; filename={filename}",
            "X-Frame-Options": "SAMEORIGIN",
            "Content-Security-Policy": "frame-ancestors 'self'"
        }
    )

# --- Endpoints de Admin y Auth ---
@app.post("/admin/login")
async def admin_login(request: LoginRequest):
    if request.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    admin_token = str(uuid.uuid4())
    return {"token": admin_token, "message": "Login exitoso"}

@app.get("/admin/users")
async def get_connected_users():
    return {
        "users": [
            {
                "user_id": user_id,
                "ip": info.get("ip"),
                "port": info.get("port"),
                "is_admin": info.get("is_admin"),
                "connected_at": info.get("connected_at"),
                "has_public_key": ("public_key" in info)
            }
            for user_id, info in chat_manager.user_info.items()
        ]
    }

@app.get("/public-key")
async def get_server_public_key():
    return {"public_key": chat_manager.get_public_key_pem()}



# --- WebSocket endpoints ---
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    if not await chat_manager.connect(websocket, user_id, is_admin=False):
        return

    try:
        while True:
            try:
                raw = await websocket.receive_text()
                data = json.loads(raw)

                if data.get("type") == "message" and "content" in data and "hash" in data:
                    debug_log(f"\n=== MENSAJE RECIBIDO de {user_id} ===")
                    debug_log(f"Contenido cifrado: {data['content'][:100]}...")
                    debug_log(f"Hash cifrado: {data['hash'][:100]}...")

                    try:
                        # Descifrar mensaje y hash
                        decrypted_content = chat_manager.decrypt_with_private_key(data["content"])
                        decrypted_hash = chat_manager.decrypt_with_private_key(data["hash"])
                        debug_log(f" Mensaje descifrado (RSA): {decrypted_content}")
                        debug_log(f" Hash descifrado (SHA-256): {decrypted_hash}")
                        
                        await chat_manager.broadcast_message(decrypted_content, decrypted_hash, origin_user_id=user_id)
                    except Exception as e:
                        debug_log(f" Error al descifrar mensaje/hash de {user_id}: {e}")
            except WebSocketDisconnect:
                debug_log(f"WebSocket desconectado: {user_id}")
                await chat_manager.disconnect(user_id)
                break
            except json.JSONDecodeError:
                debug_log(f"Error: Mensaje mal formado de {user_id}")
                continue
            except Exception as e:
                debug_log(f"Error procesando mensaje de {user_id}: {e}")
                await chat_manager.disconnect(user_id)
                break
    except Exception as e:
        debug_log(f"Error en el websocket de {user_id}: {e}")
        await chat_manager.disconnect(user_id)

    except WebSocketDisconnect:
        chat_manager.disconnect(user_id)

@app.websocket("/ws/admin/{user_id}")
async def admin_websocket_endpoint(websocket: WebSocket, user_id: str):
    admin_id = f"admin_{user_id}"
    await chat_manager.connect(websocket, admin_id, is_admin=True)
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)

            # Registro clave pública admin
            if data.get("type") == "register" and "public_key" in data:
                chat_manager.register_client_public_key(admin_id, data["public_key"])
                await websocket.send_text(json.dumps({
                    "status": "ok",
                    "message": "public_key_registered",
                    "tipo_comunicacion": chat_manager.get_tipo_comunicacion()
                }))
                continue

            # Mensaje admin: se espera cifrado con la clave pública del servidor
            if data.get("type") == "message" and "content" in data and "hash" in data:
                try:
                    decrypted_content = chat_manager.decrypt_with_private_key(data["content"])
                    decrypted_hash = chat_manager.decrypt_with_private_key(data["hash"])
                    debug_log(f" Mensaje admin descifrado (RSA): {decrypted_content}")
                    debug_log(f" Hash admin descifrado (SHA-256): {decrypted_hash}")
                except Exception as e:
                    debug_log(f" Error al descifrar mensaje/hash de admin: {e}")
                    return

                await chat_manager.broadcast_message(decrypted_content, decrypted_hash, origin_user_id=admin_id)

    except WebSocketDisconnect:
        chat_manager.disconnect(admin_id)

@app.get("/")
async def root():
    protocol = "HTTPS" if USE_SSL else "HTTP"
    ws_protocol = "WSS" if USE_SSL else "WS"
    return {
        "message": f"Chat WebSocket Server está funcionando con cifrado RSA",
        "protocol": protocol,
        "websocket_protocol": ws_protocol,
        "ssl_enabled": USE_SSL
    }

# --- Ejecutar servidor con o sin SSL ---
if __name__ == "__main__":
    import uvicorn
    
    if USE_SSL:
        # Verificar que existan los archivos de certificado
        if not os.path.exists(SSL_CERT_FILE):
            print(f" ERROR: No se encontró el archivo de certificado: {SSL_CERT_FILE}")
            print("   Ejecuta: python generate_certs.py")
            exit(1)
        if not os.path.exists(SSL_KEY_FILE):
            print(f" ERROR: No se encontró el archivo de clave privada: {SSL_KEY_FILE}")
            print("   Ejecuta: python generate_certs.py")
            exit(1)
        
        debug_log(f"\n Iniciando servidor con SSL/TLS...")
        debug_log(f" URL: https://localhost:8000")
        debug_log(f" WebSocket: wss://localhost:8000")
        
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            ssl_keyfile=SSL_KEY_FILE,
            ssl_certfile=SSL_CERT_FILE,
            reload=True
        )
    else:
        debug_log(f"\n  Iniciando servidor SIN SSL (desarrollo)")
        debug_log(f" URL: http://localhost:8000")
        debug_log(f" WebSocket: ws://localhost:8000")
        
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True
        )