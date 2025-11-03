from flask import Flask, render_template, request, redirect, url_for, session
from flask import jsonify
from dotenv import load_dotenv
import os, sys
import datetime
import json
from typing import List, Dict, Any
try:
    import pdfkit
except Exception:
    pdfkit = None
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

# Configuración de wkhtmltopdf (Windows):
# - Usa variable de entorno WKHTMLTOPDF_BIN si existe
# - Si no, intenta ruta típica por defecto en Windows
WKHTMLTOPDF_BIN = os.environ.get("WKHTMLTOPDF_BIN")
if not WKHTMLTOPDF_BIN:
    # rutas típicas de instalación
    possibles = [
        r"C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe",
        r"C:\\Program Files (x86)\\wkhtmltopdf\\bin\\wkhtmltopdf.exe",
    ]
    for p in possibles:
        if os.path.exists(p):
            WKHTMLTOPDF_BIN = p
            break

def get_pdfkit_config():
    if pdfkit is None:
        return None
    if not WKHTMLTOPDF_BIN or not os.path.exists(WKHTMLTOPDF_BIN):
        return None
    try:
        return pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_BIN)
    except Exception:
        return None



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
    product_not_found = False

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
            if not product:
                product_not_found = True
    else:
        # GET: intentar cargar la tienda desde sesión si existe
        search_store = get_store_by_code(session_store_code) if session_store_code else None

    # El store persiste en la sesión y se recupera en GET o POST
    return render_template('config_param_product.html', products=product, store=search_store, product_not_found=product_not_found)

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

        # Validación servidor: máximo no puede ser menor que mínimo
        if ms is not None and MaS is not None and MaS < ms:
            msg = 'El stock máximo no puede ser menor al stock mínimo.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"ok": False, "error": msg}), 400
            print(msg)
            return redirect(url_for('config_param_product'))

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
    store_origin_code = os.environ.get('DEFAULT_STORE_ORIGIN_CODE')
    selected_department = None

    # Resolver tiendas origen/destino para GET y POST
    search_store_origin = get_store_by_code(store_origin_code) if store_origin_code else None
    store_destination = get_store_by_code(session.get('store_code_destination', None)) if session.get('store_code_destination') else None

    if request.method == 'POST':
        # Actualizar destino desde el formulario si viene
        if request.form.get('store_code_destination'):
            session['store_code_destination'] = request.form.get('store_code_destination')
            store_destination = get_store_by_code(session.get('store_code_destination')) if session.get('store_code_destination') else None

        selected_department = request.form.get('department', None)
        products = get_collection_products(store_origin_code, session.get('store_code_destination'), selected_department)

    # Construir lista única de departamentos presentes en los productos para el filtro
    departments = []
    seen = set()
    for p in products:
        d = p.get('department_description')
        if d and d not in seen:
            seen.add(d)
            departments.append(d)

    return render_template(
        'create_collection_order.html',
        products=products,
        departments=departments,
        store_origin=search_store_origin,
        store_destination=store_destination,
        selected_department=selected_department
    )


# ---------- PREVISUALIZACIÓN DE LA ORDEN ----------
# Recibe JSON con items seleccionados y metadatos, los guarda en sesión para usar en PDF
@app.route('/collection/preview', methods=['POST'])
def collection_preview():
    try:
        payload = request.get_json(silent=True) or {}
        items: List[Dict[str, Any]] = payload.get('items', []) or []
        meta: Dict[str, Any] = payload.get('meta', {}) or {}

        # Normalizar cantidades a float y filtrar inválidos
        normalized_items = []
        codes = []
        for it in items:
            code = (it.get('product_code') or it.get('code') or '').strip()
            if not code:
                continue
            raw_qty = it.get('quantity', it.get('qty', 0))
            if isinstance(raw_qty, str):
                raw_qty = raw_qty.replace(',', '.')
            try:
                qty = float(raw_qty)
            except Exception:
                qty = 0.0
            if qty <= 0:
                continue
            normalized_items.append({
                'product_code': code,
                'quantity': qty,
                'description': it.get('description'),
                'unit': it.get('unit')
            })
            codes.append(code)

        # enriquecer con descripciones si faltan
        if codes:
            try:
                base_info = {p['code']: p for p in get_products_by_codes(codes)}
            except Exception:
                base_info = {}
        else:
            base_info = {}

        for it in normalized_items:
            b = base_info.get(it['product_code'], {})
            if not it.get('description'):
                it['description'] = b.get('description') or b.get('product_description')
            if not it.get('unit'):
                it['unit'] = b.get('unit_description')

        # resolver datos de tienda origen/destino
        origin_code = meta.get('store_origin_code') or os.environ.get('DEFAULT_STORE_ORIGIN_CODE')
        dest_code = meta.get('store_destination_code') or session.get('store_code_destination')
        try:
            origin_store = get_store_by_code(origin_code) if origin_code else None
            dest_store = get_store_by_code(dest_code) if dest_code else None
        except Exception:
            origin_store = None
            dest_store = None

        preview_data = {
            'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
            'user_code': session.get('user_id', '01'),
            'department': meta.get('department') or session.get('department'),
            'store_origin': {
                'code': (origin_store or {}).get('code') if isinstance(origin_store, dict) else getattr(origin_store, 'code', None),
                'description': (origin_store or {}).get('description') if isinstance(origin_store, dict) else getattr(origin_store, 'description', None),
            },
            'store_destination': {
                'code': (dest_store or {}).get('code') if isinstance(dest_store, dict) else getattr(dest_store, 'code', None),
                'description': (dest_store or {}).get('description') if isinstance(dest_store, dict) else getattr(dest_store, 'description', None),
            },
            'items': normalized_items,
            'total_quantity': sum(i['quantity'] for i in normalized_items)
        }
        session['collection_preview'] = preview_data
        session.modified = True
        return jsonify({'ok': True, 'count': len(normalized_items)}), 200
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400


@app.route('/collection/preview.pdf', methods=['GET'])
def collection_preview_pdf():
    data = session.get('collection_preview')
    if not data:
        return 'No hay datos de previsualización en la sesión. Genera la previsualización primero.', 400

    # Permitir ver HTML sin generar PDF para depuración
    if request.args.get('view') == 'html':
        return render_template('preview_collection_order.html', data=data)

    if pdfkit is None:
        return 'pdfkit no está instalado en el entorno de Python.', 500

    config = get_pdfkit_config()
    if not config:
        return 'wkhtmltopdf no está configurado o no se encuentra el ejecutable.', 500

    html = render_template('preview_collection_order.html', data=data)
    options = {
        'page-size': 'A4',
        'encoding': 'UTF-8',
        'margin-top': '10mm',
        'margin-bottom': '10mm',
        'margin-left': '10mm',
        'margin-right': '10mm',
    }
    try:
        pdf = pdfkit.from_string(html, False, configuration=config, options=options)
    except Exception as e:
        return f'Error generando PDF: {e}', 500

    from flask import make_response
    resp = make_response(pdf)
    resp.headers['Content-Type'] = 'application/pdf'
    # Inline para previsualizar en el navegador
    resp.headers['Content-Disposition'] = 'inline; filename="orden_recoleccion_preview.pdf"'
    return resp


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