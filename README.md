# Proyecto CHAT CON WEBSOCKETS

## Historial de Versiones y Mejoras de Seguridad

### Versión 1 - Chat Básico con WebSockets
**MD5:** 03dfeb1aae885130dd6915c65f42f393

Esta versión inicial implementó la funcionalidad básica del chat en tiempo real utilizando WebSockets. 
**Beneficios para el usuario:**
- Comunicación instantánea entre usuarios
- Interfaz de administrador para monitoreo
- Historial de mensajes
- Sin necesidad de actualizar la página
 **Nota:** Los mensajes se transmiten sin cifrado en esta versión.

### Versión 2 - Implementación de Cifrado Dual
**MD5:** 82d169fcdf9dcf822a638e583f95996c

Esta versión introdujo dos tipos de cifrado para mayor flexibilidad y seguridad.
**Beneficios para el usuario:**
- Opción de elegir entre cifrado simétrico o asimétrico
- Cifrado simétrico: Más rápido, ideal para mensajes grandes
- Cifrado asimétrico (RSA): Mayor seguridad, ideal para información sensible
- Posibilidad de cambiar el tipo de cifrado en tiempo real
- Protección contra interceptación de mensajes

### Versión 3 - Seguridad Avanzada
**MD5:** 54c199d32e0e3080d4441d57cedb3a4a

Versión con importantes mejoras en seguridad.
**Beneficios para el usuario:**
- Cifrado asimétrico RSA exclusivo para máxima seguridad
- Verificación de integridad de mensajes mediante SHA-256
- Protección contra manipulación de mensajes
- Garantía de que los mensajes no han sido alterados durante la transmisión
- Mayor confiabilidad en la comunicación

### Versión 4 - Hardening y SSL/TLS
**MD5:** 11ff91434407dec5a915893240be21bd

Versión enfocada en seguridad profesional y mejores prácticas de desarrollo.
**Ventajas de usar SSL/TLS:**
-  Comunicación cifrada entre cliente y servidor
- WebSocket Secure (WSS) para mensajes en tiempo real
- Preparado para producción (solo se necesita implementar certificados válidos)

**Beneficios para el usuario:**
- **Hardening de Seguridad**: Eliminación completa de valores hardcodeados
  - Variables de entorno obligatorias para todas las configuraciones sensibles
  - El sistema no arranca sin configuración adecuada
  - Contraseñas y claves secretas configurables por entorno
  
- **SSL/TLS (HTTPS y WSS)**:
  - Comunicación completamente cifrada con certificados SSL/TLS
  - WebSocket Secure (WSS) para mensajes en tiempo real
  - Preparado para producción con certificados válidos
  
- **Gestión de Logs Inteligente**:
  - Logs de debug solo en modo desarrollo
  - Información sensible oculta en producción
  - Mejor experiencia de desarrollo y diagnóstico
  
- **Seguridad Empresarial**:
  - Configuración flexible por entorno (development/production)
  - CORS configurable por dominio
  - Tamaño de claves RSA ajustable (2048/3072/4096 bits)

### Versión 5 - Sistema de Firma Digital Colaborativa (Versión Actual)
**MD5:** 07299d9e2156de069f71523f2dc7ec95

Versión actual con sistema completo de firma digital colaborativa y mejoras en la experiencia de usuario.

**Funcionalidades de Firma Digital:**
- **Subida de Archivos**: 
  - Soporte para múltiples formatos (PDF, TXT, ZIP)
  - Selección de firmantes autorizados
  - Notificaciones en tiempo real vía WebSocket
  
- **Firma Digital Real**:
  - Generación de firmas digitales con SHA-256
  - Para PDFs: Agrega página de firma con ReportLab con información de todos los firmantes
  - Para TXT: Anexa bloque de firmas al final del documento
  - Timestamp y datos del firmante en cada firma
  
- **Gestión de Permisos**:
  - Solo usuarios autorizados pueden firmar
  - El uploader y firmantes seleccionados pueden visualizar archivos
  - Control de estados: Pendiente, Parcialmente Firmado, Completamente Firmado
  
- **Visualización y Descarga**:
  - Vista previa de archivos en navegador (nueva pestaña)
  - Descarga de archivos firmados
  - Lista de "Mis Archivos" y "Archivos Pendientes de Firma"

**Mejoras en UX/UI:**
- **Interfaz Moderna sin Emojis**: 
  - Diseño limpio y profesional
  
