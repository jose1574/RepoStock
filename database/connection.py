"""Módulo unificado de conexión a base de datos.

Provee `get_connection()`, `close_connection(conn)` e `init_db()` que delegan
en la implementación concreta según la variable de entorno `DB_ENGINE`.

Soporta:
- sqlite: usa `db_sqlite.py`
- postgres: usa `db.py` (psycopg2)

Uso:
    from database.connection import get_connection
    conn = get_connection()
"""
from __future__ import annotations
import os
from typing import Any

DB_ENGINE = os.environ.get("DB_ENGINE", "postgres").lower()


def _use_sqlite() -> bool:
    return DB_ENGINE in ("sqlite", "sqlite3")


if _use_sqlite():
    import db_sqlite as _backend
else:
    import db as _backend


def get_connection(*args, **kwargs) -> Any:
    """Devuelve una conexión según el backend seleccionado.

    Parámetros se pasan al backend correspondiente (ej: `db_sqlite.get_connection`).
    """
    if _use_sqlite():
        return _backend.get_connection(*args, **kwargs)
    else:
        # En el backend Postgres, la función se llama `get_db_connection`.
        return _backend.get_db_connection()


def close_connection(conn: Any) -> None:
    """Cierra la conexión provista por `get_connection()`.

    Acepta conexiones de sqlite3 o psycopg2.
    """
    try:
        conn.close()
    except Exception:
        pass


def init_db(*args, **kwargs):
    """Inicializa la base de datos si el backend lo soporta (ej. sqlite).

    Para Postgres devuelve None (la creación de esquemas debe gestionarse
    vía migraciones externas).
    """
    if _use_sqlite():
        return _backend.init_db(*args, **kwargs)
    return None


__all__ = ["get_connection", "close_connection", "init_db", "DB_ENGINE"]
