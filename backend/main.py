from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional
import asyncio

# Modelos de datos
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

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Almacenamiento en memoria
class ChatManager:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}
        self.admin_connections: Dict[str, WebSocket] = {}
        self.messages: List[Message] = []
        self.user_info: Dict[str, dict] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str, is_admin: bool = False):
        await websocket.accept()
        
        # Obtener información del cliente
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
        }
        
        print(f"Usuario {'admin' if is_admin else 'regular'} conectado: {user_id} desde {client_host}:{client_port}")
        
        # Enviar historial de mensajes al usuario que se conecta
        for message in self.messages[-50:]:  # Últimos 50 mensajes
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
        message_data = {
            "id": message.id,
            "content": message.content,
            "timestamp": message.timestamp,
            "user_id": message.user_id
        }
        
        # Solo los admins ven la información adicional
        if is_admin:
            message_data.update({
                "user_ip": message.user_ip,
                "user_port": message.user_port
            })
        
        await websocket.send_text(json.dumps(message_data))
    
    async def broadcast_message(self, message: Message):
        # Guardar mensaje en historial
        self.messages.append(message)
        
        # Enviar a usuarios regulares (sin info IP)
        for websocket in self.connections.values():
            try:
                await self.send_message_to_user(websocket, message, is_admin=False)
            except:
                pass  # Conexión cerrada
        
        # Enviar a admins (con info IP)
        for websocket in self.admin_connections.values():
            try:
                await self.send_message_to_user(websocket, message, is_admin=True)
            except:
                pass  # Conexión cerrada

# Instancia del manejador de chat
chat_manager = ChatManager()

# Endpoints HTTP
@app.post("/admin/login")
async def admin_login(request: LoginRequest):
    if request.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    
    admin_token = str(uuid.uuid4())
    return {"token": admin_token, "message": "Login exitoso"}

@app.get("/admin/users")
async def get_connected_users():
    # Endpoint para que los admins vean usuarios conectados
    return {
        "users": [
            {
                "user_id": user_id,
                "ip": info["ip"],
                "port": info["port"],
                "is_admin": info["is_admin"],
                "connected_at": info["connected_at"]
            }
            for user_id, info in chat_manager.user_info.items()
        ]
    }

# WebSocket endpoints
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await chat_manager.connect(websocket, user_id, is_admin=False)
    
    try:
        while True:
            # Recibir mensaje del cliente
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Crear mensaje
            user_info = chat_manager.user_info.get(user_id, {})
            message = Message(
                id=str(uuid.uuid4()),
                content=message_data["content"],
                timestamp=datetime.now().isoformat(),
                user_id=user_id,
                user_ip=user_info.get("ip"),
                user_port=user_info.get("port")
            )
            
            # Broadcast del mensaje
            await chat_manager.broadcast_message(message)
            
    except WebSocketDisconnect:
        chat_manager.disconnect(user_id)

@app.websocket("/ws/admin/{user_id}")
async def admin_websocket_endpoint(websocket: WebSocket, user_id: str):
    await chat_manager.connect(websocket, f"admin_{user_id}", is_admin=True)
    
    try:
        while True:
            # Recibir mensaje del admin
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Crear mensaje de admin
            admin_user_id = f"admin_{user_id}"
            user_info = chat_manager.user_info.get(admin_user_id, {})
            message = Message(
                id=str(uuid.uuid4()),
                content=f"[ADMIN] {message_data['content']}",
                timestamp=datetime.now().isoformat(),
                user_id=admin_user_id,
                user_ip=user_info.get("ip"),
                user_port=user_info.get("port")
            )
            
            # Broadcast del mensaje
            await chat_manager.broadcast_message(message)
            
    except WebSocketDisconnect:
        chat_manager.disconnect(f"admin_{user_id}")

@app.get("/")
async def root():
    return {"message": "Chat WebSocket Server está funcionando"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)