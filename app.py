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
import pdfkit


# Robust loader for .env files: intenta UTF-8, UTF-8-SIG y latin-1 como fallback.
def safe_load_dotenv(path, override=False):
    """Carga un .env intentando varias codificaciones para evitar UnicodeDecodeError.

    - Primero intenta `load_dotenv` con 'utf-8' y 'utf-8-sig'.
    - Si falla por UnicodeDecodeError, intenta leer en 'latin-1' y parsear manualmente.
    - Nunca lanza excepciones; retorna True si cargó algo, False en caso contrario.
    """
    if not path or not os.path.exists(path):
        return False
    tried = []
    encodings = ["utf-8", "utf-8-sig"]
    for enc in encodings:
        try:
            # python-dotenv acepta encoding en versiones recientes
            try:
                load_dotenv(path, encoding=enc, override=override)
            except TypeError:
                # versiones antiguas no soportan encoding kw
                load_dotenv(path, override=override)
            return True
        except UnicodeDecodeError:
            tried.append(enc)
            continue
        except Exception:
            # otras excepciones (permiso, I/O) no las manejamos aquí
            break

    # Fallback: intentar leer con latin-1 y parsear líneas manualmente
    try:
        with open(path, 'rb') as f:
            raw = f.read()
        # decodificar con latin-1 para preservar bytes sin fallar
        txt = raw.decode('latin-1')
        for line in txt.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            k, v = line.split('=', 1)
            k = k.strip()
            v = v.strip()
            # remover comillas simples/dobles
            if len(v) >= 2 and ((v[0] == '"' and v[-1] == '"') or (v[0] == "'" and v[-1] == "'")):
                v = v[1:-1]
            # Si override es True, siempre setear; sino, solo si no existe
            if override or (k not in os.environ):
                try:
                    os.environ[k] = v
                except Exception:
                    pass
        return True
    except Exception:
        return False

# Determinar paths base y cargar .env ANTES de importar `db` o los blueprints
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
            safe_load_dotenv(external_env, override=True)
    except Exception:
        pass

# Carga el .env embebido (no sobrescribe claves ya definidas por el externo)
safe_load_dotenv(env_path, override=False)

# importar funciones de la base de datos (después de cargar .env)
from db import (
    get_store_by_code,
    search_product_failure,
    search_product,
    get_product_stock_by_store,
    search_products_with_stock_and_price,
    get_product_price_and_unit,
    insert_product_image,
    get_product_images,
    delete_product_image,
    login_user,
)

try:
    import pdfkit
except Exception:
    pdfkit = None

# Registrar blueprints / módulos después de tener variables de entorno y db importado
from modules import (
    inventory, 
    sales, 
    manager,
    systems,
    shopping,
)


app = Flask(__name__, template_folder=template_folder)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "root1574**")

## aqui registro todos los modulos blueprints
# Registrar blueprint de inventory
app.register_blueprint(inventory.inventory_bp)

# Registra blieprint de manager_bp
app.register_blueprint(manager.manager_bp)

# Registrar blueprint de sales
app.register_blueprint(sales.sales_bp)

# Registrar blueprint de systems
app.register_blueprint(systems.systems_bp)

#Registrar blueprint de shopping
app.register_blueprint(shopping.shopping_bp)

# Protección global: redirige a login si no hay usuario en sesión.
# Excepciones: endpoint 'login' y archivos estáticos.
@app.before_request
def require_login():
    try:
        ep = (request.endpoint or "")
    except Exception:
        ep = ""
    # permitir acceso a login y recursos estáticos
    public_endpoints = {"login", "static"}
    if ep in public_endpoints:
        return None
    # permitir favicon
    if request.path.startswith("/favicon.ico"):
        return None
    # si ya hay sesión, permitir
    if session.get("user"):
        return None
    # de lo contrario redirigir a login con next
    return redirect(url_for("login", next=request.path))

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


@app.route("/logout")
def logout():
    """Cierra la sesión del usuario y muestra el formulario de login.

    Si había un usuario en sesión, intentamos pasar su código al template
    para precargar el campo `username` en el formulario de login.
    """
    user = session.get("user")
    # Obtener posible nombre/código para prefill
    username = None
    try:
        if isinstance(user, dict):
            username = user.get("code") or user.get("description")
    except Exception:
        username = None
    # Eliminar solo la información de usuario (no tocar otras claves de sesión)
    session.pop("user_code", None)
    session.pop("user_description", None)
    session.pop("user", None)
    return render_template("login.html", username=username)


