"""Acceso a base de datos para el módulo de compras.

Este archivo importa la API unificada desde el paquete `database`.
Provee un context manager `get_db_connection()` y un helper `execute_query()`
para facilitar consultas posteriores en este módulo.
"""

from __future__ import annotations
from contextlib import contextmanager
from typing import Any, Iterable, Optional

from database import get_connection, close_connection
from .schemas.set_shopping_operation import SetShoppingOperationData
from .schemas.set_shopping_operation_details import SetShoppingOperationDetailData
from .schemas.provider import Provider


@contextmanager
def get_db_connection():
    """Context manager que provee una conexión y la cierra al finalizar."""
    conn = get_connection()
    try:
        yield conn
    finally:
        try:
            close_connection(conn)
        except Exception:
            pass


def get_shopping_operations(p_initial_date, p_final_date, p_provider=None, p_user=None):
    """Devuelve operaciones de compra llamando la función DB `get_shopping_operation`.

    Parámetros:
    - p_initial_date, p_final_date: fechas (tipo date o string YYYY-MM-DD)
    - p_provider: código de proveedor o None
    - p_user: código de usuario o None

    Retorna una lista de diccionarios (o registros tal como los devuelve el cursor).
    """
    conn = get_connection()
    try:
        # Intentar cursor que devuelva dicts (psycopg2.RealDictCursor) si está disponible
        try:
            import psycopg2.extras as _extras

            cur = conn.cursor(cursor_factory=_extras.RealDictCursor)
        except Exception:
            cur = conn.cursor()

        sql = "SELECT * FROM get_shopping_operation(%s, %s, %s, %s);"
        cur.execute(
            sql, (p_initial_date, p_final_date, p_provider or None, p_user or None)
        )
        rows = cur.fetchall()

        # Si el cursor no devolvió dicts, convertir usando description
        if rows and isinstance(rows[0], tuple):
            cols = [c[0] for c in cur.description] if cur.description else []
            rows = [dict(zip(cols, r)) for r in rows]

        return rows
    finally:
        close_connection(conn)


# Obtener una lista de proveedores
def get_providers() -> list[Provider]:
    """Obtiene la lista de proveedores desde la tabla provider."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = "SELECT * FROM provider ORDER BY code;"
        cur.execute(sql)
        rows = cur.fetchall()

        if not rows:
            return []

        # Get column names
        colnames = [desc[0] for desc in cur.description]

        providers = []
        for row in rows:
            # Create a dictionary from the row
            row_dict = dict(zip(colnames, row))

            try:
                # Filter the dict to pass only known fields to the constructor
                valid_keys = Provider.__annotations__.keys()
                filtered_data = {k: v for k, v in row_dict.items() if k in valid_keys}

                provider = Provider(**filtered_data)
                providers.append(provider)
            except Exception as e:
                print(
                    f"Error mapping provider row {row_dict.get('code', 'unknown')}: {e}"
                )
                continue

        return providers
    except Exception as e:
        print(f"Error fetching providers: {e}")
        return []
    finally:
        close_connection(conn)

# Guardar header de una operación de compra
def save_shopping_operation(data: SetShoppingOperationData) -> int:
    """Guarda una operación de compra llamando a set_shopping_operation.

    Retorna el correlativo de la operación (nuevo o existente).
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        # La función SQL tiene 51 parámetros.
        # El primero es INOUT, pero en la llamada SELECT pasamos el valor de entrada.
        # La función retorna el nuevo correlativo.
        sql = """
            SELECT set_shopping_operation(
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s
            );
        """
        params = (
            data.correlative,
            data.operation_type,
            data.document_no,
            data.control_no,
            data.emission_date,
            data.reception_date,
            data.provider_code,
            data.provider_name,
            data.provider_id,
            data.provider_address,
            data.provider_phone,
            data.credit_days,
            data.expiration_date,
            data.wait,
            data.description,
            data.store or '00',
            data.locations or '00',
            data.user_code or '00',
            data.station or '00',
            data.percent_discount,
            data.discount,
            data.percent_freight,
            data.freight,
            data.freight_tax,
            data.freight_aliquot,
            data.credit,
            data.cash,
            data.operation_comments,
            data.pending,
            data.buyer,
            data.total_amount,
            data.total_net_details,
            data.total_tax_details,
            data.total_details,
            data.total_net,
            data.total_tax,
            data.total,
            data.total_retention_tax,
            data.total_retention_municipal,
            data.total_retention_islr,
            data.total_operation,
            data.retention_tax_prorration,
            data.retention_islr_prorration,
            data.retention_municipal_prorration,
            data.coin_code or '02',
            data.free_tax,
            data.total_exempt,
            data.secondary_coin,
            data.base_igtf,
            data.percent_igtf,
            data.igtf,
        )

        cur.execute(sql, params)
        result = cur.fetchone()
        conn.commit()

        if result:
            return result[0]
        return 0

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        close_connection(conn)


