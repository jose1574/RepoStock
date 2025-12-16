"""Conexión SQLite para RepoStock.

Este módulo crea (si no existe) la base de datos `repostock.db` en el
directorio del proyecto y proporciona `get_connection()` e `init_db()`.
"""
import sqlite3
from pathlib import Path

DB_FILENAME = 'repostock.db'
DB_PATH = Path(__file__).resolve().parent / DB_FILENAME

def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Devuelve una conexión a la base SQLite indicada (por defecto `repostock.db`)."""
    path = Path(db_path) if db_path else DB_PATH
    conn = sqlite3.connect(str(path), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    # Activar claves foráneas para que las FK funcionen correctamente
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Crea las tablas necesarias si no existen y devuelve la conexión abierta."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    # Tabla users: solo id y descripción (datos reales vendrán de Postgres)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id PRIMARY KEY CHAR(36),
            description TEXT NOT NULL UNIQUE,
            profile_id INTEGER,
            FOREIGN KEY(profile_id) REFERENCES profile(id) ON DELETE SET NULL
        )
        """
    )
    # Migración: asegurar que la tabla `users` termine con el esquema (id, description).
    cur.execute("PRAGMA table_info(users)")
    ucols = [r[1] for r in cur.fetchall()]
    if 'description' not in ucols or set(ucols) != set(['id', 'description']):
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                description TEXT NOT NULL UNIQUE,
                profile_id INTEGER,
                FOREIGN KEY(profile_id) REFERENCES profile(id) ON DELETE SET NULL
            )
            """
        )
        # Intentar copiar description si existe; si no, usar username; si tampoco, usar placeholder
        if 'description' in ucols:
            cur.execute("INSERT OR IGNORE INTO users (id, description) SELECT id, description FROM users")
        elif 'username' in ucols:
            cur.execute("INSERT OR IGNORE INTO users (id, description) SELECT id, username FROM users")
        else:
            cur.execute("SELECT id FROM users")
            for r in cur.fetchall():
                cur.execute("INSERT OR IGNORE INTO users (id, description) VALUES (?, ?)", (r[0], f'user-{r[0]}'))
        cur.execute("ALTER TABLE users RENAME TO users_old")
        cur.execute("ALTER TABLE users RENAME TO users")
        cur.execute("DROP TABLE IF EXISTS users_old")
    # Tabla profile: solo id y descripción
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL UNIQUE
        )
        """
    )
    # Migraciones simples: si la tabla `profile` existía con otro esquema,
    # asegurarnos de que tenga la columna `description`. Si la tabla antigua
    # contenía `user_id` (modelo previo), reconstruimos la tabla para el nuevo
    # esquema y migramos datos básicos (usar display_name si existe).
    cur.execute("PRAGMA table_info(profile)")
    cols = [r[1] for r in cur.fetchall()]
    if 'user_id' in cols:
        # crear tabla temporal con nuevo esquema
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS profile_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL UNIQUE
            )
            """
        )
        # migrar datos: preferir display_name -> user_id
        cur.execute("SELECT id, user_id, display_name FROM profile")
        for row in cur.fetchall():
            old_id = row[0]
            user_id = row[1]
            display_name = row[2] if len(row) > 2 else None
            desc = display_name if display_name else f'user-{user_id}'
            try:
                cur.execute("INSERT OR IGNORE INTO profile_new (description) VALUES (?)", (desc,))
            except Exception:
                pass
        # renombrar tablas
        cur.execute("ALTER TABLE profile RENAME TO profile_old")
        cur.execute("ALTER TABLE profile_new RENAME TO profile")
        cur.execute("DROP TABLE IF EXISTS profile_old")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_profile_description ON profile(description)")
        # Si existía la tabla profile_menus, la recreamos para que sus FK apunten
        # a la nueva tabla `profile` (evita referencias a profile_old).
        cur.execute("DROP TABLE IF EXISTS profile_menus")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS profile_menus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                menu_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(profile_id) REFERENCES profile(id) ON DELETE CASCADE,
                FOREIGN KEY(menu_id) REFERENCES menus(id) ON DELETE CASCADE,
                UNIQUE(profile_id, menu_id)
            )
            """
        )
        # actualizar cols variable
        cur.execute("PRAGMA table_info(profile)")
        cols = [r[1] for r in cur.fetchall()]
    elif 'description' not in cols:
        # Añadir columna (no permite añadir UNIQUE en ALTER TABLE, crear índice aparte)
        cur.execute("ALTER TABLE profile ADD COLUMN description TEXT")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_profile_description ON profile(description)")

    # Tabla menus para definir menús y opciones de la aplicación
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS menus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            url TEXT,
            icon TEXT,
            parent_id INTEGER,
            position INTEGER DEFAULT 0,
            role TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP,
            FOREIGN KEY(parent_id) REFERENCES menus(id) ON DELETE CASCADE
        )
        """
    )
    # Tabla de relación profile <-> menus
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS profile_menus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            menu_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(profile_id) REFERENCES profile(id) ON DELETE CASCADE,
            FOREIGN KEY(menu_id) REFERENCES menus(id) ON DELETE CASCADE,
            UNIQUE(profile_id, menu_id)
        )
        """
    )
    # Tabla de relación user <-> profile (asignación de perfil a usuario)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            profile_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(profile_id) REFERENCES profile(id) ON DELETE CASCADE,
            UNIQUE(user_id)
        )
        """
    )
    # Sembrar menús por defecto (si la tabla está vacía)
    cur.execute("SELECT COUNT(1) as cnt FROM menus")
    cnt = cur.fetchone()[0]
    if cnt == 0:
        defaults = [
            ('home', 'Inicio', 'index', None, 0, None, 1),
            ('operations', 'Operaciones', None, None, 1, None, 1),
            ('manager.documents', 'Administrador de documentos', 'manager.document_manager', None, 2, 'manager', 1),
            ('settings', 'Configuración', 'systems.setup', None, 3, 'admin', 1),
            ('logout', 'Salir', 'logout', None, 99, None, 1),
        ]
        for key, label, url, parent_key, position, role, is_active in defaults:
            cur.execute(
                "INSERT INTO menus (key, label, url, parent_id, position, role, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (key, label, url, None, position, role, is_active)
            )
        # insertar hijos de 'operations'
        cur.execute("SELECT id FROM menus WHERE key = ?", ('operations',))
        op_row = cur.fetchone()
        if op_row:
            op_id = op_row['id'] if isinstance(op_row, sqlite3.Row) else op_row[0]
            children = [
                ('operations.collect_auto', 'Orden de Recolección Automatica', 'inventory.select_store_destination_collection_order', op_id, 1, None, 1),
                ('operations.collect_manual', 'Orden de Recolección Manual', 'inventory.select_store_manual_collection_order', op_id, 2, None, 1),
                ('operations.check_collection', 'Chequeo de Orden de Recolección', 'inventory.check_order_collection', op_id, 3, None, 1),
                ('operations.check_transfer', 'Chequeo de Recepción de Traslados', 'inventory.check_transfer_reception', op_id, 4, None, 1),
                ('operations.params_products', 'Parámetros de Productos', 'inventory.config_param_product_store', op_id, 5, None, 1),
                ('operations.product_location', 'Ubicación de Productos', 'inventory.form_destination_store_for_location', op_id, 6, None, 1),
            ]
            for key, label, url, parent_id, position, role, is_active in children:
                cur.execute(
                    "INSERT INTO menus (key, label, url, parent_id, position, role, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (key, label, url, parent_id, position, role, is_active)
                )
    conn.commit()
    return conn

#asginar perfil a un usuario
def create_profile(description: str) -> int:
    """Crea un perfil (solo descripción) y devuelve su id."""
    print('Creating profile with description:', description)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO profile (description) VALUES (?)", (description,))
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid


def get_profile_by_description(description: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM profile WHERE description = ?", (description,))
    row = cur.fetchone()
    conn.close()
    return row


def create_user(user_id: int, description: str) -> None:
    """Inserta un usuario local mínimo con `id` y `description`.
    El `id` se espera provenga de Postgres cuando se sincronice; aquí permitimos
    crear registros mínimos para pruebas localmente.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO users (id, description) VALUES (?, ?)", (user_id, description))
    conn.commit()
    conn.close()


