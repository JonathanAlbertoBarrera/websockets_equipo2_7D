from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional
import base64

# Crypto
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.fernet import Fernet
from base64 import b64encode, b64decode

# --- Modelos ---
class LoginRequest(BaseModel):
    password: str

class TipoComunicacionRequest(BaseModel):
    tipo: str  # "Asimetrico" o "Simetrico"

class Message(BaseModel):
    id: str
    content: str
    timestamp: str
    user_id: str
    user_ip: Optional[str] = None
    user_port: Optional[int] = None

# --- Configuración ---
ADMIN_PASSWORD = "admin123"  # Cambiar en producción

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en prod, restringir dominios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Clases de cifrado ---
class SymmetricEncryption:
    def __init__(self):
        self.key = Fernet.generate_key()
        self.cipher_suite = Fernet(self.key)

    def encrypt(self, message: str) -> str:
        """Cifra un mensaje usando Fernet (cifrado simétrico)"""
        encrypted_message = self.cipher_suite.encrypt(message.encode())
        return b64encode(encrypted_message).decode()

    def decrypt(self, encrypted_message: str) -> str:
        """Descifra un mensaje usando Fernet"""
        try:
            decoded = b64decode(encrypted_message.encode())
            decrypted_message = self.cipher_suite.decrypt(decoded)
            return decrypted_message.decode()
        except Exception as e:
            print(f"Error al descifrar: {e}")
            return encrypted_message

# --- ChatManager con RSA y cifrado simétrico ---
class ChatManager:
    def __init__(self):
        # Generar claves RSA al crear la instancia del servidor
        self.server_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.server_public_key = self.server_private_key.public_key()

        self.connections: Dict[str, WebSocket] = {}
        self.admin_connections: Dict[str, WebSocket] = {}
        self.messages: List[Message] = []
        # user_info guarda ip, port, is_admin, connected_at, y opcionalmente 'public_key' (PEM)
        self.user_info: Dict[str, dict] = {}
        self.tipo_comunicacion: str = "Asimetrico"  # Valor por defecto
        self.symmetric_encryption = SymmetricEncryption()

    # --- Métodos para gestionar el tipo de comunicación ---
    def set_tipo_comunicacion(self, tipo: str):
        """Establece el tipo de comunicación: 'Asimetrico' o 'Simetrico'"""
        tipos_validos = ["Asimetrico", "Simetrico"]
        if tipo in tipos_validos:
            self.tipo_comunicacion = tipo
            print(f"Tipo de comunicación cambiado a: {tipo}")
            return True
        else:
            print(f"Tipo de comunicación no válido: {tipo}. Usando: {self.tipo_comunicacion}")
            return False

    def get_tipo_comunicacion(self) -> str:
        """Retorna el tipo de comunicación actual"""
        return self.tipo_comunicacion

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
        await websocket.accept()
        # Mostrar claves para debug (no lo hagas en producción)
        print("Clave pública del servidor (PEM):")
        print(self.get_public_key_pem())
        print(f"Tipo de comunicación actual: {self.tipo_comunicacion}")

        # info cliente
        client_host = websocket.client.host if websocket.client else "unknown"
        client_port = websocket.client.port if websocket.client else 0
        
        if is_admin:
            self.admin_connections[user_id] = websocket
        else:
            self.connections[user_id] = websocket
        
        self.user_info[user_id] = {
            "ip": client_host,
            "port": client_port,
            "is_admin": is_admin,
            "connected_at": datetime.now().isoformat()
            # 'public_key' puede agregarse luego con mensaje de registro
        }
        
        print(f"Usuario {'admin' if is_admin else 'regular'} conectado: {user_id} desde {client_host}:{client_port}")
        
        # Enviar historial de mensajes al usuario que se conecta (en texto claro)
        for message in self.messages[-50:]:
            await self.send_message_to_user(websocket, message, is_admin)

    def disconnect(self, user_id: str):
        if user_id in self.connections:
            del self.connections[user_id]
        if user_id in self.admin_connections:
            del self.admin_connections[user_id]
        if user_id in self.user_info:
            del self.user_info[user_id]
        print(f"Usuario desconectado: {user_id}")
    
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

    def get_symmetric_key(self) -> str:
        """Retorna la clave simétrica en formato base64"""
        return b64encode(self.symmetric_encryption.key).decode()

    async def broadcast_message(self, plaintext: str, origin_user_id: str):
        """Modificar el método broadcast_message para manejar cifrado simétrico"""
        message_obj = Message(
            id=str(uuid.uuid4()),
            content=plaintext,
            timestamp=datetime.now().isoformat(),
            user_id=origin_user_id,
            user_ip=self.user_info.get(origin_user_id, {}).get("ip"),
            user_port=self.user_info.get(origin_user_id, {}).get("port")
        )
        self.messages.append(message_obj)

        # Preparar el mensaje según el tipo de comunicación
        for uid, ws in list(self.connections.items()):
            try:
                if self.tipo_comunicacion == "Simetrico":
                    encrypted = self.symmetric_encryption.encrypt(plaintext)
                    payload = {
                        "id": message_obj.id,
                        "content": encrypted,
                        "encrypted": True,
                        "timestamp": message_obj.timestamp,
                        "user_id": origin_user_id,
                        "tipo_comunicacion": "Simetrico"
                    }
                else:
                    # Código existente para asimétrico...
                    recipient_info = self.user_info.get(uid, {})
                    recipient_pub = recipient_info.get("public_key")
                    if recipient_pub:
                        encrypted_b64 = self.encrypt_with_public_key_pem(recipient_pub, plaintext)
                        payload = {
                            "id": message_obj.id,
                            "content": encrypted_b64,
                            "encrypted": True,
                            "timestamp": message_obj.timestamp,
                            "user_id": origin_user_id,
                            "tipo_comunicacion": "Asimetrico"
                        }
                    else:
                        payload = {
                            "id": message_obj.id,
                            "content": plaintext,
                            "encrypted": False,
                            "timestamp": message_obj.timestamp,
                            "user_id": origin_user_id,
                            "tipo_comunicacion": "Asimetrico"
                        }
                await ws.send_text(json.dumps(payload))
            except Exception as e:
                print(f"Error enviando a {uid}: {e}")

        # Enviar a admins
        for uid, ws in list(self.admin_connections.items()):
            try:
                recipient_info = self.user_info.get(uid, {})
                recipient_pub = recipient_info.get("public_key")
                
                if self.tipo_comunicacion == "Asimetrico" and recipient_pub:
                    encrypted_b64 = self.encrypt_with_public_key_pem(recipient_pub, plaintext)
                    payload = {
                        "id": message_obj.id, 
                        "content": encrypted_b64, 
                        "encrypted": True, 
                        "timestamp": message_obj.timestamp, 
                        "user_id": origin_user_id,
                        "tipo_comunicacion": self.tipo_comunicacion
                    }
                else:
                    payload = {
                        "id": message_obj.id, 
                        "content": plaintext, 
                        "encrypted": False, 
                        "timestamp": message_obj.timestamp, 
                        "user_id": origin_user_id,
                        "tipo_comunicacion": self.tipo_comunicacion
                    }
                # incluir ip/port en el payload para admins
                payload.update({"user_ip": message_obj.user_ip, "user_port": message_obj.user_port})
                await ws.send_text(json.dumps(payload))
            except Exception as e:
                print(f"Error enviando a admin {uid}: {e}")

