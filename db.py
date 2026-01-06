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

# Fuerza codificación UTF-8 para el cliente de PostgreSQL (libpq)
os.environ.setdefault("PGCLIENTENCODING", "UTF8")


DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "database": os.environ.get("DB_NAME"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", "root"),
    "port": os.environ.get("DB_PORT", "5432"),
}


def get_db_connection():
    """Establece y retorna una conexión a la base de datos PostgreSQL."""
    try:
        # Asegura codificación del lado del cliente
        conn = psycopg2.connect(**DB_CONFIG, options="-c client_encoding=UTF8")
    except UnicodeDecodeError as e:
        # Mensaje guía: .env o variables con caracteres no-UTF8
        raise Exception(
            "Error de codificación al conectar a PostgreSQL. Revisa que el archivo .env y las variables de entorno "
            "(DB_HOST, DB_NAME, DB_USER, DB_PASSWORD) estén en UTF-8 sin caracteres especiales fuera de rango. "
            "También puedes guardar .env en UTF-8 (sin BOM). Detalle: " + str(e)
        )
    if conn is None:
        raise Exception("No se pudo conectar a la base de datos.")
    return conn


def close_db_connection(conn):
    """Cierra la conexión a la base de datos."""
    if conn:
        conn.close()


def login_user(code: str, password: str):
    """Autentica un usuario por su nombre y contraseña.
    Retorna un dict con los datos del usuario si es válido, o None si no.
    """
    print("esto es lo que recibe la funcion login_user ", code, password)
    conn = get_db_connection()
    sql = """
        SELECT  
        u.code, 
        u.description, 
        u.status
        FROM users AS u
        WHERE u.code = UPPER(%s) AND u.user_password = %s AND u.status = '01'
        LIMIT 1;
    """
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (code, password))
            row = cur.fetchone()
            if not row:
                return None
            rows = [row]
            print("esto es lo que imprime desde db ", rows)

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
            return [_serialize_row(r) for r in rows][0]
    finally:
        close_db_connection(conn)
        

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


