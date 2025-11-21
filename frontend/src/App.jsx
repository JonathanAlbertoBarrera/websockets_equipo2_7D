import React, { useState, useEffect, useRef } from 'react';
import { Send, Lock, Eye, EyeOff } from 'lucide-react';

const ChatApp = () => {
  // Validar y cargar variables de entorno requeridas
  const getRequiredEnv = (key) => {
    const value = import.meta.env[key];
    if (!value) {
      const error = `❌ ERROR: Variable de entorno '${key}' no configurada.\n` +
        `Por favor, configura el archivo .env con todas las variables requeridas.\n` +
        `Consulta .env.example para ver el formato correcto.`;
      console.error(error);
      alert(error);
      throw new Error(error);
    }
    return value;
  };

  let WS_URL, API_URL, DEBUG, ENVIRONMENT;
  
  try {
    WS_URL = getRequiredEnv('VITE_WS_URL');
    API_URL = getRequiredEnv('VITE_API_URL');
    DEBUG = import.meta.env.VITE_DEBUG === 'true';
    ENVIRONMENT = import.meta.env.VITE_ENVIRONMENT || 'development';
  } catch (error) {
    return (
      <div style={{ padding: '20px', color: 'red' }}>
        <h2>Error de Configuración</h2>
        <p>{error.message}</p>
        <p>Revisa tu archivo <code>.env</code> en la carpeta frontend</p>
      </div>
    );
  }
  
  // Función para logs condicionales
  const debugLog = (...args) => {
    if (ENVIRONMENT === 'development') {
      console.log(...args);
    }
  };
  
  // Estados principales
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [userId, setUserId] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminPassword, setAdminPassword] = useState('');
  const [showAdminLogin, setShowAdminLogin] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  // Solo se usa cifrado asimétrico
  
  // ---- Claves RSA ----
  const [publicKey, setPublicKey] = useState(null);
  const [privateKey, setPrivateKey] = useState(null);
  const [serverPublicKey, setServerPublicKey] = useState(null);
  
  // ---- Firma Digital ----
  const [connectedUsers, setConnectedUsers] = useState([]);
  const [pendingFiles, setPendingFiles] = useState([]);
  const [fileNotifications, setFileNotifications] = useState([]);
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [selectedSigners, setSelectedSigners] = useState([]);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [showMyFiles, setShowMyFiles] = useState(false);
  const [previewFile, setPreviewFile] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  
  // Referencias
  const wsRef = useRef(null);
  const messagesEndRef = useRef(null);
  const isAdminRef = useRef(false);
  
  // Actualizar la referencia cuando cambia isAdmin
  useEffect(() => {
    isAdminRef.current = isAdmin;
  }, [isAdmin]);
  
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

  // Actualizar lista de usuarios conectados periódicamente
  useEffect(() => {
    if (isConnected) {
      fetchConnectedUsers();
      fetchUploadedFiles();
      const interval = setInterval(() => {
        fetchConnectedUsers();
        fetchUploadedFiles();
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [isConnected]);

  // Debug modal de vista previa
  useEffect(() => {
    debugLog('👀 Estado modal:', { showPreview, previewFile });
  }, [showPreview, previewFile]);

  // Función para cambiar el tipo de comunicación en el servidor
  const cambiarTipoComunicacionServidor = async (tipo) => {
    try {
      const response = await fetch(`${API_URL}/tipo-comunicacion`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ tipo: tipo }),
      });
      
      if (response.ok) {
        const data = await response.json();
        return true;
      } else {
        debugLog('Error cambiando tipo de comunicación en el servidor');
        return false;
      }
    } catch (error) {
      debugLog('Error conectando con el servidor:', error);
      return false;
    }
  };

  // Generar par de claves RSA para el cliente
  const generateRSAKeys = async () => {
    const keyPair = await window.crypto.subtle.generateKey(
      {
        name: "RSA-OAEP",
        modulusLength: 2048,
        publicExponent: new Uint8Array([1, 0, 1]),
        hash: "SHA-256"
      },
      true,
      ["encrypt", "decrypt"]
    );

    setPublicKey(keyPair.publicKey);
    setPrivateKey(keyPair.privateKey);
    debugLog(" Claves RSA generadas para el cliente.");
  };

  // Exportar la clave pública en formato PEM
  const exportPublicKey = async (key) => {
    const exported = await window.crypto.subtle.exportKey("spki", key);
    const exportedAsString = String.fromCharCode(...new Uint8Array(exported));
    const exportedAsBase64 = btoa(exportedAsString);
    return `-----BEGIN PUBLIC KEY-----\n${exportedAsBase64.match(/.{1,64}/g).join('\n')}\n-----END PUBLIC KEY-----`;
  };

  // Cifrar texto con clave pública
  const encryptMessage = async (text, publicKeyPem) => {
    // Convertir la clave PEM del servidor a formato usable
    const binaryDer = Uint8Array.from(atob(publicKeyPem
      .replace(/-----.*-----/g, '')
      .replace(/\s/g, '')
    ), c => c.charCodeAt(0));

    const key = await window.crypto.subtle.importKey(
      "spki",
      binaryDer.buffer,
      { name: "RSA-OAEP", hash: "SHA-256" },
      false,
      ["encrypt"]
    );

    const encoded = new TextEncoder().encode(text);
    const ciphertext = await window.crypto.subtle.encrypt({ name: "RSA-OAEP" }, key, encoded);
    return btoa(String.fromCharCode(...new Uint8Array(ciphertext)));
  };

  // Descifrar mensaje con la clave privada
  const decryptMessage = async (cipherBase64) => {
    const cipherBytes = Uint8Array.from(atob(cipherBase64), c => c.charCodeAt(0));
    const decrypted = await window.crypto.subtle.decrypt({ name: "RSA-OAEP" }, privateKey, cipherBytes);
    return new TextDecoder().decode(decrypted);
  };

  // Conectar WebSocket
  const connectWebSocket = async (asAdmin = false) => {
    await generateRSAKeys();

    // Obtener la clave pública del servidor
    try {
      const response = await fetch(`${API_URL}/public-key`);
      const data = await response.json();
      setServerPublicKey(data.public_key);
      debugLog(" Clave pública del servidor obtenida.");
    } catch (error) {
      debugLog(" Error obteniendo clave pública del servidor:", error);
    }

    const wsUrl = asAdmin
      ? `${WS_URL}/ws/admin/${userId}`
      : `${WS_URL}/ws/${userId}`;
    
    wsRef.current = new WebSocket(wsUrl);
    
    wsRef.current.onopen = async () => {
      setIsConnected(true);
      debugLog(`Conectado como ${asAdmin ? 'admin' : 'usuario regular'}`);
      
      // Enviar registro con clave pública
      if (publicKey) {
        try {
          const publicKeyPem = await exportPublicKey(publicKey);
          wsRef.current.send(JSON.stringify({
            type: "register",
            public_key: publicKeyPem
          }));
        } catch (error) {
          debugLog(" Error enviando clave pública:", error);
        }
      }
    };
    
    wsRef.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      debugLog(' Mensaje recibido completo:', message);
      debugLog(' asAdmin (en callback):', asAdmin);
      debugLog(' isAdmin (estado):', isAdmin);
      debugLog(' user_ip:', message.user_ip);
      debugLog(' user_port:', message.user_port);
      
      (async () => {
        try {
          // Manejar notificaciones de firma digital
          if (message.type === 'signature_invitation') {
            debugLog(' Invitación de firma recibida:', message);
            setPendingFiles(prev => [...prev, message]);
            setFileNotifications(prev => [...prev, {
              id: Date.now(),
              text: `${message.invited_by} te invitó a firmar: ${message.filename}`,
              fileId: message.file_id
            }]);
            return;
          }

          if (message.type === 'signature_performed') {
            debugLog('⚡ Firma realizada:', message);
            setFileNotifications(prev => [...prev, {
              id: Date.now(),
              text: `${message.signed_by} firmó: ${message.filename} (${message.status})`,
              fileId: message.file_id
            }]);
            return;
          }

          if (message.encrypted && privateKey) {
            debugLog(' Mensaje cifrado recibido:', message.content);
            debugLog(' Hash cifrado recibido:', message.hash);
            
            try {
              // Descifrar el mensaje y el hash
              const decryptedContent = await decryptMessage(message.content);
              const decryptedHash = await decryptMessage(message.hash);
              
              // Calcular el hash del mensaje descifrado
              const calculatedHash = await calculateSHA256(decryptedContent);
              
              // Verificar integridad comparando hashes
              if (decryptedHash === calculatedHash) {
                debugLog(' Verificación de integridad exitosa');
                message.content = decryptedContent;
                message.verified = true;
                // Preservar user_ip y user_port para admins
                // (ya vienen en el objeto message desde el backend)
                if (message.user_ip) {
                  debugLog(` Info del usuario: ${message.user_ip}:${message.user_port}`);
                }
              } else {
                debugLog(' Verificación de integridad fallida');
                message.content = ' Error: El mensaje puede haber sido alterado';
                message.verified = false;
              }
              
              debugLog(' Mensaje descifrado:', decryptedContent);
              debugLog(' Hash original:', decryptedHash);
              debugLog(' Hash calculado:', calculatedHash);
            } catch (err) {
              debugLog(" Error al descifrar o verificar mensaje:", err);
              message.verified = false;
            }
          }

          setMessages(prevMessages => {
            // Evitar duplicados verificando el ID del mensaje
            const messageExists = prevMessages.some(m => m.id === message.id);
            if (messageExists) {
              return prevMessages;
            }
            return [...prevMessages, message];
          });
        } catch (err) {
          debugLog("Error al procesar mensaje:", err);
        }
      })();
    };    wsRef.current.onclose = (event) => {
      if (!event.wasClean) {
        debugLog('Conexión perdida. Código:', event.code, 'Razón:', event.reason || 'Sin razón especificada');
      } else {
        debugLog('Conexión cerrada limpiamente. Código:', event.code, 'Razón:', event.reason);
      }
      setIsConnected(false);
      if (event.code !== 1000) { // Si no es un cierre voluntario
        wsRef.current = null;
        setIsAdmin(false);
      }
    };
    
    wsRef.current.onerror = (error) => {
      debugLog(' Error WebSocket:', error);
      setIsConnected(false);
    };
  };
  
  // Login como admin
  const handleAdminLogin = async () => {
    try {
      const response = await fetch(`${API_URL}/admin/login`, {
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
        // Esperar a que el estado se actualice antes de conectar
        setTimeout(() => connectWebSocket(true), 0);
      } else {
        alert('Contraseña incorrecta');
      }
    } catch (error) {
      debugLog('Error en login admin:', error);
      alert('Error al conectar con el servidor');
    }
  };
  
  // Enviar mensaje
  // Función para calcular SHA-256
  const calculateSHA256 = async (message) => {
    const encoder = new TextEncoder();
    const data = encoder.encode(message);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    return hashHex;
  };

  const sendMessage = async () => {
    if (!newMessage.trim() || !wsRef.current || !isConnected) {
      return;
    }

    try {
      const messageText = newMessage.trim();
      debugLog(" Preparando mensaje:", {
        mensajeOriginal: messageText
      });
      
      // 1. Calcular hash SHA-256 del mensaje original
      const messageHash = await calculateSHA256(messageText);
      debugLog(" Hash SHA-256:", messageHash);
      
      // 2. Cifrar el mensaje y el hash por separado
      let encryptedContent, encryptedHash;
      if (serverPublicKey) {
        encryptedContent = await encryptMessage(messageText, serverPublicKey);
        encryptedHash = await encryptMessage(messageHash, serverPublicKey);
        debugLog(" Mensaje cifrado (RSA):", encryptedContent);
        debugLog(" Hash cifrado (RSA):", encryptedHash);
      }

      // Verificar estado de la conexión antes de enviar
      if (wsRef.current.readyState === WebSocket.OPEN) {
        // Crear un mensaje temporal para mostrar inmediatamente
        const tempMessage = {
          id: `temp_${Date.now()}`,
          content: messageText,
          timestamp: new Date().toISOString(),
          user_id: userId,
          encrypted: false
        };

        // Agregar el mensaje temporal a la interfaz
        setMessages(prev => [...prev, tempMessage]);
        
        // Enviar el mensaje y hash cifrados al servidor
        wsRef.current.send(JSON.stringify({
          type: "message",
          content: encryptedContent,
          hash: encryptedHash
        }));
        
        setNewMessage('');
      } else {
        debugLog("Reconectando...");
        await connectWebSocket(isAdmin);
      }
    } catch (error) {
      debugLog("Error procesando mensaje:", error);
      if (error.message.includes('WebSocket')) {
        setIsConnected(false);
        wsRef.current = null;
      }
      alert("Error al enviar el mensaje. Intenta reconectarte.");
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

  // ---- Funciones de Firma Digital ----
  const fetchConnectedUsers = async () => {
    try {
      const response = await fetch(`${API_URL}/admin/users`);
      const data = await response.json();
      setConnectedUsers(data.users || []);
      debugLog('Usuarios conectados:', data.users);
    } catch (error) {
      debugLog('Error obteniendo usuarios conectados:', error);
    }
  };

  const fetchUploadedFiles = async () => {
    try {
      const response = await fetch(`${API_URL}/api/list-files?user_id=${userId}`);
      const data = await response.json();
      setUploadedFiles(data.files || []);
      debugLog('Archivos del usuario:', data.files);
    } catch (error) {
      debugLog('Error obteniendo archivos:', error);
    }
  };

  const uploadFile = async () => {
    if (!selectedFile) {
      alert('Selecciona un archivo');
      return;
    }

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('allowed_signers', JSON.stringify(selectedSigners));
    formData.append('require_all_signers', 'true');
    formData.append('user_id', userId);

    try {
      const response = await fetch(`${API_URL}/api/upload-file`, {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        alert(`Archivo subido: ${data.filename}`);
        setShowFileUpload(false);
        setSelectedFile(null);
        setSelectedSigners([]);
        fetchUploadedFiles(); // Refrescar lista
      } else {
        alert('Error al subir archivo');
      }
    } catch (error) {
      debugLog('Error subiendo archivo:', error);
      alert('Error al subir archivo');
    }
  };

  const signFile = async (fileId) => {
    try {
      const formData = new FormData();
      formData.append('signer_id', userId);

      const response = await fetch(`${API_URL}/api/sign-file/${fileId}`, {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        alert(`Archivo firmado: ${data.file_id}`);
        // Remover de pendientes
        setPendingFiles(prev => prev.filter(f => f.file_id !== fileId));
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail}`);
      }
    } catch (error) {
      debugLog('Error firmando archivo:', error);
      alert('Error al firmar archivo');
    }
  };

  const toggleSignerSelection = (userId) => {
    setSelectedSigners(prev => {
      if (prev.includes(userId)) {
        return prev.filter(id => id !== userId);
      } else {
        return [...prev, userId];
      }
    });
  };

  const downloadFile = (fileId, filename) => {
    const url = `${API_URL}/api/download-file/${fileId}`;
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const openPreview = (fileId, filename, fileType) => {
    debugLog('👁️ Abriendo vista previa:', { fileId, filename, fileType });
    // Abrir en nueva pestaña
    const url = `${API_URL}/api/preview-file/${fileId}`;
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  const closePreview = () => {
    debugLog('✖ Cerrando vista previa');
    setShowPreview(false);
    setPreviewFile(null);
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
            
            <div className="flex items-center space-x-4">
              {/* Indicador de cifrado RSA */}
              <div className="px-4 py-2 rounded-lg font-semibold bg-purple-600 text-black">
                🔒 RSA-2048
              </div>
              
              <div className="flex items-center space-x-2">
                {/* Indicador de conexión */}
                <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}>
                </div>
                <span className="text-sm text-gray-600">
                  {isConnected ? 'Conectado' : 'Desconectado'}
                </span>
                
                {/* Botones de conexión */}
                {!isConnected ? (
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
                ) : (
                  <button
                    onClick={() => {
                      if (wsRef.current) {
                        wsRef.current.close(1000, "Desconexión voluntaria");
                        wsRef.current = null;
                        setIsConnected(false);
                        setIsAdmin(false);
                        setMessages([]);
                        setPublicKey(null);
                        setPrivateKey(null);
                        setServerPublicKey(null);
                      }
                    }}
                    className="bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded text-sm"
                  >
                    Desconectar
                  </button>
                )}
              </div>
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
              {/*
              <p className="text-sm text-red-600 mt-2">
                Contraseña por defecto: admin123
              </p> */}
            </div>
          )}
        </div>

        {/* Notificaciones de Firma */}
        {fileNotifications.length > 0 && (
          <div className="bg-yellow-50 border-x border-yellow-200 p-3">
            <div className="flex justify-between items-center mb-2">
              <h3 className="font-semibold text-yellow-800 text-sm">📋 Notificaciones de Firma</h3>
              <button
                onClick={() => setFileNotifications([])}
                className="text-xs text-yellow-600 hover:text-yellow-800"
              >
                Limpiar
              </button>
            </div>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {fileNotifications.map(notif => (
                <div key={notif.id} className="text-sm text-yellow-700 bg-yellow-100 p-2 rounded">
                  {notif.text}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Panel de Firma Digital */}
        {isConnected && (
          <div className="bg-white border-x p-4 border-b">
            <div className="flex justify-between items-center mb-3">
              <h3 className="font-semibold text-gray-800">✍️ Firma Digital Colaborativa</h3>
              <div className="flex space-x-2">
                <button
                  onClick={() => setShowMyFiles(!showMyFiles)}
                  className="bg-purple-600 hover:bg-purple-700 text-white px-3 py-1 rounded text-sm"
                >
                  {showMyFiles ? 'Ocultar' : '📁 Mis Archivos'}
                </button>
                <button
                  onClick={() => setShowFileUpload(!showFileUpload)}
                  className="bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded text-sm"
                >
                  {showFileUpload ? 'Cancelar' : '+ Subir Archivo'}
                </button>
              </div>
            </div>

            {/* Mis Archivos Subidos */}
            {showMyFiles && uploadedFiles.length > 0 && (
              <div className="bg-purple-50 p-4 rounded-lg border border-purple-200 mb-3">
                <h4 className="font-semibold text-purple-800 mb-3">📁 Mis Archivos</h4>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {uploadedFiles.map(file => (
                    <div key={file.file_id} className="flex justify-between items-center bg-white p-3 rounded border">
                      <div className="flex-1">
                        <p className="font-semibold text-sm">📄 {file.filename}</p>
                        <p className="text-xs text-gray-600">
                          Estado: <span className={`font-semibold ${
                            file.status === 'fully_signed' ? 'text-green-600' :
                            file.status === 'partially_signed' ? 'text-yellow-600' :
                            'text-blue-600'
                          }`}>{file.status}</span>
                        </p>
                        <p className="text-xs text-gray-500">
                          Firmantes: {file.completed_signers.length}/{file.allowed_signers.length}
                        </p>
                      </div>
                      <div className="flex space-x-2">
                        <button
                          onClick={() => openPreview(file.file_id, file.filename, file.file_type)}
                          className="bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1 rounded text-sm"
                          title="Vista previa"
                        >
                          👁️ Ver
                        </button>
                        <button
                          onClick={() => downloadFile(file.file_id, file.filename)}
                          className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded text-sm"
                          title="Descargar archivo"
                        >
                          ⬇️ Descargar
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Formulario de Subida */}
            {showFileUpload && (
              <div className="bg-green-50 p-4 rounded-lg border border-green-200 mb-3">
                <h4 className="font-semibold text-green-800 mb-3">Subir Archivo para Firma</h4>
                <input
                  type="file"
                  accept=".pdf,.txt,.zip"
                  onChange={(e) => setSelectedFile(e.target.files[0])}
                  className="mb-3 text-sm"
                />
                {selectedFile && (
                  <p className="text-sm text-gray-600 mb-3">📄 {selectedFile.name}</p>
                )}
                
                <h5 className="font-semibold text-sm text-gray-700 mb-2">Seleccionar Firmantes:</h5>
                <div className="space-y-2 mb-3 max-h-32 overflow-y-auto">
                  {connectedUsers.filter(u => u.user_id !== userId).map(user => (
                    <label key={user.user_id} className="flex items-center space-x-2 text-sm">
                      <input
                        type="checkbox"
                        checked={selectedSigners.includes(user.user_id)}
                        onChange={() => toggleSignerSelection(user.user_id)}
                        className="rounded"
                      />
                      <span>{user.user_id} {user.is_admin && '👑'}</span>
                    </label>
                  ))}
                  {connectedUsers.length === 1 && (
                    <p className="text-sm text-gray-500">No hay otros usuarios conectados</p>
                  )}
                </div>

                <button
                  onClick={uploadFile}
                  disabled={!selectedFile || selectedSigners.length === 0}
                  className="bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white px-4 py-2 rounded text-sm w-full"
                >
                  Subir y Solicitar Firmas
                </button>
              </div>
            )}

            {/* Archivos Pendientes de Firma */}
            {pendingFiles.length > 0 && (
              <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                <h4 className="font-semibold text-blue-800 mb-3">📝 Archivos Pendientes de Firma</h4>
                <div className="space-y-2">
                  {pendingFiles.map(file => (
                    <div key={file.file_id} className="flex justify-between items-center bg-white p-3 rounded border">
                      <div>
                        <p className="font-semibold text-sm">{file.filename}</p>
                        <p className="text-xs text-gray-600">Subido por: {file.invited_by}</p>
                      </div>
                      <div className="flex space-x-2">
                        <button
                          onClick={() => openPreview(file.file_id, file.filename, file.filename.split('.').pop())}
                          className="bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1 rounded text-sm"
                          title="Vista previa"
                        >
                          👁️ Ver
                        </button>
                        <button
                          onClick={() => signFile(file.file_id)}
                          className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded text-sm"
                        >
                          ✍️ Firmar
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        
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