# --- Instancia global ---
chat_manager = ChatManager()

# --- Endpoints HTTP ---
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

# --- Nuevo endpoint para cambiar tipo de comunicación ---
@app.post("/tipo-comunicacion")
async def cambiar_tipo_comunicacion(request: TipoComunicacionRequest):
    """Endpoint para cambiar entre comunicación Asimétrica y Simétrica"""
    success = chat_manager.set_tipo_comunicacion(request.tipo)
    if success:
        return {
            "status": "success", 
            "message": f"Tipo de comunicación cambiado a: {request.tipo}",
            "tipo_actual": chat_manager.get_tipo_comunicacion()
        }
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Tipo de comunicación no válido: {request.tipo}. Use 'Asimetrico' o 'Simetrico'"
        )

@app.get("/tipo-comunicacion")
async def obtener_tipo_comunicacion():
    """Endpoint para obtener el tipo de comunicación actual"""
    return {
        "tipo_actual": chat_manager.get_tipo_comunicacion()
    }

@app.get("/symmetric-key")
async def get_symmetric_key():
    """Endpoint para obtener la clave simétrica actual"""
    return {
        "symmetric_key": chat_manager.get_symmetric_key()
    }

# --- WebSocket endpoints ---
# En el websocket_endpoint - AGREGAR ESTOS PRINTS
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await chat_manager.connect(websocket, user_id, is_admin=False)
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)

            if data.get("type") == "message" and "content" in data:
                print(f"\n=== MENSAJE RECIBIDO de {user_id} ===")
                print(f"Tipo comunicación: {chat_manager.get_tipo_comunicacion()}")
                print(f"Contenido recibido: {data['content'][:100]}...")

                try:
                    if chat_manager.get_tipo_comunicacion() == "Asimetrico":
                        decrypted = chat_manager.decrypt_with_private_key(data["content"])
                        print(f"✅ Mensaje descifrado (asimétrico): {decrypted}")
                    elif chat_manager.get_tipo_comunicacion() == "Simetrico":
                        decrypted = chat_manager.symmetric_encryption.decrypt(data["content"])
                        print(f"✅ Mensaje descifrado (simétrico): {decrypted}")
                    else:
                        decrypted = data["content"]
                        print(f"📝 Mensaje en texto plano: {decrypted}")
                except Exception as e:
                    print(f"❌ Error al descifrar: {e}")
                    decrypted = data["content"]

                await chat_manager.broadcast_message(decrypted, origin_user_id=user_id)

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
            if data.get("type") == "message" and "content" in data:
                try:
                    if chat_manager.get_tipo_comunicacion() == "Asimetrico":
                        decrypted = chat_manager.decrypt_with_private_key(data["content"])
                    else:
                        decrypted = data["content"]
                except Exception:
                    decrypted = data["content"]

                await chat_manager.broadcast_message(decrypted, origin_user_id=admin_id)
            else:
                if "content" in data:
                    try:
                        if chat_manager.get_tipo_comunicacion() == "Asimetrico":
                            decrypted = chat_manager.decrypt_with_private_key(data["content"])
                        else:
                            decrypted = data["content"]
                    except Exception:
                        decrypted = data["content"]
                    await chat_manager.broadcast_message(decrypted, origin_user_id=admin_id)

    except WebSocketDisconnect:
        chat_manager.disconnect(admin_id)

@app.get("/")
async def root():
    return {
        "message": "Chat WebSocket Server está funcionando",
        "tipo_comunicacion_actual": chat_manager.get_tipo_comunicacion()
    }