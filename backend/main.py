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

# Configuración
ADMIN_PASSWORD = "admin123" 

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en prod, restringir dominios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ChatManager con RSA ---
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
            
            # Mostrar claves para debug (no lo hagas en producción)
            print("Clave pública del servidor (PEM):")
            print(self.get_public_key_pem())

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
            
            print(f"Usuario {'admin' if is_admin else 'regular'} conectado: {user_id} desde {client_host}:{client_port}")
            
            try:
                # Enviar historial de mensajes al usuario que se conecta
                for message in self.messages[-50:]:
                    await self.send_message_to_user(websocket, message, is_admin)
            except Exception as e:
                print(f"Error enviando historial a {user_id}: {e}")
                
            return True
        except Exception as e:
            print(f"Error en conexión de {user_id}: {e}")
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
                print(f"Error al cerrar websocket de {user_id}: {e}")
                
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
                print(f"Error preparando mensaje para {uid}: {e}")
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
                print(f"Error preparando mensaje para admin {uid}: {e}")
                to_disconnect.add(uid)

        # Enviar mensajes
        for uid, ws, msg in regular_messages:
            try:
                await ws.send_text(msg)
            except Exception as e:
                print(f"Error enviando a {uid}: {e}")
                to_disconnect.add(uid)

        for uid, ws, msg in admin_messages:
            try:
                await ws.send_text(msg)
            except Exception as e:
                print(f"Error enviando a admin {uid}: {e}")
                to_disconnect.add(uid)

        # Desconectar usuarios con error al final
        for uid in to_disconnect:
            try:
                await self.disconnect(uid)
            except Exception as e:
                print(f"Error al desconectar {uid}: {e}")# --- Instancia global ---
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
                    print(f"\n=== MENSAJE RECIBIDO de {user_id} ===")
                    print(f"Contenido cifrado: {data['content'][:100]}...")
                    print(f"Hash cifrado: {data['hash'][:100]}...")

                    try:
                        # Descifrar mensaje y hash
                        decrypted_content = chat_manager.decrypt_with_private_key(data["content"])
                        decrypted_hash = chat_manager.decrypt_with_private_key(data["hash"])
                        print(f"✅ Mensaje descifrado (RSA): {decrypted_content}")
                        print(f"✅ Hash descifrado (SHA-256): {decrypted_hash}")
                        
                        await chat_manager.broadcast_message(decrypted_content, decrypted_hash, origin_user_id=user_id)
                    except Exception as e:
                        print(f"❌ Error al descifrar mensaje/hash de {user_id}: {e}")
            except WebSocketDisconnect:
                print(f"WebSocket desconectado: {user_id}")
                await chat_manager.disconnect(user_id)
                break
            except json.JSONDecodeError:
                print(f"Error: Mensaje mal formado de {user_id}")
                continue
            except Exception as e:
                print(f"Error procesando mensaje de {user_id}: {e}")
                await chat_manager.disconnect(user_id)
                break
    except Exception as e:
        print(f"Error en el websocket de {user_id}: {e}")
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
                    print(f"✅ Mensaje admin descifrado (RSA): {decrypted_content}")
                    print(f"✅ Hash admin descifrado (SHA-256): {decrypted_hash}")
                except Exception as e:
                    print(f"❌ Error al descifrar mensaje/hash de admin: {e}")
                    return

                await chat_manager.broadcast_message(decrypted_content, decrypted_hash, origin_user_id=admin_id)

    except WebSocketDisconnect:
        chat_manager.disconnect(admin_id)

@app.get("/")
async def root():
    return {
        "message": "Chat WebSocket Server está funcionando con cifrado RSA"
    }