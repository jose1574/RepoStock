"""Acceso a base de datos para el módulo de compras.

Este archivo importa la API unificada desde el paquete `database`.
Provee un context manager `get_db_connection()` y un helper `execute_query()`
para facilitar consultas posteriores en este módulo.
"""

from __future__ import annotations
from contextlib import contextmanager
from typing import Any, Iterable, Optional

from database import get_connection, close_connection
from modules.shopping.services.schemas.product_codes import ProductCodes
from modules.shopping.services.schemas.product_units import ProductUnits
from .schemas.set_shopping_operation import SetShoppingOperationData
from .schemas.set_shopping_operation_details import SetShoppingOperationDetailData
from .schemas.provider import Provider
from .schemas.product import Product


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
        print("Saving shopping operation detail with data:", data)
        params = (
            data.main_correlative,
            data.line,
            data.code_product,
            data.description_product,
            data.referenc,
            data.mark,
            data.model,
            data.amount,
            data.store,
            data.locations,
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
            data.coin_code,
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


def create_product(product: Product) -> str:
    """
    Crea o actualiza un producto en la base de datos usando la función set_product.
    Retorna el código del producto.
    """
    print(f"--- DEBUG DB: Intentando crear producto: {product.code} ---")
    
    # Validaciones básicas
    if not product.code:
        raise ValueError("El código del producto es obligatorio")
    if not product.description:
        raise ValueError("La descripción del producto es obligatoria")

    conn = get_connection()
    try:
        cur = conn.cursor()
        # Llamada a la función almacenada set_product
        # El orden de los parámetros debe coincidir con la definición de la función en la BD
        params = (
            product.code,
            product.description,
            product.short_name,
            product.mark,
            product.model,
            product.referenc,
            product.department,
            product.days_warranty,
            product.sale_tax,
            product.buy_tax,
            product.rounding_type,
            product.costing_type,
            product.discount,
            product.max_discount,
            product.minimal_sale,
            product.maximal_sale,
            product.status,
            product.origin,
            product.take_department_utility,
            product.allow_decimal,
            product.edit_name,
            product.sale_price,
            product.product_type,
            product.technician,
            product.request_technician,
            product.serialized,
            product.request_details,
            product.request_amount,
            product.coin,
            product.allow_negative_stock,
            product.use_scale,
            product.add_unit_description,
            product.use_lots,
            product.lots_order,
            product.minimal_stock,
            product.notify_minimal_stock,
            product.size,
            product.color,
            product.extract_net_from_unit_cost_plus_tax,
            product.extract_net_from_unit_price_plus_tax,
            product.maximum_stock,
            product.action
        )
        
        # print(f"--- DEBUG DB: Parámetros para set_product: {params}") # Descomentar si se necesita ver todos los params
        
        cur.callproc('set_product', params)
        conn.commit()
        print(f"--- DEBUG DB: Producto {product.code} creado/actualizado exitosamente ---")
        return product.code
    except Exception as e:
        conn.rollback()
        print(f"--- ERROR DB: Error al crear producto {product.code}: {e}")
        import traceback
        traceback.print_exc()
        raise e
    finally:
        close_connection(conn)

#crea product_units
def create_product_units(product_units: ProductUnits) -> None:
    """
    Crea o actualiza las unidades de un producto en la base de datos usando la función set_product_units.
    """
    print(f"--- DEBUG DB: Intentando crear unidad de producto: {product_units.producto_codigo} - {product_units.unit} ---")
    
    # Validaciones básicas
    if not product_units.producto_codigo:
        raise ValueError("El código del producto es obligatorio")
    if not product_units.unit:
        raise ValueError("La unidad es obligatoria")

    conn = get_connection()
    try:
        cur = conn.cursor()
        # Llamada a la función almacenada set_product_units
        params = (
            product_units.correlative,
            product_units.unit,
            product_units.producto_codigo,
            product_units.main_unit,
            product_units.conversion_factor,
            product_units.unit_type,
            product_units.show_in_screen,
            product_units.is_for_buy,
            product_units.is_for_sale,
            product_units.unitary_cost,
            product_units.calculated_cost,
            product_units.average_cost,
            product_units.perc_waste_cost,
            product_units.perc_handling_cost,
            product_units.perc_operating_cost,
            product_units.perc_additional_cost,
            product_units.maximum_price,
            product_units.offer_price,
            product_units.higher_price,
            product_units.minimum_price,
            product_units.perc_maximum_price,
            product_units.perc_offer_price,
            product_units.perc_higher_price,
            product_units.perc_minimum_price,
            product_units.perc_freight_cost,
            product_units.perc_discount_provider,
            product_units.lenght,
            product_units.height,
            product_units.width,
            product_units.weight,
            product_units.capacitance
        )
        
        cur.callproc('set_products_units', params)
        conn.commit()
        print(f"--- DEBUG DB: Unidad de producto {product_units.producto_codigo} - {product_units.unit} creada/actualizada exitosamente ---")
    except Exception as e:
        conn.rollback()
        print(f"--- ERROR DB: Error al crear unidad de producto {product_units.producto_codigo} - {product_units.unit}: {e}")
        import traceback
        traceback.print_exc()
        raise e
    finally:
        close_connection(conn)

#crea product_codes
def create_product_codes(product_codes: ProductCodes) -> None:
    """
    Crea o actualiza los códigos alternos de un producto en la base de datos usando la función set_product_codes.
    """
    print(f"--- DEBUG DB: Intentando crear código alterno de producto: {product_codes.main_code} - {product_codes.other_code} ---")
    
    # Validaciones básicas
    if not product_codes.main_code:
        raise ValueError("El código principal del producto es obligatorio")
    if not product_codes.other_code:
        raise ValueError("El código alterno es obligatorio")

    conn = get_connection()
    try:
        cur = conn.cursor()
        # Llamada a la función almacenada set_product_codes
        params = (
            product_codes.main_code,
            product_codes.other_code,
            product_codes.code_type
        )
        
        cur.callproc('set_products_codes', params)
        conn.commit()
        print(f"--- DEBUG DB: Código alterno de producto {product_codes.main_code} - {product_codes.other_code} creado/actualizado exitosamente ---")
    except Exception as e:
        conn.rollback()
        print(f"--- ERROR DB: Error al crear código alterno de producto {product_codes.main_code} - {product_codes.other_code}: {e}")
        import traceback
        traceback.print_exc()
        raise e
    finally:
        close_connection(conn)

#obtiene moneda por defecto para productos

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

def get_products_history_by_provider(provider_code: str) -> list[dict]:
    """
    Obtiene la lista de productos comprados a un proveedor con su información detallada.
    Optimizado para realizar consultas en lote y evitar N+1 queries.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        p_code = str(provider_code).strip()

        # 1. Obtener productos base (solo la última compra por producto)
        sql_products_provider = """
            SELECT
                p.description as product_description,
                p.code as product_code,
                p.mark as product_mark,
                p.department as product_department,
                d.description as department_description,
                pv.product_code,
                pv.unitary_cost as product_provider_unitary_cost,
                to_char(pv.emission_date, 'DD-MM-YYYY') as product_provider_emission_date,
                pv.amount as product_provider_amount,
                pv.coin_code as product_provider_coin,
                pv.document_no as product_provider_document_no
            FROM (
                SELECT 
                    *,
                    ROW_NUMBER() OVER (PARTITION BY product_code ORDER BY emission_date DESC) as rn
                FROM products_provider
                WHERE provider_code = %s
            ) as pv
            LEFT JOIN products as p ON (p.code = pv.product_code)
            LEFT JOIN department as d ON (d.code = p.department)
            WHERE pv.rn = 1
            AND p.status = '01'
            ORDER BY p.code
        """

        cur.execute(sql_products_provider, (p_code,))
        rows = cur.fetchall()
        
        if not rows:
            return []

        colnames = [desc[0] for desc in cur.description]
        products_provider_list = [dict(zip(colnames, row)) for row in rows]
        
        # Obtener lista de códigos para consultas en lote
        product_codes = [p['product_code'] for p in products_provider_list if p.get('product_code')]
        
        if not product_codes:
            return products_provider_list

        product_codes_tuple = tuple(product_codes)

        # 2. Consultas en lote (Bulk queries)
        
        # Stocks
        sql_stocks = """
            SELECT * FROM products_stock WHERE product_code IN %s
        """
        cur.execute(sql_stocks, (product_codes_tuple,))
        stock_rows = cur.fetchall()
        stock_cols = [desc[0] for desc in cur.description]
        
        stocks_by_code = {}
        for row in stock_rows:
            d = dict(zip(stock_cols, row))
            p_code_val = d.get('product_code')
            if p_code_val:
                if p_code_val not in stocks_by_code:
                    stocks_by_code[p_code_val] = []
                stocks_by_code[p_code_val].append(d)

        # Units
        sql_units = """
            SELECT 
            pu.*,
            u.description as unit_description
            FROM products_units pu
            LEFT JOIN units u ON pu.unit = u.code
            WHERE pu.product_code IN %s
        """
        
        cur.execute(sql_units, (product_codes_tuple,))
        unit_rows = cur.fetchall()
        unit_cols = [desc[0] for desc in cur.description]
        
        units_by_code = {}
        for row in unit_rows:
            d = dict(zip(unit_cols, row))
            p_code_val = d.get('product_code')
            if p_code_val:
                if p_code_val not in units_by_code:
                    units_by_code[p_code_val] = []
                units_by_code[p_code_val].append(d)

        # Parameters
        sql_params = """
            SELECT 
            *
            FROM products_failures
            WHERE product_code IN %s
        """
        cur.execute(sql_params, (product_codes_tuple,))
        param_rows = cur.fetchall()
        param_cols = [desc[0] for desc in cur.description]
        
        params_by_code = {}
        for row in param_rows:
            d = dict(zip(param_cols, row))
            p_code_val = d.get('product_code')
            if p_code_val:
                if p_code_val not in params_by_code:
                    params_by_code[p_code_val] = []
                params_by_code[p_code_val].append(d)

          # devuelve las compras relacionadas al producto con otros proveedores
        sql_product_in_order = """
            select 
            pp.product_code,
            so.document_no,
            so.emission_date,
            so.provider_code,
            so.provider_name,
            pp.amount,
            pp.unitary_cost
            from shopping_operation as so
            left join products_provider as pp on (pp.document_no = so.document_no )
            where so.operation_type = 'ORDER'
            and pp.product_code IN %s
            order by so.document_no desc
            """
        cur.execute(sql_product_in_order, (product_codes_tuple,))
        order_rows = cur.fetchall()
        order_cols = [desc[0] for desc in cur.description]

        product_in_order = {}
        for row in order_rows: 
            d = dict(zip(order_cols, row))
            p_code_val = d.get('product_code')
            if p_code_val:
                if p_code_val not in product_in_order:
                    product_in_order[p_code_val] = []
                product_in_order[p_code_val].append(d)

        # 3. Asignar detalles a cada producto
        for product in products_provider_list:
            code = product.get('product_code')
            product['stocks'] = stocks_by_code.get(code, [])
            product['units'] = units_by_code.get(code, [])
            product['parameters'] = params_by_code.get(code, [])
            product['product_in_order'] = product_in_order.get(code, [])

        

      





        return products_provider_list

    except Exception as e:
        print(f"Error fetching products history for provider {provider_code}: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        close_connection(conn)





def get_stores() -> list[dict]:
    """Obtiene la lista de tiendas disponibles."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = "SELECT * FROM store ORDER BY code;"
        cur.execute(sql)
        rows = cur.fetchall()

        # Get column names
        colnames = [desc[0] for desc in cur.description]
        stores = [dict(zip(colnames, row)) for row in rows]
        
        return stores

    except Exception as e:
        print(f"Error fetching stores: {e}")
        return []
    finally:
        close_connection(conn)
         


def get_products_history_by_product_code(product_code: str) -> Optional[dict]:
    """
    Devuelve un único producto identificado por su código (o código alterno),
    con el mismo shape que `get_products_history_by_provider`:
    - Campos base del producto y departamento
    - Última compra (product_provider_*): unitary_cost, emission_date, amount, coin, document_no
    - stocks, units, parameters
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        # Normalizar y resolver código principal si viene un código alterno
        input_code = str(product_code).strip()
        sql_resolve_main = """
            SELECT main_code FROM products_codes WHERE other_code = %s LIMIT 1
        """
        cur.execute(sql_resolve_main, (input_code,))
        row_main = cur.fetchone()
        main_code = row_main[0] if row_main and row_main[0] else input_code

        # Datos base del producto
        sql_product = """
            SELECT 
                p.description AS product_description,
                p.code AS product_code,
                p.mark AS product_mark,
                p.department AS product_department,
                d.description AS department_description
            FROM products p
            LEFT JOIN department d ON d.code = p.department
            WHERE p.code = %s
        """
        cur.execute(sql_product, (main_code,))
        base_row = cur.fetchone()
        if not base_row:
            return None
        base_cols = [desc[0] for desc in cur.description]
        product_info = dict(zip(base_cols, base_row))

        # Última compra registrada para el producto (misma convención de nombres)
        sql_last_purchase = """
            SELECT 
                pv.unitary_cost AS product_provider_unitary_cost,
                to_char(pv.emission_date, 'DD-MM-YYYY') AS product_provider_emission_date,
                pv.amount AS product_provider_amount,
                pv.coin_code AS product_provider_coin,
                pv.document_no AS product_provider_document_no
            FROM products_provider pv
            WHERE pv.product_code = %s
            ORDER BY pv.emission_date DESC
            LIMIT 1
        """

        

        cur.execute(sql_last_purchase, (main_code,))
        last_purchase_row = cur.fetchone()
        if last_purchase_row:
            last_cols = [desc[0] for desc in cur.description]
            product_info.update(dict(zip(last_cols, last_purchase_row)))
        # Stock por tienda
        sql_stocks = """
            SELECT 
                ps.product_code,
                ps.store,
                ps.stock,
                s.description AS store_description
            FROM products_stock ps
            LEFT JOIN store s ON s.code = ps.store
            WHERE ps.product_code = %s
        """
        cur.execute(sql_stocks, (main_code,))
        stock_rows = cur.fetchall()
        stock_cols = [desc[0] for desc in cur.description]
        product_info["stocks"] = [dict(zip(stock_cols, r)) for r in stock_rows]    


        # Unidades configuradas
        sql_units = """
            SELECT 
                pu.*, 
                u.description AS unit_description
            FROM products_units pu
            LEFT JOIN units u ON u.code = pu.unit
            WHERE pu.product_code = %s
        """
        cur.execute(sql_units, (main_code,))
        unit_rows = cur.fetchall()
        unit_cols = [desc[0] for desc in cur.description]
        product_info["units"] = [dict(zip(unit_cols, r)) for r in unit_rows]

        # Parámetros / fallas
        sql_params = """
            SELECT *
            FROM products_failures
            WHERE product_code = %s
        """
        cur.execute(sql_params, (main_code,))
        param_rows = cur.fetchall()
        param_cols = [desc[0] for desc in cur.description]
        product_info["parameters"] = [dict(zip(param_cols, r)) for r in param_rows]

        return product_info

    except Exception as e:
        print(f"Error fetching product history for product {product_code}: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        close_connection(conn)

# devuelve una lista de productos
def get_products_by_codes_list(product_codes: list[str]) -> list[dict]:
    """Obtiene detalles completos de una lista de productos por sus códigos."""
    if not product_codes:
        return []

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

        # Construir la consulta con IN y los placeholders necesarios
        placeholders = ','.join(['%s'] * len(product_codes))
        sql = f"""
            select 
            p.*
            from products as p 
            where p.code IN ({placeholders})
            """
        cur.execute(sql, tuple(product_codes))
        rows = cur.fetchall()

        # Convert to dicts if necessary
        if rows and isinstance(rows[0], tuple):
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in rows]

        return rows
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
    "create_product",
    "get_products_history_by_provider",
    "get_products_history_by_product_code",
    "get_stores",
    "get_product_in_order_by_code",
    "get_products_by_codes_list",
]

