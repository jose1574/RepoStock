from flask import (
    Flask,
    render_template,
    render_template_string,
    request,
    redirect,
    url_for,
    session,
)
from flask import jsonify
from dotenv import load_dotenv
import os, sys
import datetime
import json
from typing import List, Dict, Any
import pdfkit

try:
    import pdfkit
except Exception:
    pdfkit = None
"""
Cargar variables de entorno ANTES de importar db.py para que DB_CONFIG lea .env correctamente
en entornos empaquetados (PyInstaller) y desarrollo.
"""
if getattr(sys, "frozen", False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

template_folder = os.path.join(base_path, "templates")

env_path = os.path.join(base_path, ".env")
# En modo congelado, permite un .env externo junto al ejecutable que tenga prioridad
if getattr(sys, "frozen", False):
    try:
        exe_dir = os.path.dirname(sys.executable)
        external_env = os.path.join(exe_dir, ".env")
        if os.path.exists(external_env):
            try:
                load_dotenv(external_env, encoding="utf-8", override=True)
            except TypeError:
                load_dotenv(external_env, override=True)
    except Exception:
        pass

# Carga el .env embebido (no sobrescribe claves ya definidas por el externo)
try:
    load_dotenv(env_path, encoding="utf-8", override=False)
except TypeError:
    # Para compatibilidad con versiones antiguas de python-dotenv sin parámetro encoding
    load_dotenv(env_path, override=False)

# importar funciones de la base de datos (después de cargar .env)
from db import (
    get_stores,
    save_product_failure,
    get_store_by_code,
    get_collection_products,
    save_transfer_order_in_wait,
    save_transfer_order_items,
    get_products_by_codes,
    get_correlative_product_unit,
    get_inventory_operations_by_correlative,
    get_inventory_operations_details_by_correlative,
    update_description_inventory_operations,
    get_document_no_inventory_operation,
    update_minmax_product_failure,
    update_locations_products_failures as db_update_locations_products_failures,
    get_inventory_operations,
    delete_inventory_operation_by_correlative,
    # save_collection_order,  # no se usa; creación directa con save_transfer_order_in_wait
    update_inventory_operation_detail_amount,
    search_product_failure,
    search_product,
    # update_inventory_operation_type,  # deprecado: ahora se usa description para validación
    get_product_stock,
)

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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("index"))


@app.route("/destination-store-selection")
def destination_store_selection_param_product():
    stores = get_stores()
    return render_template(
        "destination_store_selection_param_product.html", stores=stores
    )


@app.route("/config_param_product_store")
def config_param_product_store():
    stores = get_stores()
    return render_template("config_param_product_store.html", stores=stores)


@app.route("/config_param_product", methods=["POST"])
def config_param_product():
    # Inicializar valores por defecto
    product = None
    search_store = None
    product_not_found = False

    # Recuperar el código de store de la sesión (si existe)
    session_store_code = session.get("store")
    if isinstance(session_store_code, str):
        session_store_code = session_store_code.strip()

    if request.method == "POST":
        # obtiene los datos del formulario
        product_code = request.form.get("product_code")
        store_code = request.form.get("store_code")

        # Guardar el store en la sesión si viene del formulario
        if store_code:
            session["store"] = store_code
            session_store_code = store_code
        # Buscar la tienda y el producto usando el código de store actual
        search_store = (
            get_store_by_code(session_store_code) if session_store_code else None
        )
        if product_code:
            product = search_product_failure(product_code, session_store_code)
            if not product:
                product_not_found = True
    else:
        # GET: intentar cargar la tienda desde sesión si existe
        search_store = (
            get_store_by_code(session_store_code) if session_store_code else None
        )

    # El store persiste en la sesión y se recupera en GET o POST
    return render_template(
        "config_param_product.html",
        products=product,
        store=search_store,
        product_not_found=product_not_found,
    )


@app.route("/api/product_failure/minmax", methods=["POST"])
def api_update_minmax_product_failure():
    """Actualiza mínimo y máximo para un producto/depósito. Devuelve JSON.
    Usa el depósito desde sesión (session['store']) si no se envía store_code explícito.
    """
    product_code = request.form.get("product_code")
    store_code = session.get("store_code_destination")
    minimal_stock = request.form.get("minimal_stock")
    maximum_stock = request.form.get("maximum_stock")

    # Validaciones básicas
    if not product_code or not store_code:
        return jsonify({"ok": False, "error": "Faltan product_code o store_code."}), 400
    try:
        ms = int(minimal_stock) if minimal_stock not in (None, "") else None
        mx = int(maximum_stock) if maximum_stock not in (None, "") else None
    except ValueError:
        return (
            jsonify({"ok": False, "error": "Valores inválidos para mínimos/máximos."}),
            400,
        )
    if ms is not None and mx is not None and mx < ms:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "El stock máximo no puede ser menor al stock mínimo.",
                }
            ),
            400,
        )

    try:
        update_minmax_product_failure(store_code, product_code, ms, mx)
        return jsonify(
            {
                "ok": True,
                "product_code": product_code,
                "store_code": store_code,
                "minimal_stock": ms,
                "maximum_stock": mx,
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/collection_order/delete_item", methods=["POST"])
def api_collection_order_delete_item():
    """Elimina un producto del detalle de la ORDER_COLLECTION por correlativo y código."""
    correlative = request.form.get("correlative", type=int)
    product_code = (request.form.get("product_code") or "").strip()
    if not correlative:
        return jsonify({"ok": False, "error": "Falta correlative"}), 400
    if not product_code:
        return jsonify({"ok": False, "error": "Falta product_code"}), 400
    try:
        # Bloquear si ya fue validada
        try:
            hdr_rows = get_inventory_operations_by_correlative(correlative, "TRANSFER", True)
            if hdr_rows:
                d = (hdr_rows[0].get("description") or "").strip().lower()
                if d == "la operacion fue validada" or d.startswith("documento chequeado"):
                    return jsonify({"ok": False, "error": "Orden ya validada. No se puede eliminar."}), 400
        except Exception:
            pass
        from db import delete_inventory_operation_detail
        delete_inventory_operation_detail(correlative, product_code)
        return jsonify({"ok": True, "deleted": product_code})
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error eliminando: {e}"}), 500


@app.route("/save_config_param_product", methods=["POST"])
def save_config_param_product():
    if request.method == "POST":
        store_code = request.form.get("store_code")
        product_code = request.form.get("product_code")
        minimal_stock = request.form.get("minimal_stock")
        maximum_stock = request.form.get("maximum_stock")
        location = request.form.get("location")

        # Normalizar tipos (int) y construir payload esperado por save_product_failure
        try:
            ms = int(minimal_stock) if minimal_stock not in (None, "") else None
        except ValueError:
            ms = None
        try:
            MaS = int(maximum_stock) if maximum_stock not in (None, "") else None
        except ValueError:
            MaS = None
        try:
            loc = str(location) if location not in (None, "") else None
        except ValueError:
            loc = None

        data = {
            "product_code": product_code,
            "store_code": store_code,
            "minimal_stock": ms,
            "maximum_stock": MaS,
            "location": loc,
        }

        # Validación servidor: máximo no puede ser menor que mínimo
        if ms is not None and MaS is not None and MaS < ms:
            msg = "El stock máximo no puede ser menor al stock mínimo."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"ok": False, "error": msg}), 400
            print(msg)
            return redirect(url_for("config_param_product"))

        try:
            # save_product_failure espera un dict con las claves usadas en db.py
            save_product_failure(data)
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return (
                    jsonify({"ok": True, "message": "Producto guardado correctamente"}),
                    200,
                )
            return redirect(url_for("config_param_product"))
        except Exception as e:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"ok": False, "error": str(e)}), 500
            # En no-AJAX redirigir mostrando el error en logs; podrías usar flash para mostrar al usuario
            print("Error guardando parámetros:", e)
            return redirect(url_for("config_param_product"))