def get_coins():
    """Obtiene la lista de monedas desde la tabla coin.

    Retorna una lista de dicts con claves: code, description.
    Serializa tipos Decimal y fechas si aparecen.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT code, description FROM coin")
            rows = cur.fetchall()

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


def search_product_failure(code_product, store_code):
    """Busca un producto por código alterno (other_code) o por código principal,
    devolviendo información desde products y, si existe, los datos de products_failures
    para el depósito indicado. Si no hay registro en products_failures, igualmente
    devuelve el producto con los campos de pf en NULL.
    """

    sql = """
    SELECT DISTINCT
        p.code,
        p.description,
        pf.minimal_stock,
        pf.maximum_stock,
        pf.location
    FROM products AS p
    LEFT JOIN products_codes AS pc
        ON pc.main_code = p.code
    LEFT JOIN products_failures AS pf
        ON pf.product_code = p.code
       AND pf.store_code = %s
    WHERE (
        UPPER(pc.other_code) = UPPER(%s)
        OR UPPER(p.code) = UPPER(%s)
    );
    """
    conn = get_db_connection()

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (store_code, code_product, code_product))
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        close_db_connection(conn)


def search_product(code_product):
    """Busca un producto por código alterno (other_code) y devuelve datos principales.

    Retorna una lista de dicts con las claves:
      - code (código principal)
      - description
      - unit_description (si existe unidad principal)
      - unit_correlative (correlativo de la unidad principal, si existe)
    """

    sql = """
    SELECT 
        p.code, 
        p.description,
        u.description AS unit_description,
        pu.correlative AS unit_correlative,
    FROM products_codes AS pc
    INNER JOIN products AS p ON pc.main_code = p.code
    LEFT JOIN products_units AS pu ON pu.product_code = p.code AND pu.main_unit = true
    LEFT JOIN units AS u ON u.code = pu.unit
    WHERE UPPER(pc.other_code) = UPPER(%s)
    ;
    """
    conn = get_db_connection()

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (code_product,))
            rows = cur.fetchall()
            if rows:
                return [dict(r) for r in rows]
            # Fallback: buscar por código principal directamente en products
            sql_fallback = """
            SELECT 
                p.code,
                p.description,
                u.description AS unit_description,
                pu.correlative AS unit_correlative
            FROM products AS p
            LEFT JOIN products_units AS pu ON pu.product_code = p.code AND pu.main_unit = true
            LEFT JOIN units AS u ON u.code = pu.unit
            WHERE UPPER(p.code) = UPPER(%s)
            ;
            """
            cur.execute(sql_fallback, (code_product,))
            rows2 = cur.fetchall()
            return [dict(r) for r in rows2]
    finally:
        close_db_connection(conn)


def search_products_for_sales():
    """Busca todos los productos disponibles en la base de datos.

    Retorna una lista de dicts con las claves:
      - code (código principal)
      - description
      - unit_description (si existe unidad principal)
      - unit_correlative (correlativo de la unidad principal, si existe)
    """

    sql = """
        SELECT
        p.code,
        p.description,
        p.mark,
        p.model,
        -- Precios (se mantienen sin cambios importantes)
        pu.offer_price * pc.sales_aliquot * 1.16 AS offer_price_01,
        pu.higher_price * 1.16 AS higher_price_01,
        pu.minimum_price * 1.16 AS minimum_price_01,
        
        -- Precios con conversión/impuestos (se mantiene la lógica original)
        -- NOTA: El sub-select es necesario para el convert_value_to_coin
        CASE
            WHEN p.extract_net_from_unit_price_plus_tax THEN
                (SELECT convert_value_to_coin(
                    p.coin,
                    '<P_COIN>',
                    ROUND(CAST((pu.offer_price + (pu.offer_price * t.aliquot / 100)) AS NUMERIC), p.rounding_type),
                    'SALES',
                        TRUE
                    ))
                ELSE
                    (SELECT convert_value_to_coin(
                        p.coin,
                        '<P_COIN>',
                        pu.offer_price + (pu.offer_price * t.aliquot / 100),
                        'SALES',
                        TRUE
                    ))
            END AS offer_price,
            SUM(ps.stock) AS stock            
        FROM products p
        JOIN products_units pu ON (pu.product_code = p.code)
        -- LEFT JOIN es clave para incluir productos sin stock, pero que cumplen las condiciones de WHERE
        LEFT JOIN products_stock ps ON (p.code = ps.product_code)
        JOIN coin pc ON (p.coin = pc.code)
        JOIN taxes t ON (t.code = p.sale_tax)

        WHERE
            pu.main_unit
            AND p.code <> 'SERVGAST'
            AND p.status = '01'
            OR p.product_type = 'S'

        GROUP BY
            p.code,
            pc.code,
            p.description,
            p.mark,
            p.model,
            pu.offer_price,
            offer_price_01,
            higher_price_01,
            minimum_price_01,
            t.aliquot
            
        ORDER BY
            p.description
    """
    conn = get_db_connection()

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
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
    p.mark,
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
        p.mark,
        u.description,
        d.description,
        stock_store_origin.stock,
        stock_store_destination.stock,
        pf.minimal_stock,
        pf.maximum_stock
    ORDER BY stock_store_destination ASC;
    """

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        close_db_connection(conn)


def update_minmax_product_failure(
    store_code: str,
    product_code: str,
    minimal_stock: int | None,
    maximum_stock: int | None,
):
    """Actualiza únicamente los campos minimal_stock y maximum_stock en products_failures.
    Si no existe el registro, lo inserta (location queda NULL por defecto).
    """
    sql_update = """
    UPDATE products_failures
    SET minimal_stock = %s,
        maximum_stock = %s
    WHERE product_code = %s AND store_code = %s
    """
    sql_insert = """
    INSERT INTO products_failures (product_code, store_code, minimal_stock, maximum_stock, location)
    VALUES (%s, %s, %s, %s, NULL)
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                sql_update, (minimal_stock, maximum_stock, product_code, store_code)
            )
            if cur.rowcount == 0:
                cur.execute(
                    sql_insert, (product_code, store_code, minimal_stock, maximum_stock)
                )
        conn.commit()
    except Exception as e:
        print(f"Error al actualizar min/max en products_failures: {e}")
        conn.rollback()
        raise
    finally:
        close_db_connection(conn)


# esta funcion optione un lote de codigos, y devuele todos los productos, correspondientes a una orden de traslado


def update_description_inventory_operations(correlative: int, description: str):
    sql_update = """
    UPDATE inventory_operation
    SET 
        description = %s
    WHERE correlative = %s;
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql_update, (description, correlative))
        conn.commit()
    except Exception as e:
        print(f"Error al actualizar la descripción de la orden de transferencia: {e}")
        conn.rollback()
    finally:
        close_db_connection(conn)


