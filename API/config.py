import os
from pathlib import Path

from dotenv import load_dotenv

# Define rutas del proyecto, carga el archivo .env y lee la URL de la base de datos.

API_DIR = Path(__file__).resolve().parent
PROJECT_DIR = API_DIR.parent

load_dotenv(
    PROJECT_DIR / ".env",
    override=True,
    encoding="utf-8-sig",
)

AI_DIR = API_DIR / "ai"
DATABASE_URL = os.environ["DATABASE_URL"]