# Guarda el detalle de una operación de compra
def save_shopping_operation_detail(data: SetShoppingOperationDetailData) -> None:
    """Guarda el detalle de una operación de compra llamando a set_shopping_operation_details."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = """
            SELECT set_shopping_operation_details(
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                %s, %s, %s, %s, %s, %s, %s
            );
        """
        params = (
            data.main_correlative,
            data.line,
            data.code_product,
            data.description_product,
            data.referenc,
            data.mark,
            data.model,
            data.amount,
            data.store or '00',
            data.locations or '00',
            data.unit,
            data.conversion_factor,
            data.unit_type,
            data.unitary_cost,
            data.buy_tax,
            data.buy_aliquot,
            data.percent_discount,
            data.discount,
            data.product_type,
            data.total_net_gross,
            data.total_tax_gross,
            data.total_gross,
            data.total_net,
            data.total_tax,
            data.total,
            data.coin_code or '02',
            False # change_price
        )
        cur.execute(sql, params)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        close_connection(conn)



def get_products_for_modal(query, p_coin="02", limit=50, offset=0):
    """Busca productos para el módulo de compras."""
    conn = get_connection()
    try:
        cur = None
        try:
            import psycopg2.extras as _extras

            # Check if conn supports cursor_factory (psycopg2 connection)
            if hasattr(conn, "cursor"):
                cur = conn.cursor(cursor_factory=_extras.RealDictCursor)
        except Exception:
            pass

        if cur is None:
            cur = conn.cursor()

        sql = """
            select 
            p.code,
            p.description,
            p.mark,
            p.model,
            case 
            when p.extract_net_from_unit_cost_plus_tax
            then
            (SELECT convert_value_to_coin(
               p.coin,
                %s,
                round(cast((pu.unitary_cost + (pu.unitary_cost * t.aliquot / 100)) as numeric),p.rounding_type) ,
                'SHOPPING',
                TRUE
            ))  
            else
            (SELECT convert_value_to_coin(
               p.coin,
                %s,
                pu.unitary_cost + (pu.unitary_cost *  t.aliquot / 100) ,
                'SHOPPING',
                TRUE
            )) 
            end as maximum_price,
            coalesce ( sum(ps.stock) ,0) as stock 
            from products p 
            join products_units pu on (pu.product_code = p.code)
            left join products_stock ps on (p.code = ps.product_code)
            join taxes t on (t.code = p.buy_tax)
            where 
            pu.main_unit 
            and p.code<>'SERVGAST'
            and  p.status='01'
            and product_type in ('T','S')
            AND (p.code ILIKE %s OR p.description ILIKE %s)
            group by 
            p.code,
            p.description,
            p.mark,
            p.model,
            pu.unitary_cost,
            t.aliquot,
            p.extract_net_from_unit_cost_plus_tax,
            p.coin,
            p.rounding_type
            order by description
            LIMIT %s OFFSET %s
        """

        # Replace * with % for wildcard search and ensure it's wrapped in % for "contains" behavior
        formatted_query = query.replace("*", "%")
        search_pattern = f"%{formatted_query}%"
        cur.execute(
            sql, (p_coin, p_coin, search_pattern, search_pattern, limit, offset)
        )
        rows = cur.fetchall()

        # Convert to dicts if necessary
        if rows and isinstance(rows[0], tuple):
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in rows]

        return rows
    finally:
        close_connection(conn)


# devuelve un producto por su código
def get_product_by_code(code):
    """Obtiene detalles completos de un producto por su código."""
    conn = get_connection()
    sql = """
    select 
    p.*
    from products as p 
    left join products_codes pc on (pc.main_code = p.code )
    where pc.other_code = %s
    """
    try:
        cur = None
        try:
            import psycopg2.extras as _extras

            # Check if conn supports cursor_factory (psycopg2 connection)
            if hasattr(conn, "cursor"):
                cur = conn.cursor(cursor_factory=_extras.RealDictCursor)
        except Exception:
            pass

        if cur is None:
            cur = conn.cursor()

        cur.execute(sql, (code,))
        row = cur.fetchone()

        if row is None:
            return None

        # Convert to dict if necessary
        if isinstance(row, tuple):
            columns = [desc[0] for desc in cur.description]
            return dict(zip(columns, row))

        return row
    finally:
        close_connection(conn)


def get_product_stock_by_code(code: str) -> list[dict]:
    """Obtiene el stock total de un producto por su código."""
    conn = get_connection()
    try:
        # Intentamos usar RealDictCursor para obtener diccionarios directamente

        sql = """
            SELECT 
                ps.product_code,
                ps.store,
                ps.stock,
                s.description as store_description,
                pf.minimal_stock,
                pf.maximum_stock,
                pf.location
            FROM products_stock AS ps    
            LEFT JOIN products_codes pc ON (pc.main_code = ps.product_code)
            LEFT JOIN store s ON (s.code = ps.store)
            LEFT JOIN products_failures pf ON (pf.product_code = ps.product_code and pf.store_Code = ps.store)
            WHERE pc.other_code =  %s
        """
        try:
            cur = conn.cursor()
            cur.execute(sql, (code,))
            rows = cur.fetchall()
            # Get column names
            colnames = [desc[0] for desc in cur.description]
            stock_info = [dict(zip(colnames, row)) for row in rows]
            return stock_info
        except Exception as e:
            print(f"Error fetching product stock: {e}")
            return []
    finally:
        close_connection(conn)


def get_provider_by_code(code: str) -> Optional[Provider]:
    """Obtiene un proveedor por su código."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = "SELECT * FROM provider WHERE code = %s;"
        cur.execute(sql, (code,))
        row = cur.fetchone()

        if not row:
            return None

        # Get column names
        colnames = [desc[0] for desc in cur.description]
        row_dict = dict(zip(colnames, row))

        try:
            # Filter the dict to pass only known fields to the constructor
            valid_keys = Provider.__annotations__.keys()
            filtered_data = {k: v for k, v in row_dict.items() if k in valid_keys}

            return Provider(**filtered_data)
        except Exception as e:
            print(f"Error mapping provider row {row_dict.get('code', 'unknown')}: {e}")
            return None

    except Exception as e:
        print(f"Error fetching provider: {e}")
        return None
    finally:
        close_connection(conn)


