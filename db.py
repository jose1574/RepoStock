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
    "port": int(os.getenv("DB_PORT", 5432)),
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
    cur.execute(
        "SELECT * FROM users WHERE username = %s AND password = %s",
        (username, password),
    )
    user = cur.fetchone()
    cur.close()
    close_db_connection(conn)
    return user


def get_stores():
    """Obtiene la lista de depositos de la base de datos."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM store")
            rows = cur.fetchall()

            # serializar tipos no nativos de JSON (Decimal, datetime)
            def _serialize_row(r):
                return {
                    k: (
                        float(v)
                        if isinstance(v, decimal.Decimal)
                        else (
                            v.isoformat()
                            if isinstance(v, (datetime.date, datetime.datetime))
                            else v
                        )
                    )
                    for k, v in r.items()
                }

            return [_serialize_row(r) for r in rows]
    finally:
        close_db_connection(conn)


def get_store_by_code(store_code):
    """Obtiene la información de un deposito por su código."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM store WHERE code = %s", (store_code,))
            row = cur.fetchone()
            if row:
                # serializar tipos no nativos de JSON (Decimal, datetime)
                def _serialize_row(r):
                    return {
                        k: (
                            float(v)
                            if isinstance(v, decimal.Decimal)
                            else (
                                v.isoformat()
                                if isinstance(v, (datetime.date, datetime.datetime))
                                else v
                            )
                        )
                        for k, v in r.items()
                    }

                return _serialize_row(row)
            return None
    finally:
        close_db_connection(conn)


def get_store_by_code(store_code):
    """Obtiene la información de un deposito por su código."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM store WHERE code = %s", (store_code,))
            row = cur.fetchone()
            if row:
                # serializar tipos no nativos de JSON (Decimal, datetime)
                def _serialize_row(r):
                    return {
                        k: (
                            float(v)
                            if isinstance(v, decimal.Decimal)
                            else (
                                v.isoformat()
                                if isinstance(v, (datetime.date, datetime.datetime))
                                else v
                            )
                        )
                        for k, v in r.items()
                    }

                return _serialize_row(row)
            return None
    finally:
        close_db_connection(conn)


def search_product(code_product):
    """Busca productos relacionados con un código alterno (other_code).

    Devuelve una lista de dicts con campos del producto.
    """
    sql = """
    SELECT 
    p.code, 
    p.description
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


def search_product_failure(code_product, store_code):
    """Busca productos relacionados con un código alterno (other_code).

    Devuelve una lista de dicts con campos del producto.
    """

    # print('Buscando producto con código:', code_product, 'en deposito:', store_code)
    sql = """
    SELECT 
    p.code, 
    p.description,
    pf.minimal_stock,
    pf.maximum_stock,
    pf.location
    FROM products_codes AS pc
    INNER JOIN products AS p ON pc.main_code = p.code
    INNER JOIN products_failures AS pf ON p.code = pf.product_code
    WHERE pc.other_code = %s
    AND pf.store_code = %s
    ;
    """
    conn = get_db_connection()

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (code_product, store_code))
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        close_db_connection(conn)