def get_document_no_inventory_operation(correlative: int):
    sql = """
    SELECT 
    correlative, 
    document_no
    FROM inventory_operation AS io
    WHERE io.correlative = %s;
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (correlative,))
            row = cur.fetchone()
            if row:
                # row[1] corresponde a document_no
                return row[1]
            return None
    finally:
        close_db_connection(conn)


def save_transfer_order_in_wait(data, description: str):
    print("datos de la orden de traslado: ", description)
    sql_insert_order = """
     SELECT set_inventory_operation(
        null,  -- p_correlative (NULL para que la función genere)
        'TRANSFER',  -- p_operation_type (literal de texto)
        '',  -- p_document_no
        %s::date,  -- p_emission_date
        true,  -- p_wait
        %s,  -- p_description
        %s,  -- p_user_code
        '00',  -- p_station
        %s,  -- p_store
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
        description,
        data.get("user_code", None),
        data.get("store", None),
        data.get("destination_store", None),
    )

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql_insert_order, params)
            row = cur.fetchone()
            order_id = row[0] if row else None
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

                # Asegurar unidad válida: si viene None, vacío o 0, usar 1 como fallback
                unit_raw = item.get("unit", 1)
                try:
                    unit = int(unit_raw) if unit_raw not in (None, "", 0) else 1
                except Exception:
                    unit = 1
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


def get_inventory_operations_by_correlative(
    correlative: int, operation_type: str, wait: bool = True
):
    """Obtiene las operaciones de inventario por su código correlativo y tipo de operación."""
    conn = get_db_connection()

    sql = """
        SELECT
            io.*,
            u.description as  user_description,
            s_origin.description AS origin_store_description,
            s_destination.description AS destination_store_description
        FROM
            inventory_operation AS io
        LEFT JOIN
            store AS s_origin ON io.store = s_origin.code
        LEFT JOIN
            store AS s_destination ON io.destination_Store = s_destination.code
        LEFT JOIN
            users as u on (u.code = io.user_code )
        WHERE
            io.correlative = %s
            AND io.operation_type = %s
            AND io.wait = %s;
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


# funcion que devuelve todas las operaciones de inventario
def get_inventory_operations(wait: bool = True, operation_type: str = "TRANSFER"):
    """Obtiene todas las operaciones de inventario que están en espera."""
    conn = get_db_connection()

    sql = """
        SELECT
            io.*,
            s_origin.description AS origin_store_description,
            s_destination.description AS destination_store_description
        FROM
            inventory_operation AS io
        LEFT JOIN
            store AS s_origin ON io.store = s_origin.code
        LEFT JOIN
            store AS s_destination ON io.destination_Store = s_destination.code
        WHERE
            io.wait = %s
            AND io.operation_type = %s
        ORDER BY io.document_no DESC;
                """
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (wait, operation_type))
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


# para eliminar operaciones de inventario por su codigo correlativo
def delete_inventory_operation_by_correlative(correlative: int):
    """Elimina una operación de inventario y sus detalles por correlativo.
    Primero elimina los detalles para evitar violaciones de FK y luego el encabezado.
    Tablas involucradas: inventory_operation_details (detalle) e inventory_operation (encabezado).
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Eliminar detalles asociados
            cur.execute(
                "DELETE FROM inventory_operation_details WHERE main_correlative = %s",
                (correlative,),
            )
            # Eliminar encabezado
            cur.execute(
                "DELETE FROM inventory_operation WHERE correlative = %s",
                (correlative,),
            )
        conn.commit()
    except Exception as e:
        print(f"Error al eliminar la operación de inventario: {e}")
        conn.rollback()
        raise
    finally:
        close_db_connection(conn)


def get_inventory_operations_details_by_correlative(
    main_correlative: int, product_failure_store: str = None
):
    """Obtiene las operaciones de inventario por su código correlativo y tipo de operación."""
    conn = get_db_connection()
    print("este es el correlavito que recibo: ", main_correlative)
    # NOTA: Antes se filtraba con "AND pu.main_unit = true" en el WHERE.
    # Eso convertía el LEFT JOIN a products_units en un JOIN efectivo, descartando
    # cualquier línea cuyo "iod.unit" no tenga unidad principal (o esté NULL),
    # provocando que no se devolvieran todas las líneas del correlativo.
    # Se elimina ese filtro para retornar todas las líneas. Si se necesita la unidad
    # principal, se puede validar en aplicación o agregar un CASE.
    sql = """
        SELECT 
            iod.*,
            u.description AS unit_description,
            pf.location
        FROM inventory_operation_details AS iod
        LEFT JOIN products_failures AS pf 
            ON iod.code_product = pf.product_code
           AND pf.store_code = COALESCE(%s, iod.destination_store)
        LEFT JOIN products_units AS pu 
            ON iod.unit = pu.correlative
        LEFT JOIN units AS u 
            ON u.code = pu.unit
        WHERE iod.main_correlative = %s
        ORDER BY pf.location NULLS LAST, iod.line NULLS LAST;
    """
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (product_failure_store, main_correlative))
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