@app.route("/select_store_destinatSion_collection_order", methods=["POST", "GET"])
def select_store_destination_collection_order():
    stores = get_stores()
    return render_template("form_destination_store.html", stores=stores)


# ruta para crear orden de recoleccion
@app.route("/create_collection_order", methods=["POST", "GET"])
def create_collection_order():
    products = []
    store_origin_code = os.environ.get("DEFAULT_STORE_ORIGIN_CODE")
    selected_department = None

    # Resolver tiendas origen/destino para GET y POST
    search_store_origin = (
        get_store_by_code(store_origin_code) if store_origin_code else None
    )
    store_destination = (
        get_store_by_code(session.get("store_code_destination", None))
        if session.get("store_code_destination")
        else None
    )

    if request.method == "POST":
        # Actualizar destino desde el formulario si viene
        if request.form.get("store_code_destination"):
            session["store_code_destination"] = request.form.get(
                "store_code_destination"
            )
            store_destination = (
                get_store_by_code(session.get("store_code_destination"))
                if session.get("store_code_destination")
                else None
            )

        selected_department = request.form.get("department", None)
        products = get_collection_products(
            store_origin_code,
            session.get("store_code_destination"),
            selected_department,
        )

    # Construir listas únicas para filtros: departamentos y marcas presentes en los productos
    departments = []
    seen = set()
    for p in products:
        d = p.get("department_description")
        if d and d not in seen:
            seen.add(d)
            departments.append(d)

    brands = []
    seen_b = set()
    for p in products:
        b = p.get("mark") or p.get("brand")
        if b and b not in seen_b:
            seen_b.add(b)
            brands.append(b)
    print("estos son los productos que reviuso ->",products)
    return render_template(
        "create_collection_order.html",
        products=products,
        departments=departments,
        store_origin=search_store_origin,
        store_destination=store_destination,
        selected_department=selected_department,
        brands=brands,
    )


