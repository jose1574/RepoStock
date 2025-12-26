from flask import Blueprint, render_template, jsonify, request, send_file, session
import io
from datetime import date


from modules.shopping.services.schemas.set_shopping_operation import SetShoppingOperationData
from modules.shopping.services.schemas.set_shopping_operation_details import SetShoppingOperationDetailData

from modules.shopping.services.shoppingDb import (
    get_shopping_operations, 
    get_providers, 
    get_products_for_modal,
    get_product_stock_by_code,
    get_provider_by_code,
    get_product_by_code,
    get_product_image_by_code,
    get_product_units_by_code,
    save_shopping_operation,
    save_shopping_operation_detail,
    get_coins
)

shopping_bp = Blueprint('shopping', __name__, template_folder='templates', url_prefix='/shopping') 


@shopping_bp.route('/shopping', methods=['GET'])
def shopping():
    user = session.get('user', {})
    coins = get_coins()
    return render_template('shopping.html', user=user, coins=coins)


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
        