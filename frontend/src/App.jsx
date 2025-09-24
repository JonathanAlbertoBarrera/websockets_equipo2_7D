import React, { useState, useEffect, useRef } from 'react';
import { Send, Lock, Eye, EyeOff } from 'lucide-react';

const ChatApp = () => {
  // Configuración del servidor - CAMBIA ESTA IP POR LA DE TU PC
  //const SERVER_IP = 'localhost'; 
  const SERVER_IP = '192.168.1.64';//Aqui ponen su ip de la pc PARA ACCEDER DESDE EL CELULAR
  const SERVER_PORT = '8000';
  
  // Estados principales
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [userId, setUserId] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminPassword, setAdminPassword] = useState('');
  const [showAdminLogin, setShowAdminLogin] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  
  // Referencias
  const wsRef = useRef(null);
  const messagesEndRef = useRef(null);
  
  // Scroll automático al final
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  
  useEffect(() => {
    scrollToBottom();
  }, [messages]);
  
  // Generar ID único para el usuario
  useEffect(() => {
    if (!userId) {
      setUserId(`user_${Date.now()}_${Math.floor(Math.random() * 1000)}`);
    }
  }, []);
  
  // Conectar WebSocket
  const connectWebSocket = (asAdmin = false) => {
    const wsUrl = asAdmin 
      ? `ws://${SERVER_IP}:${SERVER_PORT}/ws/admin/${userId}`
      : `ws://${SERVER_IP}:${SERVER_PORT}/ws/${userId}`;
    
    wsRef.current = new WebSocket(wsUrl);
    
    wsRef.current.onopen = () => {
      setIsConnected(true);
      console.log(`Conectado como ${asAdmin ? 'admin' : 'usuario regular'}`);
    };
    
    wsRef.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      setMessages(prev => [...prev, message]);
    };
    
    wsRef.current.onclose = () => {
      setIsConnected(false);
      console.log('Conexión WebSocket cerrada');
    };
    
    wsRef.current.onerror = (error) => {
      console.error('Error WebSocket:', error);
      setIsConnected(false);
    };
  };
  
  // Login como admin
  const handleAdminLogin = async () => {
    try {
      const response = await fetch(`http://${SERVER_IP}:${SERVER_PORT}/admin/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ password: adminPassword }),
      });
      
      if (response.ok) {
        setIsAdmin(true);
        setShowAdminLogin(false);
        setAdminPassword('');
        connectWebSocket(true);
      } else {
        alert('Contraseña incorrecta');
      }
    } catch (error) {
      console.error('Error en login admin:', error);
      alert('Error al conectar con el servidor');
    }
  };
  
  // Enviar mensaje
  const sendMessage = () => {
    if (newMessage.trim() && wsRef.current && isConnected) {
      wsRef.current.send(JSON.stringify({
        content: newMessage
      }));
      setNewMessage('');
    }
  };
  
  // Manejar Enter
  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      sendMessage();
    }
  };
  
  // Formatear timestamp
  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString('es-ES', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-t-lg shadow-lg p-4 border-b">
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold text-gray-800">
              Chat en Tiempo Real
              {isAdmin && <span className="text-red-600 text-sm ml-2">[ADMIN]</span>}
            </h1>
            
            <div className="flex items-center space-x-2">
              {/* Indicador de conexión */}
              <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}>
              </div>
              <span className="text-sm text-gray-600">
                {isConnected ? 'Conectado' : 'Desconectado'}
              </span>
              
              {/* Botones de admin */}
              {!isConnected && (
                <>
                  <button
                    onClick={() => setShowAdminLogin(!showAdminLogin)}
                    className="bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded text-sm flex items-center space-x-1"
                  >
                    <Lock size={16} />
                    <span>Admin</span>
                  </button>
                  
                  <button
                    onClick={() => connectWebSocket(false)}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded text-sm"
                  >
                    Conectar
                  </button>
                </>
              )}
            </div>
          </div>
          
          {/* Login de Admin */}
          {showAdminLogin && !isConnected && (
            <div className="mt-4 p-4 bg-red-50 rounded-lg border border-red-200">
              <h3 className="font-semibold text-red-800 mb-2">Login de Administrador</h3>
              <div className="flex items-center space-x-2">
                <div className="relative flex-1">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={adminPassword}
                    onChange={(e) => setAdminPassword(e.target.value)}
                    placeholder="Contraseña de admin"
                    className="w-full p-2 pr-10 border rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500"
                    onKeyPress={(e) => e.key === 'Enter' && handleAdminLogin()}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-2 top-2.5 text-gray-400 hover:text-gray-600"
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                <button
                  onClick={handleAdminLogin}
                  className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg"
                >
                  Entrar
                </button>
              </div>
              <p className="text-sm text-red-600 mt-2">
                Contraseña por defecto: admin123
              </p>
            </div>
          )}
        </div>
        
        {/* Área de mensajes */}
        <div className="bg-white shadow-lg border-x h-96 overflow-y-auto p-4">
          {messages.length === 0 && (
            <div className="text-center text-gray-500 mt-8">
              <p>No hay mensajes aún.</p>
              <p className="text-sm">¡Sé el primero en escribir algo!</p>
            </div>
          )}
          
          {messages.map((message) => (
            <div key={message.id} className="mb-3">
              <div className="flex items-start space-x-2">
                <div className="flex-1">
                  <div className="flex items-center space-x-2 mb-1">
                    <span className="font-semibold text-sm text-gray-700">
                      {message.user_id}
                    </span>
                    <span className="text-xs text-gray-500">
                      {formatTime(message.timestamp)}
                    </span>
                    {isAdmin && message.user_ip && (
                      <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">
                        {message.user_ip}:{message.user_port}
                      </span>
                    )}
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3 text-gray-800">
                    {message.content}
                  </div>
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
        
        {/* Input de mensaje */}
        <div className="bg-white rounded-b-lg shadow-lg p-4">
          <div className="flex items-center space-x-2">
            <input
              type="text"
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={isConnected ? "Escribe tu mensaje..." : "Conectate para enviar mensajes"}
              disabled={!isConnected}
              className="flex-1 p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
            />
            <button
              onClick={sendMessage}
              disabled={!isConnected || !newMessage.trim()}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white p-3 rounded-lg transition-colors"
            >
              <Send size={20} />
            </button>
          </div>
          
          <div className="flex justify-between items-center mt-2 text-sm text-gray-600">
            <span>Tu ID: {userId}</span>
            <span>{messages.length} mensaje{messages.length !== 1 ? 's' : ''}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatApp;