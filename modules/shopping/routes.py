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
    get_products_by_codes_list,
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
        products = get_products_history_by_provider(provider_code, None)        
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
        
        # Guardar proveedor en sesión
        provider_obj = get_provider_by_code(provider_code)
        if provider_obj:
            session['current_auto_order_provider'] = provider_obj.to_dict()
            print(f"--- DEBUG: Proveedor {provider_code} guardado en sesión ---")
            
        session.modified = True
        print(f"--- DEBUG: {len(products_map)} productos guardados en sesión ---")
        # --------------------------------

        return jsonify({'ok': True, 'items': products})
    except Exception as e:
        print(f"Error getting product history: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

# API para obtener el historial de productos por código de producto y codigo de proveedor
@shopping_bp.route('/api/products/history_by_code/<path:product_code>', methods=['GET'])
def api_products_history_by_product_code(product_code):
    try:
        provider_code = request.args.get('provider_code')
        print(f"Buscando historial para producto: {product_code} del proveedor {provider_code}")
        item = get_products_history_by_provider(provider_code, product_code)
        if not item:
            return jsonify({'ok': False, 'error': 'Product history not found'}), 404
        # Convertir Decimal a float
        print(f"Historial obtenido: {item}")
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

        # 2. validar proveedor exista
        provider_code = data.get('provider_code')
        provider = get_provider_by_code(provider_code)
        user = session.get('user', {})
        
        if not provider:
            return jsonify({'ok': False, 'error': f'Provider with code {provider_code} not found'}), 400

        # 3. CALCULAR TOTALES DESDE EL BACKEND
        details_data = data.get('details', [])
        
        # Sumamos las cantidades (amount) y calculamos montos monetarios
        total_qty = sum(float(item.get('amount', 0)) for item in details_data)
        total_net = sum(float(item.get('amount', 0)) * float(item.get('unitary_cost', 0)) for item in details_data)
        
        # Asumiendo IVA del 16% si no es exento (puedes ajustar esta lógica)
        tax_rate = 0.16 if not data.get('free_tax') else 0.0
        total_tax = total_net * tax_rate
        total_operation = total_net + total_tax
        # 4. Construir el payload completo para la operación
        payload_header = SetShoppingOperationData(
            correlative=None,
            operation_type="ORDER",
            document_no="",
            control_no="",
            emission_date=date.today(),
            reception_date=date.today(),
            provider_code=provider.provider_code,
            provider_name=provider.provider_name,
            provider_id=provider.provider_id,
            provider_address=provider.address,
            provider_phone=provider.phone,
            credit_days=provider.credit_days,
            expiration_date=date.today(),
            wait=False,
            description=data.get('description', ''),
            store=data.get('store', '00'),
            locations=data.get('locations', '00'),
            user_code=user.get('user_code', '00'),
            station="00",
            percent_discount=0.0,
            discount=0.0,
            percent_freight=0.0,
            freight=0.0,
            freight_tax='01',
            freight_aliquot=16.0,
            credit=0.0,
            cash=0.0,
            operation_comments=data.get('operation_comments', ''),
            pending=True,
            buyer=user.get('description', 'Sin Nombre'),
            total_amount=total_qty,
            total_net_details=total_net,
            total_tax_details=total_tax,
            total_details=total_operation,
            total_net=total_net,
            total_tax=total_tax,
            total=total_operation,
            total_retention_tax=0.0,
            total_retention_municipal=0.0,
            total_retention_islr=0.0,
            total_operation=total_operation,
            retention_tax_prorration=0.0,
            retention_islr_prorration=0.0,
            retention_municipal_prorration=0.0,
            coin_code=data.get('coin_code'),
            free_tax=False,
            total_exempt=0.0,
            secondary_coin='01',
            base_igtf=0.0,
            percent_igtf=0.0,
            igtf=0.0
        )

        # 5. Guardar la operación
        operation_id = save_shopping_operation(payload_header)

        if not operation_id:
            return jsonify({'ok': False, 'error': 'Failed to save operation'}), 500
        print(f"--- DEBUG: Operación guardada con ID {operation_id} ---")
        #6. obtiene los productos desde la base de datos para validacion
        details_data = data.get('details', [])
        # 7. extraer todos los codigos de producto de los detalles
        product_codes = [detail.get('code_product') for detail in details_data if detail.get('code_product')]
        

        # 8. obtener los productos desde la base de datos en un solo llamado
        products_in_db = get_products_by_codes_list(product_codes)
        products_map = {p['code']: p for p in products_in_db}

        
         # 3. Procesar detalles construyendo el objeto con datos reales de la DB
        for detail in details_data:
            product_code = detail.get('code_product')
            product_in_db = products_map.get(product_code)

            if not product_in_db:
                print(f"--- WARNING: Producto con código {product_code} no encontrado en la base de datos. Se omite. ---")
                continue  # O manejar el error según sea necesario

            detail_payload = SetShoppingOperationDetailData(
                main_correlative=operation_id,
                line=None,
                code_product=product_in_db['code'],
                description_product=product_in_db['description'],
                referenc=product_in_db.get('referenc', ''),
                mark=product_in_db.get('mark', ''),
                model=product_in_db.get('model', ''),
                amount=float(detail.get('amount', 0)),
                store='00',
                locations='00',
                unit=int(detail.get('unit', 0)),
                conversion_factor=1.0,
                unit_type=0,
                unitary_cost=float(detail.get('unitary_cost', 0)),
                sale_tax=product_in_db.get('sale_tax', '01'),
                sale_aliquot=float(product_in_db.get('sale_aliquot', 0.0)),
                buy_tax=product_in_db.get('buy_tax', '01'),
                buy_aliquot=float(product_in_db.get('buy_aliquot', 0.0)),
                price=float(detail.get('price', 0)),
                type_price=0,
                percent_discount=float(detail.get('percent_discount', 0.0)),
                discount=float(detail.get('discount', 0.0)),
                product_type=product_in_db.get('product_type', 'T'),
                total_net_cost=float(detail.get('total_net_cost', 0)),
                total_tax_cost=float(detail.get('total_tax_cost', 0)),
                total_cost=float(detail.get('total_cost', 0)),
                total_net_gross=float(detail.get('total_net_gross', 0)),
                total_tax_gross=float(detail.get('total_tax_gross', 0)),
                total_gross=float(detail.get('total_gross', 0)),
                total_net=float(detail.get('total_net', 0)),
                total_tax=float(detail.get('total_tax', 0)),
                total=float(detail.get('total', 0)),
                description=detail.get('description', ''),
                technician=product_in_db.get('technician', '00'),
                coin_code=payload_header.coin_code,
                total_weight=0.0
            )
            print("AQUIIII: ", detail_payload)
            # Guardar detalle
            save_shopping_operation_detail(detail_payload)
            print(f"--- DEBUG: Detalle de producto {product_code} guardado ---")
        return jsonify({'ok': True, 'message': 'Operation saved successfully.', 'operation_id': operation_id})
    except Exception as e:
        print(f"Error saving shopping operation: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500
    

# ...existing code...

# RUTA DE DEBUG: Ver contenido de la sesión

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