#Obtiene la imagen del producto 
def get_product_image_by_code(code: str) -> Optional[bytes]:
    """Obtiene la imagen de un producto por su código."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = "SELECT image_data FROM rs_products_images WHERE product_code = %s;"
        cur.execute(sql, (code,))
        row = cur.fetchone()

        if row and row[0]:
            return row[0]  # Asumiendo que la imagen está en la primera columna
        return None

    except Exception as e:
        print(f"Error fetching product image: {e}")
        return None
    finally:
        close_connection(conn)

# Obtiene las unidades alternas del producto
def get_product_units_by_code(code: str) -> list[dict]:
    """Obtiene las unidades alternas de un producto por su código."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = """
        SELECT 
            *
        FROM products_units AS pu 
        LEFT JOIN units AS u ON  (pu.unit = u.code )
        WHERE pu.product_code = %s;
        """
        cur.execute(sql, (code,))
        rows = cur.fetchall()

        # Get column names
        colnames = [desc[0] for desc in cur.description]
        units = [dict(zip(colnames, row)) for row in rows]

        return units

    except Exception as e:
        print(f"Error fetching product units: {e}")
        return []
    finally:
        close_connection(conn)

#devuelve monedas 
def get_coins():
    """Obtiene la lista de monedas disponibles."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = "SELECT * FROM coin ORDER BY code;"
        cur.execute(sql)
        rows = cur.fetchall()

        # Get column names
        colnames = [desc[0] for desc in cur.description]
        coins = [dict(zip(colnames, row)) for row in rows]
        
        return coins

    except Exception as e:
        print(f"Error fetching coins: {e}")
        return []
    finally:
        close_connection(conn)


__all__ = [
    "get_db_connection",
    "execute_query",
    "get_shopping_operations",
    "get_products_for_search",
    "get_product_by_code",
    "save_shopping_operation",
    "get_product_stock_by_code",
    "get_provider_by_code",
    "get_providers",
    "get_products_for_modal",
    "get_product_image_by_code",
    "save_shopping_operation_detail",
    "get_product_units_by_code",
    "get_coins",
]