def update_inventory_operation_detail_amount(
    main_correlative: int, code_product: str, amount: float
) -> int:
    """Actualiza la cantidad (amount) de una o varias líneas de detalle por correlativo y código de producto.
    Devuelve el número de filas afectadas. Normaliza el código a mayúsculas en la comparación.
    """
    conn = get_db_connection()
    origin_store = (os.environ.get('DEFAULT_STORE_ORIGIN_CODE') or '01').strip()
    sql = """
        UPDATE inventory_operation_details
        SET amount = %s
        WHERE main_correlative = %s AND UPPER(code_product) = UPPER(%s);
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (amount, main_correlative, code_product))
            affected = cur.rowcount
        conn.commit()
        return affected
    except Exception as e:
        print(f"Error al actualizar cantidad en detalle: {e}")
        conn.rollback()
        raise
    finally:
        close_db_connection(conn)


def update_locations_products_failures(
    store_code: str, product_code: str, location: str
):
    """Actualiza únicamente el campo location en products_failures.
    Si no existe el registro, lo inserta (minimal_stock y maximum_stock quedan NULL por defecto).
    """
    sql_update = """
    UPDATE products_failures
    SET location = %s
    WHERE product_code = %s AND store_code = %s
    """
    sql_insert = """
    INSERT INTO products_failures (product_code, store_code, minimal_stock, maximum_stock, location)
    VALUES (%s, %s, NULL, NULL, %s)
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql_update, (location, product_code, store_code))
            if cur.rowcount == 0:
                cur.execute(sql_insert, (product_code, store_code, location))
        conn.commit()
    except Exception as e:
        print(f"Error al actualizar la ubicación en products_failures: {e}")
        conn.rollback()
        raise
    finally:
        close_db_connection(conn)


# para devolver operaciones de inventario


def delete_inventory_operation_detail(main_correlative: int, code_product: str):
    """Elimina líneas de detalle de una operación por correlativo y código de producto.
    Si hay varias líneas con el mismo producto, elimina todas (comportamiento consistente con update).
    """
    conn = get_db_connection()
    sql = """
        DELETE FROM inventory_operation_details
        WHERE main_correlative = %s AND code_product = %s;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (main_correlative, code_product))
        conn.commit()
    except Exception as e:
        print(f"Error eliminando detalle: {e}")
        conn.rollback()
        raise
    finally:
        close_db_connection(conn)


def update_inventory_operation_type(
    correlative: int, new_operation_type: str, description: str = ""
):
    """Actualiza el campo operation_type de inventory_operation para un correlativo dado."""
    conn = get_db_connection()
    sql = """
        UPDATE inventory_operation
        SET operation_type = %s,
            description = %s
        WHERE correlative = %s;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (new_operation_type, description, correlative))
        conn.commit()
    except Exception as e:
        print(f"Error actualizando operation_type: {e}")
        conn.rollback()
        raise
    finally:
        close_db_connection(conn)


def search_product(code: str):
    """Busca un producto por código alterno (other_code) y devuelve datos principales.

    Retorna una lista de dicts con las claves:
      - code (código principal)
      - description
      - unit_description (si existe unidad principal)
      - unit_correlative (correlativo de la unidad principal, si existe)
    """

    sql = """
    SELECT 
        p.code, 
        p.description,
        u.description AS unit_description,
        pu.correlative AS unit_correlative
    FROM products_codes AS pc
    INNER JOIN products AS p ON pc.main_code = p.code
    LEFT JOIN products_units AS pu ON pu.product_code = p.code AND pu.main_unit = true
    LEFT JOIN units AS u ON u.code = pu.unit
    WHERE UPPER(pc.other_code) = UPPER(%s)
    ;
    """
    conn = get_db_connection()

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (code,))
            rows = cur.fetchall()
            if rows:
                return [dict(r) for r in rows]
            # Fallback: buscar por código principal directamente en products
            sql_fallback = """
            SELECT 
                p.code,
                p.description,
                u.description AS unit_description,
                pu.correlative AS unit_correlative
            FROM products AS p
            LEFT JOIN products_units AS pu ON pu.product_code = p.code AND pu.main_unit = true
            LEFT JOIN units AS u ON u.code = pu.unit
            WHERE UPPER(p.code) = UPPER(%s)
            ;
            """
            cur.execute(sql_fallback, (code,))
            rows2 = cur.fetchall()
            return [dict(r) for r in rows2]
    finally:
        close_db_connection(conn)


