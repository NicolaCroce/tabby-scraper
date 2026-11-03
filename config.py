# config.py
"""
Módulo de configuración global.
Carga las variables de entorno desde el archivo .env de forma segura.
"""
import os
from dotenv import load_dotenv

# Carga el archivo .env ubicado en la raíz del proyecto
load_dotenv()

# Obtiene la cadena de conexión desde las variables de entorno
NEON_DB_URL = os.getenv("NEON_DB_URL")

# Validación preventiva
if not NEON_DB_URL:
    raise ValueError(
        "❌ ERROR CRÍTICO: La variable NEON_DB_URL no está configurada en el archivo .env"
    )