def save_product_failure(data):

    # 1. Sentencia SQL de ACTUALIZACIÓN (UPDATE)
    # NOTA: Solo actualizamos los stocks, ya que product_code y store_code
    # son las claves de coincidencia (WHERE) y no deben cambiar.
    sql_update = """
    UPDATE products_failures
    SET 
        minimal_stock = %s,
        maximum_stock = %s,
        location = %s
    WHERE product_code = %s AND store_code = %s;
    """

    # 2. Sentencia SQL de INSERCIÓN (INSERT)
    sql_insert = """
    INSERT INTO products_failures (product_code, store_code, minimal_stock, maximum_stock, location)
    VALUES (%s, %s, %s, %s, %s);
    """

    # Prepara los datos para la ejecución
    update_data = (
        data["minimal_stock"],  # -> SET minimal_stock = %s
        data["maximum_stock"],  # -> SET maximum_stock = %s
        data["location"],  # -> AND store_code = %s
        data["product_code"],  # -> WHERE product_code = %s
        data["store_code"],
    )

    insert_data = (
        data["product_code"],
        data["store_code"],
        data["minimal_stock"],
        data["maximum_stock"],
        data["location"],
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


# consulta sql para devolver los productos para visualizar la recoleccion de products


def get_collection_products(
    stock_store_origin=None, store_code_destination=None, department=None
):
    # Calcula to_transfer = min(stock_store_origin.stock, max(pf.maximum_stock - stock_store_destination.stock, 0))
    sql = """
        SELECT 
        p.code,
        p.description AS product_description,
        u.description AS unit_description,
        d.description AS department_description,
        COALESCE(stock_store_origin.stock, 0) AS stock_store_origin,
        pf.minimal_stock,
        pf.maximum_stock,
        ROUND(COALESCE(stock_store_destination.stock, 0)::numeric, 2) AS stock_store_destination,
        ROUND(
            LEAST(
                COALESCE(stock_store_origin.stock, 0),
                GREATEST(COALESCE(pf.maximum_stock, 0) - COALESCE(stock_store_destination.stock, 0), 0)
            )::numeric,
            2
        ) AS to_transfer
        FROM products_failures AS pf
        LEFT JOIN products AS p ON p.code = pf.product_code
        LEFT JOIN products_units AS pu ON pf.product_code = pu.product_code AND pu.main_unit = true
        LEFT JOIN units AS u ON u.code = pu.unit
        LEFT JOIN products_stock AS stock_store_origin ON (stock_store_origin.product_code = pf.product_code AND stock_store_origin.store = %s)
        LEFT JOIN products_stock AS stock_store_destination ON (stock_store_destination.product_code = pf.product_code AND stock_store_destination.store = %s)
        LEFT JOIN department AS d ON d.code = p.department
        WHERE pf.store_code IN (%s)
        AND COALESCE(stock_store_destination.stock, 0) < COALESCE(pf.minimal_stock, 0)
        AND COALESCE(stock_store_origin.stock, 0) > 0
    """
    params = [stock_store_origin, store_code_destination, store_code_destination]

    if department is not None:
        sql += " AND p.department = %s"
        params.append(department)

    sql += """
    GROUP BY
        p.code,
        p.description,
        u.description,
        d.description,
        stock_store_origin.stock,
        stock_store_destination.stock,
        pf.minimal_stock,
        pf.maximum_stock
    ORDER BY p.code;
    """

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        close_db_connection(conn)


# esta funcion optione un lote de codigos, y devuele todos los productos, correspondientes a una orden de traslado
def get_products_by_codes(codes):
    sql = """
    SELECT 
    *
    FROM products AS p
    WHERE p.code = ANY(%s);
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (codes,))
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        close_db_connection(conn)



def save_transfer_order_in_wait(data, document_no: str = ""):
    print("datos de la orden de traslado: ", data)
    sql_insert_order = """
     SELECT set_inventory_operation(
        null,  -- p_correlative (NULL para que la función genere)
        'TRANSFER',  -- p_operation_type
        '',  -- p_document_no
        %s::date,  -- p_emission_date
        true,  -- p_wait
        'ESTA ES LA DESCRIPCION DEL TRASLADO PARA SER UBICADO',  -- p_description
        '01',  -- p_user_code
        '00',  -- p_station
        '00',  -- p_store
        '00',  -- p_locations
        %s,  -- p_destination_store
        '00',  -- p_destination_location
        '',  -- p_operation_comments
        150,  -- p_total_amount
        150,  -- p_total_net
        15,  -- p_total_tax
       150,  -- p_total
        '02',  -- p_coin_code
        false   -- p_internal_use
    );
    """
    params = (
        data.get("emission_date", datetime.date.today()),
        data.get("destination_store", None),
    )

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql_insert_order, params)
            order_id = cur.fetchone()
        conn.commit()
        return order_id
    except Exception as e:
        print(f"Error al guardar la orden de transferencia: {e}")
        conn.rollback()
        return None
    finally:
        close_db_connection(conn)


def get_correlative_product_unit(product_code):
    sql = """
    SELECT 
    correlative
    FROM products_units AS pu
    WHERE pu.product_code = %s AND pu.main_unit = true;
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (product_code,))
            row = cur.fetchone()
            if row:
                return row[0]
            return None
    finally:
        close_db_connection(conn)


def save_transfer_order_items(order_id, items):
    print("items a guardar en la orden de traslado: ", order_id, items)
    # """
    # Guarda los ítems de una orden de transferencia llamando a la función
    # set_inventory_operation_details en la base de datos. Usa los campos
    # del dict 'item' y aplica valores por defecto cuando falta alguno.
    # """
    sql_insert_item = """
    SELECT set_inventory_operation_details(
        %s::integer,    -- p_main_correlative
        null::integer,  -- p_line (dejar que la función lo genere)
        %s::varchar,    -- p_code_product
        %s::varchar,    -- p_description_product
        %s::varchar,    -- p_referenc
        %s::varchar,    -- p_mark
        %s::varchar,    -- p_model
        %s::double precision, -- p_amount
        %s::varchar,    -- p_store
        %s::varchar,    -- p_locations
        %s::varchar,    -- p_destination_store
        %s::varchar,    -- p_destination_location
        %s::integer,    -- p_unit
        %s::double precision, -- p_conversion_factor
        %s::integer,    -- p_unit_type
        %s::double precision, -- p_unitary_cost
        %s::varchar,    -- p_buy_tax
        %s::double precision, -- p_aliquot
        %s::double precision, -- p_total_cost
        %s::double precision, -- p_total_tax
        %s::double precision, -- p_total
        %s::varchar,    -- p_coin_code
        %s::boolean     -- p_change_price
    );
    """

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            for item in items:
                # Normalizar y mapear keys esperadas por app.py
                product_code = item.get("product_code") or item.get("code")
                description = item.get("description", "")
                referenc = item.get("reference") or item.get("referenc") or None
                mark = item.get("mark") or None
                model = item.get("model") or None
                try:
                    amount = float(item.get("quantity", 0))
                except Exception:
                    amount = 0.0

                store_from = (
                    item.get("from_store")
                    or item.get("store_from")
                    or item.get("store")
                    or "01"
                )
                location_from = (
                    item.get("from_location") or item.get("location_from") or "00"
                )
                store_to = (
                    item.get("to_store")
                    or item.get("store_to")
                    or item.get("destination_store")
                    or "02"
                )
                location_to = item.get("to_location") or item.get("location_to") or "00"

                unit = int(item.get("unit", 1))
                conversion_factor = float(item.get("conversion_factor", 1.0))
                unit_type = int(item.get("unit_type", 1))
                unit_price = float(item.get("unit_price", 0.0))
                buy_tax = item.get("buy_tax", None)
                aliquot = (
                    None if item.get("aliquot") is None else float(item.get("aliquot"))
                )
                total_cost = float(item.get("total_cost", item.get("total_price", 0.0)))
                total_tax = (
                    None
                    if item.get("total_tax") is None
                    else float(item.get("total_tax"))
                )
                total_price = float(item.get("total_price", item.get("total", 0.0)))
                coin_code = item.get("coin_code", "USD")
                change_price = bool(item.get("change_price", False))

                params = (
                    order_id,
                    product_code,
                    description,
                    referenc,
                    mark,
                    model,
                    amount,
                    store_from,
                    location_from,
                    store_to,
                    location_to,
                    unit,
                    conversion_factor,
                    unit_type,
                    unit_price,
                    buy_tax,
                    aliquot,
                    total_cost,
                    total_tax,
                    total_price,
                    coin_code,
                    change_price,
                )
                cur.execute(sql_insert_item, params)
        conn.commit()
    except Exception as e:
        print(f"Error al guardar los ítems de la orden de transferencia: {e}")
        conn.rollback()
        raise
    finally:
        close_db_connection(conn)


