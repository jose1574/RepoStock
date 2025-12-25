from flask import Blueprint, render_template, jsonify, request, send_file, session
import io


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
        data = request.json
        # Separar los detalles del header para evitar error en SetShoppingOperationData
        details = data.pop('details', [])
        print("estos son los datos recibidos en el backend para guardar la operacion de compra:", data)
        
        # Guardar el header de la operación de compra
        correlativo = save_shopping_operation(SetShoppingOperationData(**data))
        
        # Guardar los detalles de la operación de compra
        for detail in details:
            detail['main_correlative'] = correlativo
            save_shopping_operation_detail(SetShoppingOperationDetailData(**detail))
        
        
        return jsonify({'ok': True, 'message': correlativo})
    except Exception as e:
        print(f"Error saving shopping operation: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500
    
# API para obtener monedas disponibles
