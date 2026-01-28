from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence
from contextlib import contextmanager

from database import get_connection, close_connection
from modules.inventory.schemas.set_inventory_operation import SetInventoryOperationData
from modules.inventory.schemas.set_inventory_operation_details import SetInventoryOperationDetailsData
from modules.inventory.schemas.products_failures import ProductsFailuresData


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


# crea o actualiza la existencia mínima y máxima de un producto en products_failures
def update_product_failure_params(product_code: str, store_code: str, minimal_stock: int, maximum_stock: int, location: str = None) -> Any:
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = """
            INSERT INTO products_failures(
                product_code, store_code, minimal_stock, maximum_stock, location
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (product_code, store_code)
            DO UPDATE SET
                minimal_stock = EXCLUDED.minimal_stock,
                maximum_stock = EXCLUDED.maximum_stock,
                location = EXCLUDED.location;
        """
        
        params = (
            product_code,
            store_code,
            minimal_stock,
            maximum_stock,
            location
        )
        
        cur.execute(sql, params)
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error updating product failure params: {e}")
        raise e
    finally:
        close_connection(conn)
















# para guardar el header de una operación de inventario
def save_inventory_operation_header(data: SetInventoryOperationData) -> Any:
    with get_db_connection() as conn:
        print("Guardando encabezado de operación de inventario con los siguientes datos:", data)
        try:
            cur = conn.cursor()
            sql = """
                SELECT set_inventory_operation(
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                );
                """
            
            params = (
                data.correlative,
                data.operation_type,
                data.document_no,
                data.emission_date,
                data.wait,
                data.description,
                data.user_code,
                data.station,
                data.store,
                data.locations,
                data.destination_store,
                data.destination_location,
                data.operation_comments,
                data.total_amount,
                data.total_net,
                data.total_tax,
                data.total,
                data.coin_code,
                data.internal_use,
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
            
        
def get_product_s_for_order_collection( store_origin: str, store_destination: str, product_code: Optional[str] = None) -> Sequence[dict[str, Any]]:
    with get_db_connection() as conn:
        print(f"Buscando productos para orden de recolección desde '{store_origin}' hacia '{store_destination}'" + (f" para el producto '{product_code}'" if product_code else ""))
        cur = conn.cursor()
        sql_products = """
            SELECT 
                p.code,
                p.description,
                u.code as unit_code,
                u.description as unit_description, -- Agregada coma y 'as' por claridad
                m.code as mark_code,
                m.description as mark_description,
                d.code as department_code,
                d.description as department_description,
                COALESCE(SUM(ps_org.stock), 0) as stock_store_origin,
                COALESCE(SUM(ps_dst.stock), 0) as stock_store_destination,
                pf.minimal_stock,
                pf.maximum_stock
            FROM products AS p
            LEFT JOIN department as d on p.department = d.code  
            LEFT JOIN products_failures AS pf ON pf.product_code = p.code AND pf.store_code = %s
            LEFT JOIN products_units pu ON p.code = pu.product_code AND pu.main_unit = true
            LEFT JOIN units u ON pu.unit = u.code 
            LEFT JOIN products_stock ps_org ON ps_org.product_code = p.code AND ps_org.store = %s
            LEFT JOIN products_stock ps_dst ON ps_dst.product_code = p.code AND ps_dst.store = %s
            LEFT JOIN marks m ON m.code = p.mark 
            WHERE p.status = '01'
            GROUP BY 
                p.code, 
                p.description,
                u.code,
                u.description,
                m.code,
                m.description,
                d.code,
                d.description,
                pf.minimal_stock,
                pf.maximum_stock
            HAVING 
                COALESCE(SUM(ps_dst.stock), 0) < COALESCE(pf.minimal_stock, 0)
                AND COALESCE(SUM(ps_org.stock), 0) > 0
            ORDER BY p.code;
        """
        sql_one_product = """
              SELECT 
                p.code,
                p.description,
                u.code as unit_code,
                u.description as unit_description, -- Agregada coma y 'as' por claridad
                m.code as mark_code,
                m.description as mark_description,
                d.code as department_code,
                d.description as department_description,
                COALESCE(SUM(ps_org.stock), 0) as stock_store_origin,
                COALESCE(SUM(ps_dst.stock), 0) as stock_store_destination,
                pf.minimal_stock,
                pf.maximum_stock
            FROM products AS p
            LEFT JOIN department as d on p.department = d.code  
            LEFT JOIN products_failures AS pf ON pf.product_code = p.code AND pf.store_code = %s
            LEFT JOIN products_units pu ON p.code = pu.product_code AND pu.main_unit = true
            LEFT JOIN units u ON pu.unit = u.code 
            LEFT JOIN products_stock ps_org ON ps_org.product_code = p.code AND ps_org.store = %s
            LEFT JOIN products_stock ps_dst ON ps_dst.product_code = p.code AND ps_dst.store = %s
            LEFT JOIN marks m ON m.code = p.mark 
            WHERE p.status = '01'
            AND p.code = %s
            GROUP BY 
                p.code, 
                p.description,
                u.code,
                u.description,
                m.code,
                m.description,
                d.code,
                d.description,
                pf.minimal_stock,
                pf.maximum_stock
            HAVING 
                COALESCE(SUM(ps_dst.stock), 0) < COALESCE(pf.minimal_stock, 0)
                AND COALESCE(SUM(ps_org.stock), 0) > 0
            ORDER BY p.code;
        """
        if product_code:
            cur.execute(sql_one_product, (store_origin, store_origin, store_destination, product_code))
        else:
            cur.execute(sql_products, (store_destination, store_origin, store_destination))
        columns = [desc[0] for desc in cur.description]
        products = [dict(zip(columns, row)) for row in cur.fetchall()]
        print(f"Productos encontrados: {len(products)}")
        return products

def get_departments() -> Iterable[dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql_departments = """
            SELECT 
            * 
            FROM department as d
        """
        cur.execute(sql_departments)
        columns = [desc[0] for desc in cur.description]
        departments = [dict(zip(columns, row)) for row in cur.fetchall()]
        return departments
    except Exception as e:
        print(f"Error al Buscar Departamentos: {e}")
        return []
    finally:
        close_connection(conn)

#obtiene una lista de productos por códigos
def get_products_by_codes(product_codes: list[str]) -> Iterable[dict[str, Any]]:
    if not product_codes:
        return []
    
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = """
            SELECT 
            p.code,
            p.description,
            p.referenc,
            p.mark,
            p.model,
            pu.correlative as unit_correlative,
            pu.conversion_factor,
            pu.unit_type,
            pu.unitary_cost,
            p.buy_tax,
            p.aliquot,
            p.coin
            FROM products AS p
            LEFT JOIN department as d on p.department = d.code  
            LEFT JOIN products_units pu ON p.code = pu.product_code AND pu.main_unit = true
            LEFT JOIN units u ON pu.unit = u.code 
            LEFT JOIN marks m ON m.code = p.mark 
            WHERE p.code = ANY(%s)
        """
        cur.execute(sql, (product_codes,))
        columns = [desc[0] for desc in cur.description]
        products = [dict(zip(columns, row)) for row in cur.fetchall()]
        return products
    except Exception as e:
        print(f"Error al Buscar Productos por Códigos: {e}")
        return []
    finally:
        close_connection(conn)
    

def get_marks() -> Iterable[dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql_marks = """
            SELECT 
            * 
            FROM marks as m
        """
        cur.execute(sql_marks)
        columns = [desc[0] for desc in cur.description]
        marks = [dict(zip(columns, row)) for row in cur.fetchall()]
        return marks
    except Exception as e:
        print(f"Error al Buscar Marcas: {e}")
        return []
    finally:
        close_connection(conn)

def get_stores() -> Iterable[dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql_stores = """
            SELECT 
            * 
            FROM store as s
        """
        cur.execute(sql_stores)
        columns = [desc[0] for desc in cur.description]
        stores = [dict(zip(columns, row)) for row in cur.fetchall()]
        return stores
    except Exception as e:
        print(f"Error al Buscar Tiendas: {e}")
        return []
    finally:
        close_connection(conn)

def get_coins():
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql_coins = """
            SELECT 
            * 
            FROM coin as c
        """
        cur.execute(sql_coins)
        columns = [desc[0] for desc in cur.description]
        coins = [dict(zip(columns, row)) for row in cur.fetchall()]
        return coins
    except Exception as e:
        print(f"Error al Buscar Monedas: {e}")
        return []
    finally:
        close_connection(conn)


# obtiene moneda por defecto
def get_default_coin() -> str:    
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = "select system_value from system_properties where code = 65"
        cur.execute(sql)
        row = cur.fetchone()

        if row and row[0]:
            return row[0]  # Asumiendo que el código de moneda está en la primera columna
        return "02"  # Retorna '02' como moneda por defecto si no se encuentra ninguna

    except Exception as e:
        print(f"Error fetching default coin: {e}")
        return "02"
    finally:
        close_connection(conn)




def save_inventory_operation_details(details: list[SetInventoryOperationDetailsData]) -> None:
    if not details:
        return

    with get_db_connection() as conn:
        try:
            print(f"Guardando {len(details)} detalles de operación de inventario.")
            cur = conn.cursor()
            sql = """
                SELECT set_inventory_operation_details(
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                    %s, %s, %s
                );
            """
            
            for d in details:
                params = (
                    d.main_correlative,
                    d.line, 
                    d.code_product,
                    d.description_product,
                    d.referenc,
                    d.mark,
                    d.model,
                    d.amount,
                    d.store,
                    d.locations,
                    d.destination_store,
                    d.destination_location,
                    d.unit,
                    d.conversion_factor,
                    d.unit_type,
                    d.unitary_cost,
                    d.buy_tax,
                    d.aliquot,
                    d.total_cost,
                    d.total_tax,
                    d.total,
                    d.coin_code,
                    d.change_price
                )
                cur.execute(sql, params)
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e

def get_products_by_codes(codes):
    conn = get_connection()
    try:
        sql = """
        SELECT 
        p.*,
        pu.correlative as unit_correlative,
        pu.conversion_factor
        FROM products AS p
        left join products_units pu on pu.product_code = p.code and pu.main_unit = true
        WHERE p.code = ANY(%s);
        """
        cur = conn.cursor(cursor_factory=None)
        cur.execute(sql, (codes,))
        columns = [desc[0] for desc in cur.description]
        products = [dict(zip(columns, row)) for row in cur.fetchall()]
        return products
    except Exception as e:
        print(f"Error al Buscar Productos por Códigos: {e}")
        return []
    finally:
        close_connection(conn)


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
        close_connection(conn)


__all__ = [
    "save_inventory_operation_header",
    "get_product_s_for_order_collection",
    "get_departments",
    "get_marks",
    "get_stores",
    "get_coins",
    "get_default_coin",
    "save_inventory_operation_details",
    "get_products_by_codes",
    "get_products_by_codes",
]