# export functions


def get_product_stock(product_code: str, store_code: str) -> float:
    """Obtiene el stock actual para un producto en un depósito específico.
    Devuelve 0.0 si no hay registro.
    """
    conn = get_db_connection()
    sql = """
        SELECT COALESCE(ROUND(stock::numeric, 2), 0)
        FROM products_stock
        WHERE product_code = %s AND store = %s
        LIMIT 1;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (product_code, store_code))
            row = cur.fetchone()
            if row and row[0] is not None:
                try:
                    # Asegurar dos decimales exactos
                    return float(f"{float(row[0]):.2f}")
                except Exception:
                    return float(round(float(row[0]), 2))
            return 0.0
    except Exception as e:
        # Propagar para manejo superior
        raise
    finally:
        close_db_connection(conn)


def get_product_stock_by_store(product_code: str):
    """Obtiene el stock del producto en todos los depósitos.
    Retorna lista de dicts: {store_code, store_description, stock}.
    """
    conn = get_db_connection()
    sql = """
        SELECT s.code AS store_code,
               s.description AS store_description,
               COALESCE(ps.stock, 0) AS stock
        FROM store AS s
        LEFT JOIN products_stock AS ps
               ON ps.store = s.code AND UPPER(ps.product_code) = UPPER(%s)
        ORDER BY s.code
    """
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (product_code,))
            rows = cur.fetchall()
            # normalizar decimales
            result = []
            for r in rows:
                stock_val = r.get("stock")
                try:
                    stock_num = float(stock_val) if stock_val is not None else 0.0
                except Exception:
                    stock_num = 0.0
                result.append(
                    {
                        "store_code": r.get("store_code"),
                        "store_description": r.get("store_description"),
                        "stock": float(f"{stock_num:.2f}"),
                    }
                )
            return result
    finally:
        close_db_connection(conn)


def get_product_by_code_or_other_code(code_product: str):
    """Busca un producto por su código principal o por other_code en products_codes.

    Retorna un dict con los campos:
      - code
      - description
      - unit_description
      - unit_correlative
      - total_stock (suma de stocks en products_stock)

    Retorna None si no se encuentra.
    """

    sql = """
    SELECT
        p.code,
        p.description,
        u.description AS unit_description,
        pu.correlative AS unit_correlative,
        COALESCE(SUM(ps.stock), 0) AS total_stock
    FROM products p
    LEFT JOIN products_codes pc ON pc.main_code = p.code
    LEFT JOIN products_units pu ON pu.product_code = p.code AND pu.main_unit = true
    LEFT JOIN units u ON u.code = pu.unit
    LEFT JOIN products_stock ps ON ps.product_code = p.code
    WHERE UPPER(p.code) = UPPER(%s) OR UPPER(pc.other_code) = UPPER(%s)
    GROUP BY p.code, p.description, u.description, pu.correlative
    LIMIT 1;
    """

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (code_product, code_product))
            row = cur.fetchone()
            if not row:
                return None

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

            product = _serialize_row(row)

            # Obtener unidades disponibles para el producto (incluye la unidad principal y alternas)
            sql_units = """
            SELECT pu.correlative, pu.unit AS unit_code, u.description AS unit_description,
                   pu.conversion_factor, pu.main_unit, pu.offer_price
            FROM products_units pu
            LEFT JOIN units u ON u.code = pu.unit
            WHERE pu.product_code = %s
            ORDER BY pu.main_unit DESC, pu.correlative ASC
            ;
            """
            # Usar el código ya serializado para evitar depender del tipo RealDictRow
            cur.execute(sql_units, (product.get('code'),))
            units_rows = cur.fetchall() or []
            units = []
            for ur in units_rows:
                units.append(
                    {
                        'correlative': ur.get('correlative'),
                        'unit_code': ur.get('unit_code'),
                        'unit_description': ur.get('unit_description'),
                        'conversion_factor': float(ur.get('conversion_factor')) if ur.get('conversion_factor') is not None else None,
                        'main_unit': bool(ur.get('main_unit')) if ur.get('main_unit') is not None else False,
                        'offer_price': float(ur.get('offer_price')) if ur.get('offer_price') is not None else None,
                    }
                )

            product['units'] = units
            return product
    finally:
        close_db_connection(conn)


def get_product_with_all_units(code_product: str):
    """Devuelve el producto buscado por código principal u other_code y todas sus unidades.

    Similar a `get_product_by_code_or_other_code` pero NO filtra las unidades por `main_unit`.
    Retorna dict con keys: code, description, total_stock, main_unit (dict or None), units (list).
    """

    sql = """
    SELECT
        p.code,
        p.description,
        COALESCE(SUM(ps.stock), 0) AS total_stock
    FROM products p
    LEFT JOIN products_codes pc ON pc.main_code = p.code
    LEFT JOIN products_stock ps ON ps.product_code = p.code
    WHERE UPPER(p.code) = UPPER(%s) OR UPPER(pc.other_code) = UPPER(%s)
    GROUP BY p.code, p.description
    LIMIT 1;
    """

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (code_product, code_product))
            row = cur.fetchone()
            if not row:
                return None

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

            product = _serialize_row(row)

            # obtener unidad principal (si existe)
            cur.execute(
                """
                SELECT pu.correlative, pu.unit AS unit_code, u.description AS unit_description,
                       pu.conversion_factor, pu.offer_price
                FROM products_units pu
                LEFT JOIN units u ON u.code = pu.unit
                WHERE pu.product_code = %s AND pu.main_unit = true
                LIMIT 1
                """,
                (product.get("code"),),
            )
            main_row = cur.fetchone()
            main_unit = None
            if main_row:
                main_unit = {
                    "correlative": main_row.get("correlative"),
                    "unit_code": main_row.get("unit_code"),
                    "unit_description": main_row.get("unit_description"),
                    "conversion_factor": float(main_row.get("conversion_factor")) if main_row.get("conversion_factor") is not None else None,
                    "offer_price": float(main_row.get("offer_price")) if main_row.get("offer_price") is not None else None,
                    "main_unit": True,
                }

            # obtener todas las unidades (sin filtrar por main_unit)
            sql_units = """
            SELECT pu.correlative, pu.unit AS unit_code, u.description AS unit_description,
                   pu.conversion_factor, pu.main_unit, pu.offer_price
            FROM products_units pu
            LEFT JOIN units u ON u.code = pu.unit
            WHERE pu.product_code = %s
            ORDER BY pu.main_unit DESC, pu.correlative ASC
            ;
            """
            cur.execute(sql_units, (product.get("code"),))
            units_rows = cur.fetchall() or []
            units = []
            for ur in units_rows:
                units.append(
                    {
                        "correlative": ur.get("correlative"),
                        "unit_code": ur.get("unit_code"),
                        "unit_description": ur.get("unit_description"),
                        "conversion_factor": float(ur.get("conversion_factor")) if ur.get("conversion_factor") is not None else None,
                        "main_unit": bool(ur.get("main_unit")) if ur.get("main_unit") is not None else False,
                        "offer_price": float(ur.get("offer_price")) if ur.get("offer_price") is not None else None,
                    }
                )

            product["main_unit"] = main_unit
            product["units"] = units
            return product
    finally:
        close_db_connection(conn)


def get_product_price_and_unit(product_code: str):
    """Obtiene el precio de oferta (offer_price) y la unidad principal del producto.
    Retorna dict: {offer_price: float|None, unit_description: str|None}.
    """
    conn = get_db_connection()
    sql = """
        SELECT pu.offer_price,
               u.description AS unit_description
        FROM products_units AS pu
        LEFT JOIN units AS u ON u.code = pu.unit
        WHERE pu.product_code = %s AND pu.main_unit = true
        LIMIT 1;
    """
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (product_code,))
            row = cur.fetchone()
            if not row:
                return {"offer_price": None, "unit_description": None}
            op = row.get("offer_price")
            try:
                offer_price = float(f"{float(op):.2f}") if op is not None else None
            except Exception:
                offer_price = float(op) if op is not None else None
            return {
                "offer_price": offer_price,
                "unit_description": row.get("unit_description"),
            }
    finally:
        close_db_connection(conn)


def search_products_with_stock_and_price(query: str, store_code: str = None):
    """Busca productos por código principal, código alterno (other_code) o descripción.
    Si `store_code` es provisto, calcula `total_stock` para ese depósito; si no,
    usa la variable de entorno `DEFAULT_STORE_ORIGIN_CODE` o '01' por defecto.
    Si query está vacío, devuelve todos los productos. Retorna código, descripción,
    stock total (suma en el depósito indicado) y offer_price (unidad principal).
    """
    conn = get_db_connection()
    sql = """
        SELECT 
            p.code AS code,
            p.description AS description,
            COALESCE(s.total_stock, 0) AS total_stock,
            pu.offer_price * 1.16 AS offer_price,
            u.description AS unit_description
        FROM products AS p
        LEFT JOIN products_units AS pu ON pu.product_code = p.code AND pu.main_unit = true
        LEFT JOIN units AS u ON u.code = pu.unit
        LEFT JOIN (
            SELECT product_code, SUM(stock) AS total_stock
            FROM products_stock
            WHERE store = %s
            GROUP BY product_code
        ) AS s ON s.product_code = p.code
        WHERE 
            p.status = '01'
            AND p.product_type = 'T'
            AND (
            %s = ''
            OR p.code ILIKE %s
            OR p.description ILIKE %s
            OR EXISTS (
                SELECT 1 FROM products_codes pc
                WHERE pc.main_code = p.code AND pc.other_code ILIKE %s
            )
            )
        ORDER BY p.code ASC
    """
    # determinar depósito origen: usar parámetro si se pasa, sino la variable de entorno
    origin_store = (store_code and str(store_code).strip()) or (os.environ.get('DEFAULT_STORE_ORIGIN_CODE') or '01').strip()
    q = (query or "").strip()
    like = f"%{q}%" if q != "" else "%"
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (origin_store, q, like, like, like))
            rows = cur.fetchall()
            result = []
            for r in rows:
                # Normalizar números a float con 2 decimales
                ts = r.get("total_stock") or 0
                try:
                    total_stock = float(f"{float(ts):.2f}")
                except Exception:
                    total_stock = float(ts) if ts is not None else 0.0
                op = r.get("offer_price")
                try:
                    offer_price = float(f"{float(op):.2f}") if op is not None else None
                except Exception:
                    offer_price = float(op) if op is not None else None
                result.append(
                    {
                        "code": r.get("code"),
                        "description": r.get("description"),
                        "total_stock": total_stock,
                        "offer_price": offer_price,
                        "unit_description": r.get("unit_description"),
                    }
                )
            return result
    finally:
        close_db_connection(conn)


def insert_product_image(data: dict):
    """Inserta una imagen para un producto en rs_products_images.
    Espera keys: product_code, image_data (bytes), filename, mime_type, size_bytes, is_primary.
    """
    conn = get_db_connection()
    sql = """
        INSERT INTO rs_products_images (product_code, image_data, filename, mime_type, size_bytes, is_primary)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING image_id;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    data.get("product_code"),
                    psycopg2.Binary(data.get("image_data")),
                    data.get("filename"),
                    data.get("mime_type"),
                    data.get("size_bytes"),
                    bool(data.get("is_primary", False)),
                ),
            )
            row = cur.fetchone()
            image_id = row[0] if row else None
        conn.commit()
        return image_id
    except Exception as e:
        conn.rollback()
        raise
    finally:
        close_db_connection(conn)