def get_store_by_code(store_code):
    """Obtiene la información de un deposito por su código."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM store WHERE code = %s", (store_code,))
            row = cur.fetchone()
            if row:
                # serializar tipos no nativos de JSON (Decimal, datetime)
                def _serialize_row(r):
                    return {
                        k: (
                            float(v)
                            if isinstance(v, decimal.Decimal)
                            else (
                                v.isoformat()
                                if isinstance(v, (datetime.date, datetime.datetime))
                                else v
                            )
                        )
                        for k, v in r.items()
                    }

                return _serialize_row(row)
            return None
    finally:
        close_db_connection(conn)


def get_departments():
    """Obtiene la lista de departamentos de la base de datos."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM department")
            rows = cur.fetchall()

            # serializar tipos no nativos de JSON (Decimal, datetime)
            def _serialize_row(r):
                return {
                    k: (
                        float(v)
                        if isinstance(v, decimal.Decimal)
                        else (
                            v.isoformat()
                            if isinstance(v, (datetime.date, datetime.datetime))
                            else v
                        )
                    )
                    for k, v in r.items()
                }

            return [_serialize_row(r) for r in rows]
    finally:
        close_db_connection(conn)


def get_inventory_operations_by_correlative(
    correlative: int, operation_type: str, wait: bool = True
):
    """Obtiene las operaciones de inventario por su código correlativo y tipo de operación."""
    conn = get_db_connection()

    sql = """
                select * from inventory_operation as io
                where io.correlative = %s
                and io.operation_type = %s
                and io.wait = %s
                """
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (correlative, operation_type, wait))
            rows = cur.fetchall()

            # serializar tipos no nativos de JSON (Decimal, datetime)
            def _serialize_row(r):
                return {
                    k: (
                        float(v)
                        if isinstance(v, decimal.Decimal)
                        else (
                            v.isoformat()
                            if isinstance(v, (datetime.date, datetime.datetime))
                            else v
                        )
                    )
                    for k, v in r.items()
                }

            return [_serialize_row(r) for r in rows]
    finally:
        close_db_connection(conn)


def get_inventory_operations_details_by_correlative(main_correlative: int):
    """Obtiene las operaciones de inventario por su código correlativo y tipo de operación."""
    conn = get_db_connection()

    sql = """
            select * from inventory_operation_details 
            where main_correlative = %s      
        """
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (main_correlative,))
            rows = cur.fetchall()

            # serializar tipos no nativos de JSON (Decimal, datetime)
            def _serialize_row(r):
                return {
                    k: (
                        float(v)
                        if isinstance(v, decimal.Decimal)
                        else (
                            v.isoformat()
                            if isinstance(v, (datetime.date, datetime.datetime))
                            else v
                        )
                    )
                    for k, v in r.items()
                }
            return [_serialize_row(r) for r in rows]
    finally:
        close_db_connection(conn)


# export functions
__all__ = [
    "get_db_connection",
    "close_db_connection",
    "login_user",
    "get_stores",
    "search_product",
    "get_store_by_code",
    "save_product_failure",
    "get_collection_products",
    "save_transfer_order_in_wait",
    "save_transfer_order_items",
    "get_products_by_codes",
    "get_correlative_product_unit",
    "get_store_by_code",
    "get_departments",
    "search_product_failure",
    "get_inventory_operations_by_correlative",
    "get_inventory_operations_details_by_correlative"
]
