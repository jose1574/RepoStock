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
# importar funciones de la base de datos
from db import (
    get_stores,
    search_product,
    save_product_failure,
    get_store_by_code,
    get_collection_products,
    save_transfer_order_in_wait,
    save_transfer_order_items,
    get_products_by_codes,
    get_correlative_product_unit,
    get_store_by_code,
    get_departments,
    search_product_failure,
    get_inventory_operations_by_correlative,
    get_inventory_operations_details_by_correlative,
    update_description_inventory_operations,
    get_document_no_inventory_operation
)


if getattr(sys, "frozen", False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

template_folder = os.path.join(base_path, "templates")

env_path = os.path.join(base_path, ".env")
# Carga el .env forzando UTF-8 para evitar problemas de codificación en Windows
try:
    load_dotenv(env_path, encoding="utf-8")
except TypeError:
    # Para compatibilidad con versiones antiguas de python-dotenv sin parámetro encoding
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
        operation_type = request.form.get("operation_type", default="TRANSFER", type=str)
        wait_param = request.form.get("wait", default="true", type=str)
        wait = True if (str(wait_param).lower() in ("1", "true", "yes", "y")) else False
    else:
        correlative = request.args.get("correlative", default=None, type=int)
        operation_type = request.args.get("operation_type", default="TRANSFER", type=str)
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
        details = get_inventory_operations_details_by_correlative(correlative)
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
    print("estos son los datos del Header del reporte: ", header)
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
                "to_store": (
                    store_stock_destination or prod.get("store")
                    if prod
                    else store_stock_destination
                ),
                # valores por defecto para campos opcionales que espera la función
                "unit": get_correlative_product_unit(code),
                "conversion_factor": 1.0,
                "unit_type": 1,
                "unit_price": 0.0,
                "total_price": 0.0,
                "total_cost": 0.0,
                "coin_code": "02",
                "to_store": session.get("store_code_destination", None),
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
            order_id = save_transfer_order_in_wait(transfer_data)
            document_no = get_document_no_inventory_operation(order_id)
            update_description_inventory_operations(order_id, f"Orden de traslado automatico No: {document_no}")

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
                url_for("collection_preview_pdf", correlative=order_id, wait="true", operation_type="TRANSFER")
            )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5002)
    # Servidor WSGI de producción (waitress) si está disponible; si no, fallback a Flask
    # host = os.environ.get("REPOSTOCK_HOST", "0.0.0.0")
    # try:
    #     port = int(os.environ.get("REPOSTOCK_PORT", "5001"))
    # except Exception:
    #     port = 5001

    # use_waitress = str(os.environ.get("REPOSTOCK_USE_WAITRESS", "1")).lower() in ("1", "true", "yes", "y")
    # if use_waitress:
    #     try:
    #         from waitress import serve
    #         threads = int(os.environ.get("REPOSTOCK_THREADS", "8"))
    #         print(f"Iniciando servidor de producción (waitress) en {host}:{port} con {threads} hilos...")
    #         serve(app, host=host, port=port, threads=threads)
    #     except Exception as e:
    #         print(f"No se pudo iniciar waitress ({e}). Iniciando servidor de desarrollo Flask...")
    #         app.run(debug=False, host=host, port=port)
    # else:
    #     debug = str(os.environ.get("FLASK_DEBUG", "0")).lower() in ("1", "true", "yes", "y")
    #     print(f"Iniciando servidor Flask debug={debug} en {host}:{port} ...")
    #     app.run(debug=debug, host=host, port=port)