- **Sistema de Notificaciones con SweetAlert2**:
  - Modales elegantes centrados en pantalla
  - Iconos animados según tipo (éxito/error/info)
  - Auto-cierre inteligente (3s para éxitos, manual para errores)
  - Barra de progreso visual del timer
  

**Beneficios Técnicos:**
- Integración de PyPDF2 y ReportLab para manipulación de PDFs
- Sistema de permisos granular por archivo
- WebSocket para notificaciones en tiempo real de firmas
- Arquitectura preparada para escalabilidad

---

Este proyecto incluye un backend en Python y un frontend en React.  
A continuación se explican los pasos para ejecutar ambos entornos en tu máquina.

##  Configuración Inicial - Variables de Entorno

### Backend
Antes de ejecutar el backend, debes configurar las variables de entorno:

1. Navega a la carpeta del backend:
```bash
cd backend
```

2. Copia el archivo de ejemplo `.env.example` y renómbralo a `.env`:
```bash
# Windows PowerShell
Copy-Item .env.example .env

# O manualmente copia y pega el archivo
```

3. Edita el archivo `.env` con tus valores de configuración:


### Frontend
Configura las variables de entorno del frontend:

1. Navega a la carpeta del frontend:
```bash
cd frontend
```

2. Copia el archivo de ejemplo `.env.example` y renómbralo a `.env`:
```bash
# Windows PowerShell
Copy-Item .env.example .env

# O manualmente copia y pega el archivo
```

3. Edita el archivo `.env` con las URLs correctas:

## 1. Instalar Python
```bash
# Ir a https://www.python.org/downloads/
# Descargar la versión recomendada
# Importante: marcar la opción "Add Python to PATH"

# Verificar instalación
python --version
```

## 2. Ejecutar Backend

### 2.1. Generar Certificados SSL/TLS (Solo primera vez)

Para usar HTTPS y WSS (WebSocket Secure), primero debes generar los certificados SSL:

```bash
# Navegar a la carpeta del backend (si no estás ahí)
cd backend

# Activar entorno virtual (Windows)
venv\Scripts\activate

# Generar certificados SSL autofirmados
python generate_certs.py
```

Esto creará dos archivos:
- `ssl_cert.pem` - Certificado SSL
- `ssl_cert.key` - Clave privada

 **NOTA IMPORTANTE**: Estos certificados son para **desarrollo local** solamente. El navegador mostrará una advertencia de seguridad que debes aceptar.

### 2.2. Iniciar el servidor

```bash
# Navegar a la carpeta del backend
cd backend

# Crear entorno virtual (si no existe)
python -m venv venv

# Activar entorno virtual (Windows)
venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar servidor
# OPCIÓN 1: Con SSL/TLS (Recomendado)
python main.py

# OPCIÓN 2: Sin SSL (solo desarrollo rápido)
# Cambia USE_SSL=false en el .env y luego:
uvicorn main:app --reload

# El backend estará disponible en:
# Con SSL: https://localhost:8000
# Sin SSL: http://localhost:8000
```

**Si usas SSL, verás:**
-  El navegador mostrará advertencia de certificado autofirmado (es normal en desarrollo)

**Para aceptar el certificado en el navegador:**
1. Ve a `https://localhost:8000` en tu navegador
2. Click en "Avanzado" o "Advanced"
3. Click en "Continuar a localhost (no seguro)" o "Proceed to localhost (unsafe)"


## 3. Ejecutar Frontend

```bash
# Abrir una NUEVA terminal/consola para el frontend

# Navegar a la carpeta del frontend
cd frontend

# Instalar dependencias
npm install

# Ejecutar servidor de desarrollo con HTTPS
npm run dev

# El frontend estará disponible en:
# https://localhost:5173
```

**Si usas SSL/TLS:**
1. Abre `https://localhost:5173` en tu navegador
2. Acepta la advertencia de certificado (similar al paso del backend)
3. ¡Listo! Ya puedes usar el chat de forma segura con HTTPS y WSS


## 4. Solución de Problemas

### Advertencia de Certificado

Si ves advertencias de seguridad en el navegador:
1. Es **NORMAL** con certificados autofirmados en desarrollo
2. Click en "Avanzado" → "Continuar a localhost"
3. En producción, se usarian certificados válidos

### Desactivar SSL para desarrollo rápido

Si prefieres desarrollar sin SSL (no recomendado):
1. Cambia `USE_SSL=false` en `backend/.env`
2. Cambia las URLs en `frontend/.env` a `http://` y `ws://`
3. Reinicia ambos servidores

### Error "Certificate not found"

Si ves este error:
```bash
cd backend
python generate_certs.py
```