@app.route("/")
def index():
    user_code = session.get("user_code")
    user_description = session.get("user_description")
    print("Usuario en sesión:", user_code, user_description)
    return render_template("index.html")
@app.route("/product_images", methods=["GET", "POST"])


def product_images():
    product = None
    store = None
    images = []
    stocks_by_store = []
    # Usar depósito de sesión si existe
    session_store_code = session.get("store") or session.get("store_code_destination") or os.environ.get("DEFAULT_STORE_ORIGIN_CODE")
    if session_store_code:
        store = get_store_by_code(session_store_code)
    if request.method == "POST":
        query = (request.form.get("product_query") or "").strip()
        if query:
            try:
                rows = search_product_failure(query, session_store_code) or []
                if not rows:
                    rows = search_product(query) or []
                if rows:
                    product = rows[0]
                    # Enriquecer con precio y unidad principal
                    try:
                        price_info = get_product_price_and_unit(product.get("code"))
                        if price_info:
                            product["offer_price"] = price_info.get("offer_price")
                            # No pisar unit_description si ya viene desde search_product
                            if product.get("unit_description") in (None, ""):
                                product["unit_description"] = price_info.get("unit_description")
                    except Exception as e:
                        print("Error obteniendo precio del producto:", e)
                    images = get_product_images(product.get("code")) or []
                    try:
                        stocks_by_store = get_product_stock_by_store(product.get("code")) or []
                    except Exception as e:
                        print("Error obteniendo stock por depósito:", e)
            except Exception as e:
                print("Error buscando producto para imágenes:", e)
    return render_template("product_images.html", product=product, store=store, images=images, stocks_by_store=stocks_by_store)


@app.route("/api/products/search", methods=["GET"])
def api_products_search():
    """Busca productos y devuelve JSON con código, descripción, stock total y precio (offer_price)."""
    q = (request.args.get("q") or "").strip()
    try:
        rows = search_products_with_stock_and_price(q) or []
        return jsonify({"ok": True, "items": rows})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/product_images/upload", methods=["POST"])
def upload_product_image():
    product_code = (request.form.get("product_code") or "").strip().upper()
    if not product_code:
        return redirect(url_for("product_images"))
    file = request.files.get("camera_file") or request.files.get("image_file")
    if not file or file.filename == "":
        return redirect(url_for("product_images"))
    try:
        data = file.read()
        mime_type = file.mimetype or "application/octet-stream"
        filename = file.filename
        size_bytes = len(data) if data else 0
        is_primary = True if (request.form.get("is_primary") in ("1", "true", "on")) else False
        insert_product_image({
            "product_code": product_code,
            "image_data": data,
            "filename": filename,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "is_primary": is_primary,
        })
    except Exception as e:
        print("Error guardando imagen:", e)
    return redirect(url_for("product_images"))

