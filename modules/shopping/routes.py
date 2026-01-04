from flask import Blueprint, render_template, jsonify, request, send_file, session
import io
from datetime import date


from modules.shopping.services.schemas.product import Product
from modules.shopping.services.schemas.product_codes import ProductCodes
from modules.shopping.services.schemas.product_units import ProductUnits
from modules.shopping.services.schemas.set_shopping_operation import SetShoppingOperationData
from modules.shopping.services.schemas.set_shopping_operation_details import SetShoppingOperationDetailData

from modules.shopping.services.shoppingDb import (
    create_product_codes,
    create_product_units,
    get_default_coin,
    get_products_history_by_product_code,
    get_shopping_operations, 
    get_providers, 
    get_products_for_modal,
    get_product_stock_by_code,
    get_provider_by_code,
    get_product_by_code,
    get_product_image_by_code,
    get_product_units_by_code,
    get_stores,
    save_shopping_operation,
    save_shopping_operation_detail,
    get_coins,
    create_product,
    get_products_history_by_provider,
)

shopping_bp = Blueprint('shopping', __name__, template_folder='templates', url_prefix='/shopping') 


@shopping_bp.route('/', methods=['GET'])
def shopping():
    user = session.get('user', {})
    coins = get_coins()
    default_coin = get_default_coin()
    print(f"Default coin: {default_coin}")
    return render_template(
        'shopping.html', 
        user=user, 
        coins=coins, 
        default_coin=default_coin  # Asumimos '02' como moneda predeterminada
        )

#vista de orden de compra automatica
@shopping_bp.route('/auto_order', methods=['GET'])
def auto_order():
    user = session.get('user', {})
    coins = get_coins()
    default_coin = get_default_coin()
    stores = get_stores()
    return render_template(
        'auto_order.html', 
        user=user, 
        coins=coins, 
        default_coin=default_coin,  # Asumimos '02' como moneda predeterminada
        stores=stores
        )


