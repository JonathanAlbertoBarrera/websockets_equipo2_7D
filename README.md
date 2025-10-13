# Proyecto CHAT CON WEBSOCKETS

Este proyecto incluye un backend en Python y un frontend en React.  
A continuación se explican los pasos para ejecutar ambos entornos en tu máquina.

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

npm install crypto-js

# El frontend estará disponible en:
# http://localhost:5173
```