def get_menus(active_only: bool = True):
    """Devuelve la lista de menús. Si `active_only`, filtra por `is_active`."""
    conn = get_connection()
    cur = conn.cursor()
    if active_only:
        cur.execute("SELECT * FROM menus WHERE is_active = 1 ORDER BY parent_id NULLS FIRST, position, id")
    else:
        cur.execute("SELECT * FROM menus ORDER BY parent_id NULLS FIRST, position, id")
    rows = cur.fetchall()
    conn.close()
    return rows


def assign_menus_to_profile(profile_id: int, menu_ids: list[int]):
    """Asigna una lista de `menu_id` al `profile_id` (sobrescribe asignaciones anteriores)."""
    conn = get_connection()
    cur = conn.cursor()
    # Desactivar temporalmente la comprobación de FK para evitar errores
    # si estamos en medio de una migración interna. Se vuelve a activar
    # al cerrar/commit.
    cur.execute('PRAGMA foreign_keys = OFF')
    cur.execute("DELETE FROM profile_menus WHERE profile_id = ?", (profile_id,))
    for mid in menu_ids:
        cur.execute("INSERT OR IGNORE INTO profile_menus (profile_id, menu_id) VALUES (?, ?)", (profile_id, mid))
    cur.execute('PRAGMA foreign_keys = ON')
    conn.commit()
    conn.close()


def get_menus_by_profile(profile_id: int):
    """Devuelve menúes asignados a un perfil (lista de menu rows)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT m.* FROM menus m
        JOIN profile_menus pm ON pm.menu_id = m.id
        WHERE pm.profile_id = ?
        ORDER BY m.parent_id, m.position, m.id
        """,
        (profile_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def assign_profile_to_user(user_id: int, profile_id: int):
    """Asigna un perfil a un usuario (sobrescribe asignación previa)."""
    conn = get_connection()
    cur = conn.cursor()
    # asegurar que el usuario exista en tabla `users` mínima (no se crean datos de Postgres aquí)
    cur.execute("INSERT OR IGNORE INTO users (id, description) VALUES (?, ?)", (user_id, f'user-{user_id}'))
    cur.execute("DELETE FROM user_profiles WHERE user_id = ?", (user_id,))
    cur.execute("INSERT INTO user_profiles (user_id, profile_id) VALUES (?, ?)", (user_id, profile_id))
    conn.commit()
    conn.close()


def get_profile_by_user(user_id: int):
    """Devuelve el `profile` asignado al `user_id` o None."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT p.* FROM profile p
        JOIN user_profiles up ON up.profile_id = p.id
        WHERE up.user_id = ?
        LIMIT 1
        """,
        (user_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row

if __name__ == '__main__':
    conn = init_db()
    print(f'Base de datos creada/actualizada en: {DB_PATH}')
    conn.close()

__all__ = [
    "get_connection",
    "init_db",
    "create_profile",
    "get_profile_by_description",
    "create_user",
    "get_menus",
    "assign_menus_to_profile",
    "get_menus_by_profile",
]