@app.route("/collection/preview.pdf", methods=["POST", "GET"])
def collection_preview_pdf():
    # Aceptar parámetros por POST (form) o GET (querystring)
    correlative = None
    operation_type = "TRANSFER"
    wait = True

    if request.method == "POST":
        correlative = request.form.get("correlative", default=None, type=int)
        operation_type = request.form.get(
            "operation_type", default="TRANSFER", type=str
        )
        wait_param = request.form.get("wait", default="true", type=str)
        wait = True if (str(wait_param).lower() in ("1", "true", "yes", "y")) else False
    else:
        correlative = request.args.get("correlative", default=None, type=int)
        operation_type = request.args.get(
            "operation_type", default="TRANSFER", type=str
        )
        wait_param = request.args.get("wait", default="true", type=str)
        wait = True if (str(wait_param).lower() in ("true")) else False

    if not correlative:
        return "Falta el parámetro correlative", 400

    # Consultar encabezado y detalle
    try:
        header_rows = get_inventory_operations_by_correlative(
            correlative, operation_type, wait
        )
        header = header_rows[0] if header_rows else {}
        # Para el PDF queremos la ubicación del depósito de origen
        details = get_inventory_operations_details_by_correlative(correlative, header.get("store") if header else None)
    except Exception as e:
        return f"Error consultando datos de la orden: {e}", 500

    # Cargar reporte desde carpeta reports/ y renderizar con Jinja
    report_path = os.path.join(base_path, "reports", "report_collection_order.html")
    if not os.path.exists(report_path):
        return (
            "No se encontró el reporte report_collection_order.html en la carpeta reports.",
            500,
        )
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            report_template = f.read()
    except Exception as e:
        return f"No se pudo leer el reporte: {e}", 500

    # Contexto para el reporte
    context = {
        "header": header,
        "details": details,
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    html = render_template_string(report_template, **context)

    if pdfkit is None:
        return "pdfkit no está instalado en el entorno de Python.", 500

    config = get_pdfkit_config()
    if not config:
        return "wkhtmltopdf no está configurado o no se encuentra el ejecutable.", 500

    options = {
        "page-size": "A4",
        "encoding": "UTF-8",
        "margin-top": "10mm",
        "margin-bottom": "10mm",
        "margin-left": "10mm",
        "margin-right": "10mm",
    }
    try:
        pdf = pdfkit.from_string(html, False, configuration=config, options=options)
    except Exception as e:
        return f"Error generando PDF: {e}", 500

    from flask import make_response

    resp = make_response(pdf)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = (
        'inline; filename="orden_recoleccion_preview.pdf"'
    )
    return resp


@app.route("/process_collection_products", methods=["POST"])
def process_collection_products():
    if request.method == "POST":
        # Leer productos seleccionados y cantidades (permitir decimales, aceptar coma o punto)
        selected = request.form.getlist("selected_products")
        product_codes = [code for code in selected if code]
        # obtener datos base de los productos (descripcion u otros campos si hacen falta)
        products_info = (
            {p["code"]: p for p in get_products_by_codes(product_codes)}
            if product_codes
            else {}
        )

        # origen/destino (si vienen en el formulario) o por defecto
        stock_store_origin = request.form.get(
            "stock_store_origin", os.environ.get("DEFAULT_STORE_ORIGIN_CODE", "01")
        )
        store_stock_destination = session.get("store_code_destination", None)

        items = []
        for code in product_codes:
            raw = request.form.get(f"to_transfer_{code}", "0")
            if isinstance(raw, str):
                raw = raw.replace(",", ".")
            try:
                qty = float(raw)
            except (ValueError, TypeError):
                qty = 0.0

            if qty <= 0:
                # saltar ítems con cantidad inválida
                continue

            prod = products_info.get(code, {})
            item = {
                "product_code": code,
                "description": prod.get("description") if prod else None,
                "quantity": qty,
                "from_store": stock_store_origin,
                "to_store": store_stock_destination,
                # valores por defecto para campos opcionales que espera la función
                "unit": get_correlative_product_unit(code),
                "conversion_factor": 1.0,
                "unit_type": 1,
                "unit_price": 0.0,
                "total_price": 0.0,
                "total_cost": 0.0,
                "coin_code": "02",
            }
            items.append(item)
        if not items:
            # nada que procesar
            print("No hay items válidos para procesar")
            return redirect(url_for("create_collection_order"))

        # Crear la orden de transferencia
        transfer_data = {
            "emission_date": datetime.date.today(),
            "wait": True,
            "user_code": session.get(
                "user_id", "01"
            ),  # usar usuario en sesión si existe
            "station": "00",
            "store": stock_store_origin,
            "locations": "00",
            "destination_store": session.get("store_code_destination", None),
            "operation_comments": "Orden creada desde interfaz Repostock",
            "total": sum([it["quantity"] for it in items]),
        }

        try:
            order_id = save_transfer_order_in_wait(transfer_data, "La operacion aun no ha sido validada")

            if not order_id:
                print("No se pudo crear la orden de transferencia")
                return redirect(url_for("create_collection_order"))

            # Guardar los items
            save_transfer_order_items(order_id, items)
            # abre una ventana con el pdf de la orden creada usando la ruta collection_preview_pdf()
            print("Orden de recoleccion creada (process_collection_products) correlativo:", order_id)

        except Exception as e:
            print("Error procesando la orden de traslado:", e)
            # aquí podrías usar flash() para mostrar el error al usuario
            return redirect(url_for("create_collection_order"))

        return redirect(
            url_for("collection_preview_pdf", correlative=order_id, wait="true", operation_type="TRANSFER")
        )


@app.route("/delete_product/<code>", methods=["POST"])
def delete_product(code):
    delete_item_product_session(code)
    return redirect(url_for("update_locations_products_failures"))

#para procesar la ruta de actualizacion de ubicacion de los productos con fallas
@app.route("/update_location_products_failures", methods=["GET", "POST"])
@app.route("/<store_code>/update_location_products_failures", methods=["GET", "POST"])
def update_locations_products_failures_products(store_code=None):
    # Resolver depósito de destino desde: ruta > querystring > sesión
    if not store_code:
        store_code = request.args.get("store_code") or session.get("store_location")
    store = get_store_by_code(store_code) if store_code else None

    if request.method == "POST":
        location = (request.form.get("location") or "").strip()
        if location:
            session["location"] = location
        # Permitir actualizar el store por POST si se envía explícito
        form_store = request.form.get("store_code_location")
        if form_store:
            session["store_location"] = form_store
        return redirect(url_for("update_locations_products_failures"))

    # GET: mostrar siempre el depósito y la ubicación actual (si existe)
    return render_template(
        "form_location.html",
        store=store,
        location=session.get("location", ""),
    )

# Limpiar sesión
@app.route("/clear", methods=["POST"])
def clear():
    store_code = session.get("store_location")
    session.pop("products", None)
    session.pop("location", None)
    return redirect(url_for("update_locations_products_failures_products", store_code=store_code))


# Eliminar ítem de la sesión por código
def delete_item_product_session(code):
    session_products = session.get("products", [])
    session_products = [p for p in session_products if p.get("code") != code]
    session["products"] = session_products


#para procesar la ruta de seleccion del deposito de destino y la ubicacion de los productos
@app.route("/form_destination_store_for_location", methods=["POST", "GET"])
def form_destination_store_for_location():
    stores = get_stores()
    return render_template("form_destination_store_for_location.html", stores=stores )


#ruta para guardar en sesion el deposito de destino seleccionado para la actualizacion de ubicacion de los productos con fallas
@app.route("/save_session_select_store_destination_for_location", methods=["POST", "GET"])
def save_session_select_store_destination_for_location():
    store_code = session.get("store_location")
    store = get_store_by_code(store_code)
    print("store_code ->", store)
    store_location = request.form.get("store_code_location")

    session['store_location'] = store_location
    return redirect(url_for("update_locations_products_failures_products", store_code=store_location))


@app.route("/update_location_products", methods=["POST"])
def update_location_products():
    if request.method == "POST":
        # Preferir datos del formulario si vienen; fallback a sesión
        location = request.form.get("location") or session.get("location", "")
        store_code = session.get("store_location", "")
        store = get_store_by_code(store_code)

        codes_from_form = request.form.getlist("product_code")
        if codes_from_form:
            products = [{"code": c} for c in codes_from_form]
        else:
            products = session.get("products", [])

        print(
            "update_location_products -> location:", location,
            "store:", store_code,
            "products_count:", len(products) if isinstance(products, list) else 0,
        )
        if location and products and store_code:
            # Actualiza location en products_failures por cada producto y depósito actual
            for p in products:
                product_code = p.get("code") if isinstance(p, dict) else None
                if product_code:
                    try:
                        db_update_locations_products_failures(
                            store_code, product_code, location
                        )
                    except Exception as e:
                        # Loguea y continúa con el siguiente
                        print(
                            f"Error actualizando ubicación para {product_code} en {store_code}: {e}"
                        )
            # Siempre limpiar la lista de productos de la sesión tras guardar
            session.pop("products", None)
    return redirect(url_for("update_locations_products_failures_products", store_code=store_code))


@app.route("/update_locations_products_failures", methods=["GET", "POST"])
def update_locations_products_failures():
    session_products = session.get("products", [])
    # Mantener la ubicación en sesión, sólo actualizar si viene una no vacía en el POST
    location = session.get("location", "")
    if request.method == "POST":
        update_locations_products_failures = request.form.get("location")
        if update_locations_products_failures is not None:
            update_locations_products_failures = update_locations_products_failures.strip()
            if update_locations_products_failures:
                session["location"] = update_locations_products_failures
                location = update_locations_products_failures
    print("update_locations_products_failures: location ->", location)
    last_search_empty = False
    last_search_code = ""
    if request.method == "POST":
        code_product = request.form.get("code_product", "")
        code_product = (code_product or "").strip()
        last_search_code = code_product
        print("index: recibido code_product -> '{}'".format(code_product))
        if code_product:
            try:
                new_products = search_product_failure(code_product, session.get("store_location"))
                print("index: new_products ->", new_products)
                last_search_empty = len(new_products) == 0
                # Evitar duplicados por 'code'
                existing_codes = {p.get("code") for p in session_products}
                for p in new_products:
                    if p.get("code") not in existing_codes:
                        session_products.append(p)
                        existing_codes.add(p.get("code"))
                # Guardar la lista actualizada en la sesión
                session["products"] = session_products
            except Exception as e:
                print("Error buscando productos:", e)
                last_search_empty = True
    return render_template(
        "update_locations_products_failures.html",
        products=session_products,
        location=location,
        last_search_empty=last_search_empty,
        last_search_code=last_search_code,
    )

## 

@app.route("/document_manager")
def document_manager():
    inventory_operations = get_inventory_operations()
    print("Inventory Operations:", inventory_operations[0])
    return render_template("document_manager.html", inventory_operations=inventory_operations)


@app.route("/document_manager/delete", methods=["POST"])
def delete_inventory_operation():
    """Elimina una orden de traslado por correlativo y vuelve a la lista de reportes."""
    correlative = request.form.get("correlative", type=int)
    if not correlative:
        return redirect(url_for("document_manager"))
    try:
        delete_inventory_operation_by_correlative(correlative)
    except Exception as e:
        # Registra el error y regresa a la lista; opcionalmente usar flash para el usuario
        print(f"No se pudo eliminar la operación {correlative}: {e}")
    return redirect(url_for("document_manager"))


@app.route("/save_collection_order", methods=["POST"])
def save_collection_order():
    if request.method == "POST":
        # Leer productos seleccionados y cantidades (permitir decimales, aceptar coma o punto)
        selected = request.form.getlist("selected_products")
        product_codes = [code for code in selected if code]

        # obtener datos base de los productos (descripcion u otros campos si hacen falta)
        products_info = (
            {p["code"]: p for p in get_products_by_codes(product_codes)}
            if product_codes
            else {}
        )

        # origen/destino (si vienen en el formulario) o por defecto
        stock_store_origin = request.form.get(
            "stock_store_origin", os.environ.get("DEFAULT_STORE_ORIGIN_CODE", "01")
        )
        store_stock_destination = session.get("store_code_destination", None)

        items = []
        for code in product_codes:
            raw = request.form.get(f"to_transfer_{code}", "0")
            if isinstance(raw, str):
                raw = raw.replace(",", ".")
            try:
                qty = float(raw)
            except (ValueError, TypeError):
                qty = 0.0

            if qty <= 0:
                # saltar ítems con cantidad inválida
                continue

            prod = products_info.get(code, {})
            item = {
                "product_code": code,
                "description": prod.get("description") if prod else None,
                "quantity": qty,
                "from_store": stock_store_origin,
                "to_store": store_stock_destination,
                # valores por defecto para campos opcionales que espera la función
                "unit": get_correlative_product_unit(code),
                "conversion_factor": 1.0,
                "unit_type": 1,
                "unit_price": 0.0,
                "total_price": 0.0,
                "total_cost": 0.0,
                "coin_code": "02",
            }
            items.append(item)
        if not items:
            # nada que procesar
            print("No hay items válidos para procesar")
            return redirect(url_for("create_collection_order"))

        # Crear la orden de transferencia
        transfer_data = {
            "emission_date": datetime.date.today(),
            "wait": True,
            "user_code": session.get(
                "user_id", "01"
            ),  # usar usuario en sesión si existe
            "station": "00",
            "store": stock_store_origin,
            "locations": "00",
            "destination_store": session.get("store_code_destination", None),
            "operation_comments": "Orden creada desde interfaz Repostock",
            "total": sum([it["quantity"] for it in items]),
        }

        try:
            # Crear la ORDER_COLLECTION con descripción inicial de no validada
            order_id = save_transfer_order_in_wait(transfer_data, "La operacion aun no ha sido validada")

            if not order_id:
                print("No se pudo crear la orden de transferencia")
                return redirect(url_for("create_collection_order"))

            # Guardar los items
            save_transfer_order_items(order_id, items)
            # abre una ventana con el pdf de la orden creada usando la ruta collection_preview_pdf()
            print(
                "Orden de traslado creada con éxito. Correlativo:",
                order_id,
            )

        except Exception as e:
            print("Error procesando la orden de traslado:", e)
            # aquí podrías usar flash() para mostrar el error al usuario
            return redirect(url_for("create_collection_order"))

        return redirect(
            url_for(
                "collection_preview_pdf",
                correlative=order_id,
                wait="true",
                operation_type="TRANSFER",
            )
        )
    

@app.route("/check_order_collection", methods=["GET"])
def check_order_collection():
    """Pantalla para chequear una ORDER_COLLECTION específica por su correlativo."""
    correlative = request.args.get("correlative", type=int)
    header = None
    details = []
    validated = True
    if correlative:
        try:
            rows = get_inventory_operations_by_correlative(correlative, "TRANSFER", True)
            if rows:
                header = rows[0]
                details = get_inventory_operations_details_by_correlative(correlative)
                # Determinar validación por descripción
                desc = (header.get("description") or "").strip().lower()
                # Se considera validada si ya fue marcada con el formato nuevo o el anterior
                validated = (desc == "la operacion fue validada" or desc.startswith("documento chequeado"))
                print("este es mi header", header)
        except Exception as e:
            print("Error cargando ORDER_COLLECTION:", e)
    return render_template("check_order_collection.html", correlative=correlative, header=header, items=details, validated=validated)


@app.route("/api/collection_order/update_count", methods=["POST"])
def api_collection_order_update_count():
    """Actualiza la cantidad contada de un producto en la ORDER_COLLECTION."""
    correlative = request.form.get("correlative", type=int)
    product_code = request.form.get("product_code")
    counted = request.form.get("counted")
    if not (correlative and product_code and counted is not None):
        return jsonify({"ok": False, "error": "Parámetros incompletos"}), 400
    try:
        # Bloquear si la orden ya fue validada
        try:
            hdr_rows = get_inventory_operations_by_correlative(correlative, "TRANSFER", True)
            if hdr_rows:
                d = (hdr_rows[0].get("description") or "").strip().lower()
                if d == "la operacion fue validada" or d.startswith("documento chequeado"):
                    return jsonify({"ok": False, "error": "Orden ya validada. No se puede modificar."}), 400
        except Exception:
            pass
        counted_val = float(str(counted).replace(",", "."))
        if counted_val < 0:
            return jsonify({"ok": False, "error": "Cantidad negativa"}), 400
    except ValueError:
        return jsonify({"ok": False, "error": "Cantidad inválida"}), 400
    try:
        rows = update_inventory_operation_detail_amount(correlative, product_code, counted_val)
        if rows == 0:
            return jsonify({"ok": False, "error": "Producto no encontrado en la orden o código no coincide."}), 404
        return jsonify({"ok": True, "product_code": product_code, "counted": counted_val, "rows": rows})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
@app.route("/check_transfer_reception", methods=["GET"])
def check_transfer_reception():
    """Pantalla para chequear la recepción de una TRANSFER procesada (wait=false)."""
    correlative = request.args.get("correlative", type=int)
    header = None
    details = []
    # Se elimina la lógica de bloqueo por validación: siempre permitir re-chequeo
    validated = False
    pending_wait = False  # indica que existe como wait=true (no procesada aún)
    if correlative:
        try:
            rows = get_inventory_operations_by_correlative(correlative, "TRANSFER", False)
            if rows and len(rows) > 0:
                header = rows[0]
                details = get_inventory_operations_details_by_correlative(correlative, header.get("destination_store"))
                # Ignorar estado de descripción para permitir múltiples validaciones
            else:
                # Fallback: buscar en espera (wait=true) para informar al usuario que aún no está procesada
                pending_rows = get_inventory_operations_by_correlative(correlative, "TRANSFER", True)
                if pending_rows:
                    pending_wait = True
                    # Podemos mostrar parte del encabezado para referencia al usuario, pero sin detalles para recepción
                    header = pending_rows[0]
                    # No cargamos detalles destino porque aún no está procesada
        except Exception as e:
            print("Error cargando TRANSFER procesada:", e)
    return render_template("check_transfer_reception.html", correlative=correlative, header=header, items=details, validated=validated, pending_wait=pending_wait)


@app.route("/api/reception/update_count", methods=["POST"])
def api_reception_update_count():
    """Actualiza la cantidad contada de un producto en la TRANSFER procesada (recepción)."""
    correlative = request.form.get("correlative", type=int)
    product_code = request.form.get("product_code")
    counted = request.form.get("counted")
    if not (correlative and product_code and counted is not None):
        return jsonify({"ok": False, "error": "Parámetros incompletos"}), 400
    try:
        # Bloquear si ya fue validada/chequeada
        try:
            hdr_rows = get_inventory_operations_by_correlative(correlative, "TRANSFER", False)
            if hdr_rows:
                d = (hdr_rows[0].get("description") or "").strip().lower()
                if d == "la operacion fue validada" or d.startswith("documento chequeado"):
                    return jsonify({"ok": False, "error": "Recepción ya validada. No se puede modificar."}), 400
        except Exception:
            pass
        counted_val = float(str(counted).replace(",", "."))
        if counted_val < 0:
            return jsonify({"ok": False, "error": "Cantidad negativa"}), 400
    except ValueError:
        return jsonify({"ok": False, "error": "Cantidad inválida"}), 400
    try:
        rows = update_inventory_operation_detail_amount(correlative, product_code, counted_val)
        if rows == 0:
            return jsonify({"ok": False, "error": "Producto no encontrado en la TRANSFER."}), 404
        return jsonify({"ok": True, "product_code": product_code, "counted": counted_val, "rows": rows})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/reception/confirm", methods=["POST"])
def api_reception_confirm():
    """Marca la TRANSFER procesada como chequeada en recepción (NO crea nueva operación)."""
    source_correlative = request.form.get("correlative", type=int)
    if not source_correlative:
        return jsonify({"ok": False, "error": "Falta correlative"}), 400
    try:
        header_rows = get_inventory_operations_by_correlative(source_correlative, "TRANSFER", False)
        if not header_rows:
            return jsonify({"ok": False, "error": "TRANSFER no encontrada"}), 404
        header = header_rows[0]
        details = get_inventory_operations_details_by_correlative(source_correlative, header.get("destination_store"))
        # Se permite revalidar múltiples veces: quitar bloqueo por descripción previa
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error consultando TRANSFER: {e}"}), 500

    # Validación de que todos los productos fueron contados
    try:
        counted_codes_raw = (request.form.get("counted_codes") or "").strip()
        counted_codes = set([c.strip() for c in counted_codes_raw.split(",") if c and c.strip()])
        server_codes = set([d.get("code_product") for d in details if d.get("code_product")])
        if not details or len(server_codes) == 0:
            return jsonify({"ok": False, "error": "La TRANSFER no tiene detalles"}), 400
        if not counted_codes or counted_codes != server_codes:
            return jsonify({"ok": False, "error": "No se puede validar: faltan productos por contar.", "expected": sorted(list(server_codes)), "received": sorted(list(counted_codes))}), 400
        # Recibir mapa de conteos para evaluación de diferencias (no se modifica DB)
        counts_json = request.form.get("counts")
        if not counts_json:
            return jsonify({"ok": False, "error": "Faltan conteos para validar diferencias (counts)."}), 400
        try:
            counts_map = json.loads(counts_json)
            if not isinstance(counts_map, dict):
                return jsonify({"ok": False, "error": "Formato inválido de counts."}), 400
        except Exception:
            return jsonify({"ok": False, "error": "Counts no es un JSON válido."}), 400
        # Verificar que todos los códigos tengan conteo
        missing = [c for c in server_codes if c not in counts_map]
        if missing:
            return jsonify({"ok": False, "error": "Faltan conteos para algunos productos.", "missing": sorted(missing)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"Validación de conteo falló: {e}"}), 400

    try:
        # Detectar diferencias entre orden y conteo recibido
        differences = False
        for d in details:
            code = d.get("code_product")
            try:
                original = float(d.get("amount") or 0)
            except Exception:
                original = 0.0
            counted_val = float(counts_map.get(code, 0))
            if abs(original - counted_val) > 1e-9:
                differences = True
                break

        document_no = get_document_no_inventory_operation(source_correlative)
        base_msg = f"Documento chequeado en recepción {document_no}" if document_no else "Documento chequeado en recepción"
        desc_msg = base_msg + (" — Se encontraron diferencias" if differences else "")
        update_description_inventory_operations(source_correlative, desc_msg)
        return jsonify({
            "ok": True,
            "transfer_correlative": source_correlative,
            "document_no": document_no,
            "differences": differences,
            "message": ("Recepción validada con diferencias" if differences else "Recepción validada")
        })
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error actualizando recepción: {e}"}), 500


@app.route("/api/reception/delete_item", methods=["POST"])
def api_reception_delete_item():
    correlative = request.form.get("correlative", type=int)
    product_code = (request.form.get("product_code") or "").strip()
    if not correlative:
        return jsonify({"ok": False, "error": "Falta correlative"}), 400
    if not product_code:
        return jsonify({"ok": False, "error": "Falta product_code"}), 400
    try:
        try:
            hdr_rows = get_inventory_operations_by_correlative(correlative, "TRANSFER", False)
            if hdr_rows:
                d = (hdr_rows[0].get("description") or "").strip().lower()
                if d == "la operacion fue validada" or d.startswith("documento chequeado"):
                    return jsonify({"ok": False, "error": "Recepción ya validada. No se puede eliminar."}), 400
        except Exception:
            pass
        from db import delete_inventory_operation_detail
        delete_inventory_operation_detail(correlative, product_code)
        return jsonify({"ok": True, "deleted": product_code})
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error eliminando: {e}"}), 500


@app.route("/api/reception/add_item", methods=["POST"])
def api_reception_add_item():
    correlative = request.form.get("correlative", type=int)
    product_code_input = (request.form.get("product_code") or "").strip()
    quantity_raw = (request.form.get("quantity") or "").replace(",", ".")
    if correlative is None:
        return jsonify({"ok": False, "error": "Falta correlative"}), 400
    if not product_code_input:
        return jsonify({"ok": False, "error": "Falta product_code"}), 400
    if quantity_raw == "":
        return jsonify({"ok": False, "error": "Falta quantity"}), 400
    try:
        quantity = float(quantity_raw)
    except ValueError:
        return jsonify({"ok": False, "error": "Cantidad inválida"}), 400
    if quantity <= 0:
        return jsonify({"ok": False, "error": "Cantidad debe ser > 0"}), 400

    try:
        header_rows = get_inventory_operations_by_correlative(correlative, "TRANSFER", False)
        if not header_rows:
            return jsonify({"ok": False, "error": "TRANSFER no encontrada"}), 404
        header = header_rows[0]
        desc_hdr = (header.get("description") or "").strip().lower()
        if desc_hdr == "la operacion fue validada" or desc_hdr.startswith("documento chequeado"):
            return jsonify({"ok": False, "error": "Recepción ya validada. No se puede agregar."}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error verificando TRANSFER: {e}"}), 500

    try:
        rows = search_product(product_code_input) or []
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error buscando producto: {e}"}), 500
    if not rows:
        return jsonify({"ok": False, "error": "Producto no encontrado"}), 404
    prod = rows[0]
    main_code = prod.get("code")
    description = prod.get("description")
    unit_corr = prod.get("unit_correlative") or get_correlative_product_unit(main_code)

    item = {
        "product_code": main_code,
        "description": description or None,
        "quantity": quantity,
        "from_store": header.get("store"),
        "to_store": header.get("destination_store"),
        "unit": int(unit_corr) if unit_corr else 1,
        "conversion_factor": 1.0,
        "unit_type": 1,
        "unit_price": 0.0,
        "total_price": 0.0,
        "total_cost": 0.0,
        "coin_code": "02",
    }
    try:
        save_transfer_order_items(correlative, [item])
        return jsonify({"ok": True, "added": {
            "code_product": main_code,
            "description_product": description,
            "unit_description": prod.get("unit_description"),
            "amount": quantity,
        }})
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error agregando item: {e}"}), 500


@app.route("/api/reception/resolve_code", methods=["GET"])
def api_reception_resolve_code():
    correlative = request.args.get("correlative", type=int)
    print("este es el correlativo que recibo ->", correlative)
    query = (request.args.get("query") or "").strip()
    if not correlative or not query:
        return jsonify({"ok": False, "error": "Parámetros incompletos"}), 400
    try:
        headers = get_inventory_operations_by_correlative(correlative, "TRANSFER", False)
        if not headers:
            return jsonify({"ok": False, "error": "TRANSFER no encontrada"}), 404
        header = headers[0]
        # Para recepción, priorizar depósito destino; si falla, usar origen
        dest = header.get("destination_store")
        origin = header.get("store")
        rows = []
        if dest:
            try:
                rows = search_product_failure(query, dest) or []
            except Exception:
                rows = []
        if not rows and origin:
            try:
                rows = search_product_failure(query, origin) or []
            except Exception:
                rows = []
        if not rows:
            return jsonify({"ok": False, "error": "Producto no encontrado por código alterno"}), 404
        prod = rows[0]
        return jsonify({"ok": True, "product_code": prod.get("code"), "product": prod})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/collection_order/confirm_transfer", methods=["POST"])
def api_collection_order_confirm_transfer():
    """Marca la operación existente como chequeada y en espera (NO crea nueva operación)."""
    source_correlative = request.form.get("correlative", type=int)
    if not source_correlative:
        return jsonify({"ok": False, "error": "Falta correlative"}), 400

    # Obtener header y detalles de la orden de recolección
    try:
        header_rows = get_inventory_operations_by_correlative(source_correlative, "TRANSFER", True)
        if not header_rows:
            return jsonify({"ok": False, "error": "Orden de recolección no encontrada"}), 404
        header = header_rows[0]
        details = get_inventory_operations_details_by_correlative(source_correlative)
        # Si ya fue validada, bloquear doble confirmación
        desc_hdr = (header.get("description") or "").strip().lower()
        if desc_hdr == "la operacion fue validada" or desc_hdr.startswith("documento chequeado"):
            return jsonify({"ok": False, "error": "La orden ya fue validada previamente."}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error consultando orden origen: {e}"}), 500

    # Validación de seguridad: no permitir generar TRANSFER si existen productos pendientes
    # En el cliente, sólo se habilita el botón cuando todas las filas tienen conteo.
    # Para reforzar del lado servidor, exigimos que se envíe la lista completa de códigos contados
    # y validamos que cubra exactamente todos los códigos de detalle actuales.
    try:
        counted_codes_raw = (request.form.get("counted_codes") or "").strip()
        counted_codes = set(
            [c.strip() for c in counted_codes_raw.split(",") if c and c.strip()]
        )
        server_codes = set([d.get("code_product") for d in details if d.get("code_product")])
        if not details or len(server_codes) == 0:
            return jsonify({"ok": False, "error": "La orden no tiene detalles"}), 400
        if not counted_codes or counted_codes != server_codes:
            return (
                jsonify({
                    "ok": False,
                    "error": "No se puede generar TRASLADO: existen productos pendientes de conteo.",
                    "expected": sorted(list(server_codes)),
                    "received": sorted(list(counted_codes)),
                }),
                400,
            )
    except Exception as e:
        return jsonify({"ok": False, "error": f"Validación de conteo falló: {e}"}), 400

    # Nuevo flujo: NO crear nueva operación; sólo actualizar descripción de la existente.
    try:
        existing_document_no = get_document_no_inventory_operation(source_correlative)
        nueva_descripcion = (
            f"Documento chequeado, Traslado en espera automatico {existing_document_no}" if existing_document_no else "Documento chequeado, Traslado en espera automatico"
        )
        update_description_inventory_operations(source_correlative, nueva_descripcion)
        return jsonify({
            "ok": True,
            "transfer_correlative": source_correlative,
            "document_no": existing_document_no,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error actualizando descripción: {e}"}), 500

# API para resolver código alterno en TRANSFER
@app.route("/api/collection_order/resolve_code", methods=["GET"])
def api_collection_order_resolve_code():
    """Resuelve un código ingresado (posible other_code) al código principal del producto usando search_product_failure.
    Intenta con el depósito destino de la TRANSFER y, si no existe, con el depósito origen.
    """
    correlative = request.args.get("correlative", type=int)
    query = (request.args.get("query") or "").strip()
    if not correlative or not query:
        return jsonify({"ok": False, "error": "Parámetros incompletos"}), 400
    try:
        headers = get_inventory_operations_by_correlative(correlative, "TRANSFER", False)
        if not headers:
            # Intentar fallback en espera (wait=true) para diferenciar entre inexistente y no procesada
            pending_headers = get_inventory_operations_by_correlative(correlative, "TRANSFER", True)
            if pending_headers:
                return jsonify({"ok": False, "error": "TRANSFER no procesada (wait=true). No disponible para recepción.", "status": "pending"}), 409
            return jsonify({"ok": False, "error": "TRANSFER no encontrada"}), 404
        header = headers[0]
        dest = header.get("destination_store")
        origin = header.get("store")
        rows = []
        if not rows:
            try:
                rows = search_product(query) or []
            except Exception:
                rows = []

        if not rows:
            return jsonify({"ok": False, "error": "Producto no encontrado por código alterno"}), 404

        prod = rows[0]
        # Normalizar la estructura del producto para la respuesta (asegura keys comunes)
        product_response = {
            "code": prod.get("code"),
            "description": prod.get("description"),
            "unit_description": prod.get("unit_description") if prod.get("unit_description") is not None else prod.get("unit_description"),
            "unit_correlative": prod.get("unit_correlative") if prod.get("unit_correlative") is not None else prod.get("unit_correlative"),
        }
        return jsonify({"ok": True, "product_code": prod.get("code"), "product": product_response})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# API para obtener info de producto por código alterno
@app.route("/api/collection_order/product_info", methods=["GET"])
def api_collection_order_product_info():
    """Obtiene información del producto por código alterno (other_code): code, description y unidad.
    Usa search_product().
    """
    query = (request.args.get("query") or "").strip()
    if not query:
        return jsonify({"ok": False, "error": "Falta query"}), 400
    try:
        rows = search_product(query) or []
        if not rows:
            return jsonify({"ok": False, "error": "Producto no encontrado"}), 404
        p = rows[0]
        return jsonify({
            "ok": True,
            "code": p.get("code"),
            "description": p.get("description"),
            "unit_description": p.get("unit_description"),
            "unit_correlative": p.get("unit_correlative"),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/collection_order/add_item", methods=["POST"])
def api_collection_order_add_item():
    """Agrega un producto nuevo (no presente) a una ORDER_COLLECTION existente.
    Requiere: correlative, product_code, description, quantity (>0).
    Usa save_transfer_order_items reutilizando la lógica de inserción de detalles.
    """
    correlative = request.form.get("correlative", type=int)
    product_code_input = (request.form.get("product_code") or "").strip()
    quantity_raw = (request.form.get("quantity") or "").replace(",", ".")
    # Validación granular para dar feedback más claro
    if correlative is None:
        return jsonify({"ok": False, "error": "Falta correlative"}), 400
    if not product_code_input:
        return jsonify({"ok": False, "error": "Falta product_code"}), 400
    if quantity_raw == "":
        return jsonify({"ok": False, "error": "Falta quantity"}), 400
    try:
        quantity = float(quantity_raw)
    except ValueError:
        return jsonify({"ok": False, "error": "Cantidad inválida"}), 400
    if quantity <= 0:
        return jsonify({"ok": False, "error": "Cantidad debe ser > 0"}), 400

    # Obtener header para validar que existe y extraer stores
    try:
        header_rows = get_inventory_operations_by_correlative(correlative, "TRANSFER", True)
        if not header_rows:
            return jsonify({"ok": False, "error": "TRANSFER no encontrada"}), 404
        header = header_rows[0]
        # Bloquear si ya fue validada
        desc_hdr = (header.get("description") or "").strip().lower()
        if desc_hdr == "la operacion fue validada" or desc_hdr.startswith("documento chequeado"):
            return jsonify({"ok": False, "error": "Orden ya validada. No se puede agregar."}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error verificando orden: {e}"}), 500

    # Buscar info de producto usando search_product (convierte other_code -> main code)
    try:
        rows = search_product(product_code_input) or []
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error buscando producto: {e}"}), 500
    if not rows:
        return jsonify({"ok": False, "error": "Producto no encontrado"}), 404
    prod = rows[0]
    main_code = prod.get("code")
    description = prod.get("description")
    unit_corr = prod.get("unit_correlative") or get_correlative_product_unit(main_code)

    # Validación de negocio: no permitir agregar cantidad mayor a stock disponible en origen
    try:
        origin_store = header.get("store")
        available_stock = get_product_stock(main_code, origin_store) if origin_store else 0.0
        if available_stock is not None and quantity > float(available_stock) + 1e-9:
            return jsonify({
                "ok": False,
                "error": f"Cantidad solicitada ({quantity}) excede el stock disponible en origen ({available_stock})."
            }), 400
    except Exception as e:
        # Si falla la consulta de stock, devolver error claro
        return jsonify({"ok": False, "error": f"No se pudo validar stock disponible: {e}"}), 500

    # Preparar item usando los campos esperados por save_transfer_order_items
    item = {
        "product_code": main_code,
        "description": description or None,
        "quantity": quantity,
        "from_store": header.get("store"),
        "to_store": header.get("destination_store"),
        "unit": int(unit_corr) if unit_corr else 1,
        "conversion_factor": 1.0,
        "unit_type": 1,
        "unit_price": 0.0,
        "total_price": 0.0,
        "total_cost": 0.0,
        "coin_code": "02",
    }
    try:
        save_transfer_order_items(correlative, [item])
        return jsonify({"ok": True, "added": {
            "code_product": main_code,
            "description_product": description,
            "unit_description": prod.get("unit_description"),
            "amount": quantity,
        }})
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error agregando item: {e}"}), 500


@app.route("/api/collection_order/product_stock", methods=["GET"])
def api_collection_order_product_stock():
    """Devuelve el stock disponible en depósito origen para un producto de una ORDER_COLLECTION (wait=true)."""
    correlative = request.args.get("correlative", type=int)
    code = (request.args.get("code") or "").strip()
    if not correlative or not code:
        return jsonify({"ok": False, "error": "Faltan correlative o code"}), 400
    try:
        header_rows = get_inventory_operations_by_correlative(correlative, "TRANSFER", True)
        if not header_rows:
            return jsonify({"ok": False, "error": "ORDER_COLLECTION no encontrada"}), 404
        header = header_rows[0]
        origin_store = header.get("store")
        if not origin_store:
            return jsonify({"ok": False, "error": "No se pudo determinar el depósito origen"}), 400
        stock = get_product_stock(code, origin_store)
        return jsonify({"ok": True, "code": code, "store": origin_store, "stock": float(stock or 0.0)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    # app.run(debug=True, host="0.0.0.0", port=os.environ.get("APP_PORT", 5002))
   #Servidor WSGI de producción (waitress) si está disponible; si no, fallback a Flask
    host = os.environ.get("REPOSTOCK_HOST", "0.0.0.0")
    try:
        port = int(os.environ.get("APP_PORT", "5001"))
    except Exception:
        port = 5001

    use_waitress = str(os.environ.get("REPOSTOCK_USE_WAITRESS", "1")).lower() in ("1", "true", "yes", "y")
    if use_waitress:
        try:
            from waitress import serve
            threads = int(os.environ.get("REPOSTOCK_THREADS", "8"))
            print(f"Iniciando servidor de producción (waitress) en {host}:{port} con {threads} hilos...")
            serve(app, host=host, port=port, threads=threads)
        except Exception as e:
            print(f"No se pudo iniciar waitress ({e}). Iniciando servidor de desarrollo Flask...")
            app.run(debug=False, host=host, port=port)
    else:
        debug = str(os.environ.get("FLASK_DEBUG", "0")).lower() in ("1", "true", "yes", "y")
        print(f"Iniciando servidor Flask debug={debug} en {host}:{port} ...")
        app.run(debug=debug, host=host, port=port)