@app.route("/product_images/raw/<int:image_id>", methods=["GET"])
def product_image_raw(image_id: int):
    try:
        rows = get_product_images(image_id=image_id) or []
        img = rows[0] if rows else None
        if not img:
            return "Imagen no encontrada", 404
        from flask import make_response
        payload = img.get("image_data")
        try:
            # Asegurar tipo bytes (psycopg2 puede devolver memoryview)
            if isinstance(payload, memoryview):
                payload = payload.tobytes()
        except NameError:
            # memoryview no definido en algunos runtimes, intentar conversión directa
            try:
                payload = bytes(payload) if payload is not None else b""
            except Exception:
                payload = payload or b""

        # Detección y decodificación de contenido base64 almacenado como texto en bytea
        # Esto permite mostrar imágenes importadas erróneamente como cadena base64.
        def _looks_like_base64(b: bytes) -> bool:
            if not b or len(b) < 32:
                return False
            # Evitar datos ya binarios (cabeceras típicas de archivos de imagen)
            if b[:2] in (b"\xFF\xD8", b"\x89P") or b[:4] in (b"GIF8", b"RIFF"):
                return False
            try:
                txt = b.decode("ascii")
            except Exception:
                return False
            # Solo caracteres base64 permitidos + '='
            for ch in txt.strip():
                if ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\n\r":
                    return False
            # Longitud múltiplo de 4 tras eliminar saltos
            core = "".join([c for c in txt if c not in "\n\r"])
            if len(core) % 4 != 0:
                return False
            # Debe terminar con '=', '==', o sin padding pero decodable
            return True

        if isinstance(payload, bytes) and _looks_like_base64(payload):
            import base64
            # Normalizar: quitar saltos de línea
            cleaned = b"".join(line for line in payload.splitlines())
            try:
                decoded = base64.b64decode(cleaned, validate=False)
                # Heurística de tipo MIME si el existente es genérico
                mime = (img.get("mime_type") or "application/octet-stream").lower()
                if mime in ("text/plain", "application/octet-stream", "binary/octet-stream"):
                    if decoded.startswith(b"\xFF\xD8\xFF"):
                        mime = "image/jpeg"
                    elif decoded.startswith(b"\x89PNG\r\n\x1a\n"):
                        mime = "image/png"
                    elif decoded.startswith(b"GIF89a") or decoded.startswith(b"GIF87a"):
                        mime = "image/gif"
                    elif decoded.startswith(b"RIFF") and b"WEBP" in decoded[:32]:
                        mime = "image/webp"
                payload = decoded
                img["mime_type"] = mime
            except Exception as e:
                print(f"Fallo al decodificar base64 imagen_id={image_id}: {e}")

        resp = make_response(payload or b"")
        resp.headers["Content-Type"] = img.get("mime_type") or "image/jpeg"
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp
    except Exception as e:
        return f"Error obteniendo imagen: {e}", 500


@app.route("/product_images/delete", methods=["POST"])
def delete_product_images_route():
    """Elimina una o varias imágenes por ID y redirige o devuelve JSON."""
    # Aceptar ids desde formulario o JSON
    ids = []
    try:
        if request.is_json:
            data = request.get_json(silent=True) or {}
            raw = data.get("image_ids") or data.get("ids")
            if isinstance(raw, list):
                ids = [int(x) for x in raw if str(x).isdigit()]
            elif raw is not None and str(raw).isdigit():
                ids = [int(raw)]
        else:
            form_ids = request.form.getlist("image_ids")
            if form_ids:
                ids = [int(x) for x in form_ids if str(x).isdigit()]
            else:
                single = request.form.get("image_id")
                if single and str(single).isdigit():
                    ids = [int(single)]
    except Exception:
        ids = []

    if not ids:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "error": "No se recibieron IDs"}), 400
        return redirect(url_for("product_images"))

    deleted = []
    errors = []
    for image_id in ids:
        try:
            delete_product_image(image_id)
            deleted.append(image_id)
        except Exception as e:
            errors.append({"id": image_id, "error": str(e)})

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "deleted": deleted, "errors": errors})
    return redirect(url_for("product_images"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    # POST
    user_code = (request.form.get("user_code") or "").strip()
    password = (request.form.get("password") or "").strip()
    print("Intento de login usuario:", user_code, "...", password)
    # Validación contra la base de datos
    user = login_user(user_code, password)
    session["user"] = user
    if user:
        try:
            # Almacenar información mínima del usuario en sesión
            session.permanent = True
            session["user"] = user
            session["user_code"] = user.get("code")
        except Exception:
            pass

        # Soportar parámetro `next` (form o query) para redirección posterior al login
        next_url = request.args.get("next") or request.form.get("next")
        if not next_url:
            return redirect(url_for("index"))
        # Evitar redirección abierta: solo rutas internas
        if next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for("index"))

    # credenciales inválidas
    return render_template("login.html", error="usuario o contraseña incorrectos", user_code=user_code)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=os.environ.get("APP_PORT", 5002))
#    Servidor WSGI de producción (waitress) si está disponible; si no, fallback a Flask
    # host = os.environ.get("REPOSTOCK_HOST", "0.0.0.0")
    # try:
    #     port = int(os.environ.get("APP_PORT", "5001"))
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
