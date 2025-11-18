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
⚠️ **Nota:** Los mensajes se transmiten sin cifrado en esta versión.

### Versión 2 - Implementación de Cifrado Dual
**MD5:** 82d169fcdf9dcf822a638e583f95996c

Esta versión introdujo dos tipos de cifrado para mayor flexibilidad y seguridad.
**Beneficios para el usuario:**
- Opción de elegir entre cifrado simétrico o asimétrico
- Cifrado simétrico: Más rápido, ideal para mensajes grandes
- Cifrado asimétrico (RSA): Mayor seguridad, ideal para información sensible
- Posibilidad de cambiar el tipo de cifrado en tiempo real
- Protección contra interceptación de mensajes

### Versión 3 - Seguridad Avanzada (Versión Actual)
**MD5:** 54c199d32e0e3080d4441d57cedb3a4a

Versión actual con importantes mejoras en seguridad.
**Beneficios para el usuario:**
- Cifrado asimétrico RSA exclusivo para máxima seguridad
- Verificación de integridad de mensajes mediante SHA-256
- Protección contra manipulación de mensajes
- Garantía de que los mensajes no han sido alterados durante la transmisión
- Mayor confiabilidad en la comunicación


Este proyecto incluye un backend en Python y un frontend en React.  
A continuación se explican los pasos para ejecutar ambos entornos en tu máquina.

## ⚙️ Configuración Inicial - Variables de Entorno

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

```bash
# Navegar a la carpeta del backend
cd backend

# Crear entorno virtual
python -m venv venv

# Activar entorno virtual (Windows)
venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar servidor
uvicorn main:app --reload

# El backend estará disponible en:
# http://localhost:8000

```


## 3. Ejecutar Frontend

```bash
# Abrir una NUEVA terminal/consola para el frontend

# Navegar a la carpeta del frontend
cd frontend

# Instalar dependencias
npm install

# Ejecutar servidor de desarrollo
npm run dev

# El frontend estará disponible en:
# http://localhost:5173
```


