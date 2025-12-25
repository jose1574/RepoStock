"""Paquete `database` - exports de conveniencia.

Importar `get_connection` desde `database.connection` permite usar:
    from database import get_connection
"""
from .connection import get_connection, close_connection, init_db, DB_ENGINE

__all__ = ["get_connection", "close_connection", "init_db", "DB_ENGINE"]