# API para obtener el historial de productos por proveedor
@shopping_bp.route('/api/products/history/<provider_code>', methods=['GET'])
def api_products_history_by_provider(provider_code):
    try:
        print(f"Buscando historial para proveedor: {provider_code}")
        products = get_products_history_by_provider(provider_code)        
        # Procesar fechas para JSON
        for p in products:
            if p.get('last_purchase_date'):
                p['last_purchase_date'] = p['last_purchase_date'].strftime('%Y-%m-%d')
            # Calcular cantidad sugerida (ejemplo simple: max - stock actual)
            # Esto es solo un placeholder, la lógica real puede ser más compleja
            p['suggested_quantity'] = 0 
            
        # --- NUEVO: Guardar en sesión ---
        # Convertimos la lista en un diccionario indexado por código de producto
        # para recuperarlo fácilmente en el guardado.
        products_map = {p['product_code']: p for p in products if 'product_code' in p}
        session['current_auto_order_products'] = products_map
        session.modified = True
        print(f"--- DEBUG: {len(products_map)} productos guardados en sesión ---")
        # --------------------------------

        return jsonify({'ok': True, 'items': products})
    except Exception as e:
        print(f"Error getting product history: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

# API para obtener el historial de productos por código de producto
@shopping_bp.route('/api/products/history_by_code/<product_code>', methods=['GET'])
def api_products_history_by_product_code(product_code):
    try:
        print(f"Buscando historial para producto: {product_code}")
        item = get_products_history_by_product_code(product_code)
        if not item:
            return jsonify({'ok': False, 'error': 'Product history not found'}), 404

        # Convertir Decimal a float
        try:
            from decimal import Decimal
            for k, v in list(item.items()):
                if isinstance(v, Decimal):
                    item[k] = float(v)
        except Exception:
            pass

        return jsonify({'ok': True, 'item': item})
    except Exception as e:
        print(f"Error getting product history by code: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

# API para buscar proveedores
@shopping_bp.route('/api/providers/search', methods=['GET'])
def api_providers_search():
    # Por ahora devolvemos todos, el filtrado se puede hacer en cliente o mejorar la query luego
    providers_objects = get_providers()
    
    # Convertir objetos a diccionarios
    providers = [p.to_dict() for p in providers_objects]

    # Si se quisiera filtrar por query param 'q':
    q = request.args.get('q', '').lower()
    if q and q != '*':
        providers = [
            p for p in providers 
            if (p['provider_code'] and q in p['provider_code'].lower()) or 
               (p['provider_name'] and q in p['provider_name'].lower())
        ]
    
    return jsonify({'ok': True, 'items': providers})


# API para obtener detalles completos de un proveedor por su código
@shopping_bp.route('/api/providers/details/<code>', methods=['GET'])
def api_provider_details(code):
    try:
        provider = get_provider_by_code(code)
        if provider:
            return jsonify({'ok': True, 'provider': provider.to_dict()})
        else:
            return jsonify({'ok': False, 'error': 'Provider not found'}), 404
    except Exception as e:
        print(f"Error getting provider details: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500




# API para buscar productos
@shopping_bp.route('/api/products/search', methods=['GET'])
def api_products_search():
    q = request.args.get('q', '')
    coin = request.args.get('coin', '02')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    
    try:
        products = get_products_for_modal(q, coin, limit, offset)        
        # Convert Decimal to float for JSON serialization
        for p in products:
            if 'maximum_price' in p and p['maximum_price'] is not None:
                p['maximum_price'] = float(p['maximum_price'])
            if 'stock' in p and p['stock'] is not None:
                p['stock'] = float(p['stock'])
                
        return jsonify({'ok': True, 'items': products})
    except Exception as e:
        print(f"Error searching products: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


# API para devolver stock de productos
@shopping_bp.route('/api/products/details/<code>', methods=['GET'])
def api_product_details(code):
    try:
        product = get_product_by_code(code)
        if product:
            # Helper to convert decimals
            for key, value in product.items():
                from decimal import Decimal
                if isinstance(value, Decimal):
                    product[key] = float(value)
            
            return jsonify({'ok': True, 'product': product})
        else:
            return jsonify({'ok': False, 'error': 'Product not found'}), 404
    except Exception as e:
        print(f"Error getting product details: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@shopping_bp.route('/api/product/stock/<product_code>', methods=['GET'])
def api_product_stock(product_code):
    try:
        stock_info = get_product_stock_by_code(product_code)
        return jsonify({'ok': True, 'stock_info': stock_info})
    except Exception as e:
        print(f"Error getting product stock: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500
    
#api para obtener la imagen de un producto por su código
@shopping_bp.route('/api/product/image/<product_code>', methods=['GET'])
def api_product_image(product_code):
    try:
        image_data = get_product_image_by_code(product_code)
        if image_data:
            return send_file(io.BytesIO(image_data), mimetype='image/jpeg')
        else:
            return jsonify({'ok': False, 'error': 'Image not found'}), 404
    except Exception as e:
        print(f"Error getting product image: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

#api para obtener unidades de medida de productos
@shopping_bp.route('/api/product/units/<product_code>', methods=['GET'])
def api_product_units(product_code):
    try:
        units = get_product_units_by_code(product_code)
        return jsonify({'ok': True, 'units': units})
    except Exception as e:
        print(f"Error getting product units: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


# API para guardar una operación de compra
@shopping_bp.route('/api/shopping/operation/save', methods=['POST'])
def api_save_shopping_operation():
    try:
        # 1. Obtener datos JSON
        data = request.get_json()
        print("--- DEBUG: Payload recibido ---")
        print(data)
        print("-------------------------------")

        if not data:
            return jsonify({'ok': False, 'error': 'No JSON data received'}), 400

        # --- NUEVO: Recuperar datos de la sesión ---
        cached_products = session.get('current_auto_order_products', {})
        # -------------------------------------------

        # 2. Separar Header y Details
        details_data = data.get('details', [])
        
        # Crear copia para el header y remover 'details'
        header_data = data.copy()
        if 'details' in header_data:
            del header_data['details']

        # Asignar fecha de emisión actual si no viene o está vacía
        if not header_data.get('emission_date'):
            header_data['emission_date'] = date.today()
        if not header_data.get('reception_date'):
            header_data['reception_date'] = date.today()

        # Limpiar otros campos de fecha vacíos para evitar error de sintaxis en BD
        date_fields = ['reception_date', 'expiration_date']
        for field in date_fields:
            if field in header_data and header_data[field] == "":
                header_data[field] = None

        print("--- DEBUG: Header Data ---")
        print(header_data)
        
        print("--- DEBUG: Details Data ---")
        print(details_data)

        # 3. Guardar Header
        # Instanciar dataclass (filtrando claves extra si es necesario, pero asumimos que el frontend manda lo correcto salvo 'details')
        # Nota: Si el dataclass es estricto, cualquier campo extra fallará.
        # Vamos a intentar instanciarlo directamente.
        header_obj = SetShoppingOperationData(**header_data)
        
        operation_id = save_shopping_operation(header_obj)
        print(f"--- DEBUG: Operación guardada con ID: {operation_id} ---")

        # 4. Guardar Detalles
        for item in details_data:
            # Limpiar datos del item
            item_clean = item.copy()
            
            # --- NUEVO: Rellenar datos desde la sesión ---
            product_code = item_clean.get('code_product')
            if product_code and product_code in cached_products:
                cached_item = cached_products[product_code]
                
                # Aquí rellenamos los datos que faltan o aseguramos la integridad
                # Si el frontend no envió descripción, marca o modelo, los tomamos del cache
                if not item_clean.get('description_product'):
                    item_clean['description_product'] = cached_item.get('product_description', '')
                
                if not item_clean.get('mark'):
                    item_clean['mark'] = cached_item.get('product_mark', '')
                
                # Puedes agregar más campos aquí si es necesario, por ejemplo:
                # item_clean['model'] = cached_item.get('product_model', '')
                # item_clean['referenc'] = cached_item.get('product_reference', '')
            # ---------------------------------------------

            # Remover campos de UI que no están en el dataclass
            if 'unit_desc' in item_clean:
                del item_clean['unit_desc']
            
            # Asignar ID de la operación
            item_clean['main_correlative'] = operation_id
            
            # Instanciar dataclass de detalle
            detail_obj = SetShoppingOperationDetailData(**item_clean)
            
            # Guardar detalle
            save_shopping_operation_detail(detail_obj)

        return jsonify({'ok': True, 'message': str(operation_id)})

    except TypeError as te:
        print(f"Error de tipo (posiblemente campos extra en dataclass): {te}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': f"Error de validación de datos: {str(te)}"}), 400
    except Exception as e:
        print(f"Error saving operation: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500



# API para crear un producto
@shopping_bp.route('/api/product/create', methods=['POST'])
def api_create_product():
    try:
        data = request.get_json()
        current_sale_tax = data.get('sale_tax') 
        current_buy_tax = data.get('buy_tax')   
        sale_tax_divisor = 1.16 if current_sale_tax == "01" else 1.0
        buy_tax_divisor = 1.16 if current_buy_tax == "01" else 1.0

        print("--- DEBUG: Payload recibido para crear producto ---")
        print(data)
        print("---------------------------------------------------")

        if not data:
            return jsonify({'ok': False, 'error': 'No JSON data received'}), 400

        # Validar campos requeridos mínimos
        if not data.get('code'):
             return jsonify({'ok': False, 'error': 'El campo código es obligatorio'}), 400
        if not data.get('description'):
             return jsonify({'ok': False, 'error': 'El campo nombre (descripción) es obligatorio'}), 400

        newProductData = Product(
            code=data.get('code'),
            description=data.get('description'),
            short_name=data.get('description'),
            mark="",
            referenc="",
            model="",
            department="00",
            days_warranty=0,
            sale_tax="01",
            buy_tax="01",
            rounding_type=2,
            costing_type=0,
            discount=0.0,
            max_discount=0.0,
            minimal_sale=float(data.get('minimum_price') or 0.0),
            maximal_sale=float(data.get('maximum_price') or 0.0),
            status="01",
            origin="01",
            take_department_utility=False,
            allow_decimal=True,
            edit_name=False,
            sale_price=0,
            product_type="T",
            technician="00",
            request_technician=True,
            serialized=False,
            request_details=False,
            request_amount=False,
            coin="02",
            allow_negative_stock=False,
            use_scale=False,
            add_unit_description=False,
            use_lots=False,
            lots_order=0,
            minimal_stock=0.0,
            notify_minimal_stock=False,
            size="",
            color="",
            extract_net_from_unit_cost_plus_tax=True,
            extract_net_from_unit_price_plus_tax=True,
            maximum_stock=0.0,
            action="I"
        )

        newProductUnitData = ProductUnits(
            correlative=None,
            unit="00",
            producto_codigo=data.get('code'),
            main_unit=True,
            conversion_factor=0,
            unit_type=0,
            show_in_screen=True,
            is_for_buy=True,
            is_for_sale=True,
            unitary_cost=(float(data.get('cost') or 0.0) / buy_tax_divisor),
            calculated_cost=(float(data.get('cost') or 0.0) / buy_tax_divisor),
            average_cost=(float(data.get('cost') or 0.0) / buy_tax_divisor),
            perc_waste_cost=0.0,
            perc_handling_cost=0.0,
            perc_operating_cost=0.0,
            perc_additional_cost=0.0,
            maximum_price=(float(data.get('maximum_price') or 0.0) / sale_tax_divisor),
            offer_price=(float(data.get('offer_price') or 0.0) / sale_tax_divisor),
            higher_price=(float(data.get('higher_price') or 0.0) / sale_tax_divisor),
            minimum_price=(float(data.get('minimum_price') or 0.0) / sale_tax_divisor),
            # Los porcentajes se calculan en base al costo unitario
            perc_maximum_price= ((float(data.get('maximum_price') or 0.0) - float(data.get('cost') or 0.0)) / float(data.get('cost') or 1.0)) * 100,
            perc_offer_price= ((float(data.get('offer_price') or 0.0) - float(data.get('cost') or 0.0)) / float(data.get('cost') or 1.0)) * 100,
            perc_higher_price= ((float(data.get('higher_price') or 0.0) - float(data.get('cost') or 0.0)) / float(data.get('cost') or 1.0)) * 100,
            perc_minimum_price= ((float(data.get('minimum_price') or 0.0) - float(data.get('cost') or 0.0)) / float(data.get('cost') or 1.0)) * 100,
            perc_freight_cost=0.0,
            perc_discount_provider=0.0,
            lenght=0.0,
            height=0.0,
            width=0.0,
            weight=0.0,
            capacitance=0.0
       )

        newProductCode = ProductCodes(
            main_code=data.get('code'),
            other_code=data.get('code'),
            code_type="C"

        )
        print(f"--- DEBUG: Objeto Product creado: {newProductData} ---")

        created_product_code = create_product(newProductData)
        created_product_units = create_product_units(newProductUnitData)
        created_product_code = create_product_codes(newProductCode) # Asumimos que devuelve el código del producto creado

        
        print(f"--- DEBUG: Producto creado con código: {created_product_code} ---")
        print(f"--- DEBUG: Producto creado con código: {created_product_units} ---")

        return jsonify({'ok': True, 'message': 'Product created successfully.', 'code': created_product_code})

    except Exception as e:
        print(f"Error creating product: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500