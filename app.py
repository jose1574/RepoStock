import psycopg2
from flask import Flask, render_template, request, redirect, url_for, session
from flask import jsonify
from dotenv import load_dotenv
import os, sys

#importar funciones de la base de datos
from db import get_stores, search_product, save_product_failure, get_store_by_code



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
def destination_store_selection():
    stores = get_stores()
    print(stores)
    return render_template('destination_store_selection.html', stores=stores)

#seleccion de deposito para configurar productos 
@app.route('/config_param_product_store')
def config_param_product_store():
    stores = get_stores()
    return render_template('config_param_product_store.html', stores=stores)

@app.route('/config_param_product', methods=['POST', 'GET'])
def config_param_product():
    product = []
    # Recuperar el store de la sesión si existe
    search_store = session.get('store')

    if request.method == 'POST':
        code_product = request.form.get('product_code')
        store_code = request.form.get('store_code')
        if store_code:
            search_store = get_store_by_code(store_code)
            session['store'] = search_store
            print('este es el codigo que busca la funcion ', search_store)

        product = search_product(code_product)
        print(product)

    # El store persiste en la sesión y se recupera en GET o POST
    return render_template('config_param_product.html', products=product, store=search_store)

@app.route('/save_config_param_product', methods=['POST'])
def save_config_param_product():
    if request.method == 'POST':
        store_code = request.form.get('store_code')
        product_code = request.form.get('product_code')
        minimal_stock = request.form.get('minimal_stock')
        maximum_stock = request.form.get('maximum_stock')

        # Normalizar tipos (int) y construir payload esperado por save_product_failure
        try:
            ms = int(minimal_stock) if minimal_stock not in (None, '') else None
        except ValueError:
            ms = None
        try:
            MaS = int(maximum_stock) if maximum_stock not in (None, '') else None
        except ValueError:
            MaS = None

        data = {
            'product_code': product_code,
            'store_code': store_code,
            'minimal_stock': ms,
            'maximum_stock': MaS
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

if __name__ == '__main__':
    app.run(
        debug=True,
        host='0.0.0.0',
        port=5001
        )