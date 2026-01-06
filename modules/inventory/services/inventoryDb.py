from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence
from contextlib import contextmanager

from database import get_connection, close_connection
from modules.inventory.schemas.set_inventory_operation import SetInventoryOperationData


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


# para guardar el header de una operación de inventario


def save_inventory_operation_header(data: SetInventoryOperationData) -> Any:
    with get_db_connection() as conn:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            sql = """
                SELECT set_inventory_operation(
                    %s, %s,  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
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
        finally:
            conn.close(conn)
            
        
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
            cur.execute(sql_products, (store_origin, store_origin, store_destination))
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

__all__ = [
    "save_inventory_operation_header",
    "get_product_s_for_order_collection",
    "get_departments",
    "get_marks",
    "get_stores",
]
