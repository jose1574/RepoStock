import psycopg2
from flask import Flask, render_template, request, redirect, url_for, session
from flask import jsonify
from dotenv import load_dotenv
import os, sys
import datetime
#importar funciones de la base de datos
from db import get_stores, search_product, save_product_failure, get_store_by_code, get_collection_products, save_transfer_order_in_wait, save_transfer_order_items, get_products_by_codes, get_correlative_product_unit, get_store_by_code, get_departments, search_product_failure




if getattr(sys, "frozen", False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

template_folder = os.path.join(base_path, "templates")

env_path = os.path.join(base_path, ".env")
load_dotenv(env_path)

app = Flask(__name__, template_folder=template_folder)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "root1574**") 



@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/destination-store-selection')
def destination_store_selection_param_product():
    stores = get_stores()
    return render_template('destination_store_selection_param_product.html', stores=stores)

#seleccion de deposito para configurar productos 
@app.route('/config_param_product_store')
def config_param_product_store():
    stores = get_stores()
    return render_template('config_param_product_store.html', stores=stores)

@app.route('/config_param_product', methods=['POST', 'GET'])
def config_param_product():
    # Inicializar valores por defecto
    product = None
    search_store = None

    # Recuperar el código de store de la sesión (si existe)
    session_store_code = session.get('store')
    if isinstance(session_store_code, str):
        session_store_code = session_store_code.strip()

    if request.method == 'POST':
        # obtiene los datos del formulario
        product_code = request.form.get('product_code')
        store_code = request.form.get('store_code')

        # Guardar el store en la sesión si viene del formulario
        if store_code:
            session['store'] = store_code
            session_store_code = store_code

        print('esto es lo que tengo que la session de store ', session.get('store'))

        # Buscar la tienda y el producto usando el código de store actual
        search_store = get_store_by_code(session_store_code) if session_store_code else None
        if product_code:
            product = search_product_failure(product_code, session_store_code)
            print('Producto encontrado:', product)
    else:
        # GET: intentar cargar la tienda desde sesión si existe
        search_store = get_store_by_code(session_store_code) if session_store_code else None

    # El store persiste en la sesión y se recupera en GET o POST
    return render_template('config_param_product.html', products=product, store=search_store)

@app.route('/save_config_param_product', methods=['POST'])
def save_config_param_product():
    if request.method == 'POST':
        store_code = request.form.get('store_code')
        product_code = request.form.get('product_code')
        minimal_stock = request.form.get('minimal_stock')
        maximum_stock = request.form.get('maximum_stock')
        location = request.form.get('location')


        # Normalizar tipos (int) y construir payload esperado por save_product_failure
        try:
            ms = int(minimal_stock) if minimal_stock not in (None, '') else None
        except ValueError:
            ms = None
        try:
            MaS = int(maximum_stock) if maximum_stock not in (None, '') else None
        except ValueError:
            MaS = None
        try:
            loc = str(location) if location not in (None, '') else None
        except ValueError:
            loc = None

        data = {
            'product_code': product_code,
            'store_code': store_code,
            'minimal_stock': ms,
            'maximum_stock': MaS,
            'location': loc
        }

        try:
            # save_product_failure espera un dict con las claves usadas en db.py
            save_product_failure(data)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"ok": True, "message": "Producto guardado correctamente"}), 200
            return redirect(url_for('config_param_product'))
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"ok": False, "error": str(e)}), 500
            # En no-AJAX redirigir mostrando el error en logs; podrías usar flash para mostrar al usuario
            print('Error guardando parámetros:', e)
            return redirect(url_for('config_param_product'))

@app.route('/select_store_destination_collection_order', methods=['POST','GET'])
def select_store_destination_collection_order():
    stores= get_stores()
    return render_template('form_destination_store.html', stores=stores)