def get_product_images(product_code: str = None, image_id: int = None):
    """Obtiene imágenes por código de producto o por image_id."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if image_id is not None:
                cur.execute(
                    "SELECT * FROM rs_products_images WHERE image_id = %s", (image_id,)
                )
                rows = cur.fetchall()
            elif product_code:
                cur.execute(
                    "SELECT image_id, product_code, filename, mime_type, size_bytes, is_primary, created_at FROM rs_products_images WHERE product_code = %s ORDER BY is_primary DESC, created_at DESC",
                    (product_code,),
                )
                rows = cur.fetchall()
            else:
                rows = []
            # Serializar
            return [dict(r) for r in rows]
    finally:
        close_db_connection(conn)


def delete_product_image(image_id: int):
    """Elimina una imagen de rs_products_images por su ID."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM rs_products_images WHERE image_id = %s", (image_id,)
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        close_db_connection(conn)


# operaciones de cleintes 

def get_clients():
    """Obtiene todos los clientes activos."""
    conn = get_db_connection()
    sql = """
        select 
        c.*,
        coalesce( (select balance from clients_balance cb where cb.client = c.code order by emission_date desc limit 1 ),0) as balance
        from clients c
        where c.client_classification = 'C'
        order by c.description
    """
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        close_db_connection(conn)


