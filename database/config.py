"""Configuración de base de datos centralizada.

Lee variables de entorno (con soporte para .env) y expone `DB_ENGINE` y
`DB_CONFIG` para consumo por otros módulos.
"""
import os
from dotenv import load_dotenv
from pathlib import Path

base_path = Path(__file__).resolve().parent.parent
env_path = base_path / '.env'
if env_path.exists():
	load_dotenv(env_path)

DB_ENGINE = os.environ.get('DB_ENGINE', 'postgres').lower()

DB_CONFIG = {}
if DB_ENGINE in ('postgres', 'postgresql'):
	DB_CONFIG = {
		'host': os.environ.get('DB_HOST', 'localhost'),
		'database': os.environ.get('DB_NAME'),
		'user': os.environ.get('DB_USER', 'postgres'),
		'password': os.environ.get('DB_PASSWORD', ''),
		'port': os.environ.get('DB_PORT', '5432'),
	}
elif DB_ENGINE in ('sqlite', 'sqlite3'):
	DB_CONFIG = {
		'filename': os.environ.get('SQLITE_FILE', 'repostock.db')
	}

__all__ = ['DB_ENGINE', 'DB_CONFIG']
