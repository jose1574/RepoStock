## este archivo va contener todas las funciones que se encargan de la base de datos
import os
import psycopg2
import psycopg2.extras
import decimal
import datetime
from dotenv import load_dotenv
base_path = os.path.abspath(os.path.dirname(__file__))
env_path = os.path.join(base_path, ".env")
load_dotenv(env_path)



DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "mi_base"),
    "user": os.getenv("DB_USER", "usuario"),
    "password": os.getenv("DB_PASSWORD", ""),
    "port": int(os.getenv("DB_PORT", 5432))
}

def get_db_connection():
    """Establece y retorna una conexión a la base de datos PostgreSQL."""
    conn = psycopg2.connect(**DB_CONFIG)
    if conn is None:
        raise Exception("No se pudo conectar a la base de datos.")
    return conn

def close_db_connection(conn):
    """Cierra la conexión a la base de datos."""
    if conn:
        conn.close()

def login_user(username, password):
    """Verifica las credenciales del usuario y retorna su información si son válidas."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password))
    user = cur.fetchone()
    cur.close()
    close_db_connection(conn)
    return user

def get_stores():
    """Obtiene la lista de depositos de la base de datos."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM store')
            rows = cur.fetchall()
            # serializar tipos no nativos de JSON (Decimal, datetime)
            def _serialize_row(r):
                return {k: (float(v) if isinstance(v, decimal.Decimal) else (v.isoformat() if isinstance(v, (datetime.date, datetime.datetime)) else v)) for k, v in r.items()}
            return [_serialize_row(r) for r in rows]
    finally:
        close_db_connection(conn)

def get_store_by_code(store_code):
    """Obtiene la información de un deposito por su código."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM store WHERE code = %s', (store_code,))
            row = cur.fetchone()
            if row:
                # serializar tipos no nativos de JSON (Decimal, datetime)
                def _serialize_row(r):
                    return {k: (float(v) if isinstance(v, decimal.Decimal) else (v.isoformat() if isinstance(v, (datetime.date, datetime.datetime)) else v)) for k, v in r.items()}
                return _serialize_row(row)
            return None
    finally:
        close_db_connection(conn)

def search_product(code_product):
    """Busca productos relacionados con un código alterno (other_code).

    Devuelve una lista de dicts con campos del producto.
    """
    sql = """
    SELECT p.code, p.description
    FROM products_codes AS pc
    INNER JOIN products AS p ON pc.main_code = p.code
    WHERE pc.other_code = %s;
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (code_product,))
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        close_db_connection(conn)

def save_product_failure(data):

    print('datos recibidos aqui: ', data)

    # 1. Sentencia SQL de ACTUALIZACIÓN (UPDATE)
    # NOTA: Solo actualizamos los stocks, ya que product_code y store_code 
    # son las claves de coincidencia (WHERE) y no deben cambiar.
    sql_update = """
    UPDATE products_failures
    SET 
        minimal_stock = %s,
        maximum_stock = %s
    WHERE product_code = %s AND store_code = %s;
    """
    
    # 2. Sentencia SQL de INSERCIÓN (INSERT)
    sql_insert = """
    INSERT INTO products_failures (product_code, store_code, minimal_stock, maximum_stock)
    VALUES (%s, %s, %s, %s);
    """
    
    # Prepara los datos para la ejecución
    update_data = (
        data['minimal_stock'], # -> SET minimal_stock = %s
        data['maximum_stock'], # -> SET maximum_stock = %s
        data['product_code'],  # -> WHERE product_code = %s
        data['store_code']     # -> AND store_code = %s
    )

    insert_data = (
        data['product_code'],
        data['store_code'],
        data['minimal_stock'],
        data['maximum_stock']
    )
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Intenta actualizar la fila
            cur.execute(sql_update, update_data)
            
            # Obtiene el número de filas actualizadas
            rows_affected = cur.rowcount 
            
            if rows_affected == 0:
                # 2. Si no se actualizó ninguna fila, inserta una nueva
                cur.execute(sql_insert, insert_data)

        conn.commit()
    except Exception as e:
        print(f"Error al guardar product_failure en PG 9.1: {e}")
        conn.rollback() 
    finally:
        close_db_connection(conn)
#export functions
__all__ = ['get_db_connection', 'close_db_connection', 'login_user', 'get_stores', 'search_product', 'get_store_by_code', 'save_product_failure']