#ruta para crear orden de recoleccion
@app.route('/create_collection_order', methods=['POST','GET'])
def create_collection_order():
    products = []
    store_origin = os.environ.get('DEFAULT_STORE_ORIGIN_CODE')
    print('este es el deposito de origen', store_origin)
    department = None

    if request.method == 'POST':
        #BUSCAR LOS DEPOSITOS DE ORIGEN Y DESTINO
        search_store_origin = get_store_by_code(store_origin)
        store_destination = get_store_by_code(session.get('store_code_destination', None))
        department = get_departments()
        session['store_code_destination'] = request.form.get('store_code_destination')
        department = request.form.get('department', None)
        products = get_collection_products(store_origin, session.get('store_code_destination'), department)
    # Construir lista única de departamentos presentes en los productos para el filtro
    departments = []
    seen = set()
    for p in products:
        d = p.get('department_description')
        if d and d not in seen:
            seen.add(d)
            departments.append(d)

    return render_template('create_collection_order.html', products=products, departments=departments, store_origin=search_store_origin, store_destination=store_destination, selected_department=department   )


@app.route('/process_collection_products', methods=['POST'])
def process_collection_products():
    if request.method == 'POST':
        # Leer productos seleccionados y cantidades (permitir decimales, aceptar coma o punto)
        selected = request.form.getlist('selected_products')
        product_codes = [code for code in selected if code]

        # obtener datos base de los productos (descripcion u otros campos si hacen falta)
        products_info = {p['code']: p for p in get_products_by_codes(product_codes)} if product_codes else {}

        # origen/destino (si vienen en el formulario) o por defecto
        stock_store_origin = request.form.get('stock_store_origin', os.environ.get('DEFAULT_STORE_ORIGIN_CODE', '01'))
        store_stock_destination = session.get('store_code_destination', None)

        items = []
        for code in product_codes:
            raw = request.form.get(f'to_transfer_{code}', '0')
            if isinstance(raw, str):
                raw = raw.replace(',', '.')
            try:
                qty = float(raw)
            except (ValueError, TypeError):
                qty = 0.0

            if qty <= 0:
                # saltar ítems con cantidad inválida
                continue

            prod = products_info.get(code, {})
            item = {
                'product_code': code,
                'description': prod.get('description') if prod else None,
                'quantity': qty,
                'from_store': stock_store_origin,
                'to_store': store_stock_destination or prod.get('store') if prod else store_stock_destination,
                # valores por defecto para campos opcionales que espera la función
                'unit': get_correlative_product_unit(code),
                'conversion_factor': 1.0,
                'unit_type': 1,
                'unit_price': 0.0,
                'total_price': 0.0,
                'total_cost': 0.0,
                'coin_code': '02',
                'to_store' : session.get('store_code_destination', None)
            }
            items.append(item)

        if not items:
            # nada que procesar
            print('No hay items válidos para procesar')
            return redirect(url_for('create_collection_order'))

        # Crear la orden de transferencia
        transfer_data = {
            'emission_date': datetime.date.today(),
            'wait': True,
            'description': 'CREACION DE ORDEN DE TRASLADO DESDE APP REPOSTOCK',
            'user_code': session.get('user_id', '01'),  # usar usuario en sesión si existe
            'station': '00',
            'store': stock_store_origin,
            'locations': '00',
            'destination_store': session.get('store_code_destination', None),
            'operation_comments': 'Orden creada desde interface Repostock',
            'total': sum([it['quantity'] for it in items])
        }

        try:
            order_id = save_transfer_order_in_wait(transfer_data)
            if not order_id:
                print('No se pudo crear la orden de transferencia')
                return redirect(url_for('create_collection_order'))

            # Guardar los items
            save_transfer_order_items(order_id, items)
            print('Orden creada id=', order_id)
        except Exception as e:
            print('Error procesando la orden de traslado:', e)
            # aquí podrías usar flash() para mostrar el error al usuario
            return redirect(url_for('create_collection_order'))

        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(
        debug=True,
        host='0.0.0.0',
        port=5001
        )