def search_products_with_stock_and_price(query: str = "", limit: int = 50, offset: int = 0, store_code: str = None):
    """Busca productos con stock agregado y precio de oferta.

    Retorna un dict: { 'items': [ {code, description, total_stock, offer_price, unit_description} ], 'total': int }
    Acepta `limit` y `offset` para paginación.
    Si `store_code` se pasa, calcula `total_stock` para ese depósito; si no, usa
    `DEFAULT_STORE_ORIGIN_CODE` o '01'.
    """
    conn = get_db_connection()
    q = (query or "").strip()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            where_clauses = ["p.status = '01'", "p.product_type = 'T'"]
            params = []
            if q:
                # Soportar comodín '*' como separador de tokens que deben aparecer (AND)
                if '*' in q:
                    parts = [p.strip() for p in q.split('*') if p.strip()]
                    for part in parts:
                        like = f"%{part}%"
                        where_clauses.append(
                            "(p.code ILIKE %s OR p.description ILIKE %s OR EXISTS (SELECT 1 FROM products_codes pc WHERE pc.main_code = p.code AND pc.other_code ILIKE %s))"
                        )
                        params.extend([like, like, like])
                else:
                    like = f"%{q}%"
                    where_clauses.append(
                        "(p.code ILIKE %s OR p.description ILIKE %s OR EXISTS (SELECT 1 FROM products_codes pc WHERE pc.main_code = p.code AND pc.other_code ILIKE %s))"
                    )
                    params.extend([like, like, like])

            where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            # Total count
            count_sql = f"SELECT COUNT(*) AS cnt FROM products p {where_sql}"
            cur.execute(count_sql, tuple(params))
            count_row = cur.fetchone()
            total = int(count_row.get("cnt") or 0)

            # Select paginated rows
            origin_store = (store_code and str(store_code).strip()) or (os.environ.get('DEFAULT_STORE_ORIGIN_CODE') or '01').strip()
            select_sql = f"""
            SELECT
                p.code AS code,
                p.description AS description,
                COALESCE(s.total_stock, 0) AS total_stock,
                pu.offer_price AS offer_price,
                u.description AS unit_description
            FROM products p
            LEFT JOIN products_units pu ON pu.product_code = p.code AND pu.main_unit = TRUE
            LEFT JOIN units u ON u.code = pu.unit
            LEFT JOIN (
                SELECT product_code, SUM(stock) AS total_stock FROM products_stock WHERE store = %s GROUP BY product_code
            ) s ON s.product_code = p.code
            """ + where_sql + "\n ORDER BY p.code ASC LIMIT %s OFFSET %s"

            exec_params = tuple(params) + (origin_store, limit, offset)
            cur.execute(select_sql, exec_params)
            rows = cur.fetchall()
            items = [dict(r) for r in rows]
            return {"items": items, "total": total}
    finally:
        close_db_connection(conn)

def get_user_by_code(code: str):
    """Obtiene un usuario por su código."""
    conn = get_db_connection()
    sql = """
        SELECT *
        FROM users
        WHERE code = %s
        LIMIT 1;
    """
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (code,))
            row = cur.fetchone()
            if row:
                return dict(row)
            return None
    finally:
        close_db_connection(conn)

__all__ = [
    "get_db_connection",
    "close_db_connection",
    "login_user",
    "get_stores",
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
    "get_inventory_operations_details_by_correlative",
    "get_document_no_inventory_operation",
    "update_description_inventory_operations",
    "update_minmax_product_failure",
    "update_locations_products_failures",
    "get_inventory_operations",
    "delete_inventory_operation_by_correlative",
    "update_inventory_operation_detail_amount",
    "delete_inventory_operation_detail",
    "search_product",
    "get_product_price_and_unit",
    "update_inventory_operation_type",
    "get_product_stock",
    "get_product_stock_by_store",
    "get_product_by_code_or_other_code",
    "search_products_with_stock_and_price",
    "insert_product_image",
    "get_product_images",
    "delete_product_image",
    "get_clients", 
    "get_user_by_code", 
]


#autenticacion de usuarios
