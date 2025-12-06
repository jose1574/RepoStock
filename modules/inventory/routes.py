import os
import json
import datetime
from flask import (
    Blueprint,
    redirect,
    render_template,
    render_template_string,
    request,
    jsonify,
    session,
    url_for,
    make_response,
)
try:
    import pdfkit
except Exception:
    pdfkit = None

# Configuración local de wkhtmltopdf para evitar import circular con app.py
WKHTMLTOPDF_BIN = os.environ.get("WKHTMLTOPDF_BIN")
if not WKHTMLTOPDF_BIN:
    for p in [
        r"C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe",
        r"C:\\Program Files (x86)\\wkhtmltopdf\\bin\\wkhtmltopdf.exe",
    ]:
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
from db import get_collection_products, get_correlative_product_unit, get_document_no_inventory_operation, get_inventory_operations_by_correlative, get_inventory_operations_details_by_correlative, get_product_stock, get_products_by_codes, get_store_by_code, get_stores, save_product_failure, save_transfer_order_in_wait, save_transfer_order_items, search_product, search_product_failure, search_products_with_stock_and_price, update_description_inventory_operations, update_inventory_operation_detail_amount, update_minmax_product_failure, get_product_with_all_units
from db import get_product_by_code_or_other_code

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")
# Directorio de templates específico del módulo
inventory_bp.template_folder = os.path.join(os.path.dirname(__file__), "templates")

@inventory_bp.route('/select_store_destination_collection_order', methods=['GET'])
def select_store_destination_collection_order():
    stores = get_stores()
    return render_template("form_destination_store.html", stores=stores)


@inventory_bp.route("/create_collection_order", methods=["POST", "GET"])
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



@inventory_bp.route("/save_collection_order", methods=["POST"])
def save_collection_order():
    if request.method == "POST":
        # Si el formulario envía un store_code_destination, actualizar la sesión
        if request.form.get('store_code_destination'):
            session['store_code_destination'] = request.form.get('store_code_destination')
        
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
            # intentar usar unidad enviada por el formulario (unit_for_{code})
            unit_raw = request.form.get(f"unit_for_{code}")
            try:
                unit_val = int(unit_raw) if unit_raw is not None and str(unit_raw).strip() != '' else get_correlative_product_unit(code)
            except Exception:
                unit_val = get_correlative_product_unit(code)

            item = {
                "product_code": code,
                "description": prod.get("description") if prod else None,
                "quantity": qty,
                "from_store": stock_store_origin,
                "to_store": store_stock_destination,
                # valores por defecto para campos opcionales que espera la función
                "unit": int(unit_val) if unit_val else get_correlative_product_unit(code),
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
            return redirect(url_for("inventory.create_collection_order"))

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
        print("esto es lo que voy a guardar: ", transfer_data, items)
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
            return redirect(url_for("inventory.create_collection_order"))

        return redirect(
            url_for(
                "inventory.collection_preview_pdf",
                correlative=order_id,
                wait="true",
                operation_type="TRANSFER",
            )
        )



@inventory_bp.route("/destination-store-selection")
def destination_store_selection_param_product():
    stores = get_stores()
    return render_template(
        "destination_store_selection_param_product.html", stores=stores
    )

@inventory_bp.route("/api/products/search", methods=["GET"])
def api_products_search():
    """Busca productos y devuelve JSON con código, descripción, stock total y precio (offer_price)."""
    q = (request.args.get("q") or "").strip()
    # soportar paginación
    try:
        limit = int(request.args.get('limit', 50))
    except Exception:
        limit = 50
    try:
        offset = int(request.args.get('offset', 0))
    except Exception:
        offset = 0

    try:
        # Determinar depósito origen: priorizar parámetro 'store', luego sesión, luego env var
        store_param = (request.args.get('store') or session.get('store_manual_collection_order_origin') or os.environ.get('DEFAULT_STORE_ORIGIN_CODE') or '').strip()
        # Intentar llamar a la función DB con paginación si la implementa
        try:
            rows_and_total = search_products_with_stock_and_price(q, limit=limit, offset=offset, store_code=store_param)
            print(f"[api_products_search] q={q!r} limit={limit} offset={offset} -> call DB returned type={type(rows_and_total)}")
            # Si la función devuelve dict {'items':..., 'total':...}
            if isinstance(rows_and_total, dict) and 'items' in rows_and_total:
                print(f"[api_products_search] items={len(rows_and_total.get('items', []))} total={rows_and_total.get('total')}")
                return jsonify({"ok": True, "items": rows_and_total.get('items', []), "total": rows_and_total.get('total', None)})
            # Si devuelve una tupla (items, total)
            if isinstance(rows_and_total, (list, tuple)) and len(rows_and_total) == 2:
                print(f"[api_products_search] items tuple len={len(rows_and_total[0])} total={rows_and_total[1]}")
                items, total = rows_and_total
                return jsonify({"ok": True, "items": items or [], "total": total})
            # Si devuelve sólo lista
            if isinstance(rows_and_total, list):
                items = rows_and_total
                total = len(items)
                # aplicar slicing por si la función no aplicó limit/offset
                sliced = items[offset: offset+limit]
                print(f"[api_products_search] DB returned list len={len(items)} -> slicing {offset}:{offset+limit} -> {len(sliced)}")
                return jsonify({"ok": True, "items": sliced, "total": total})

        except TypeError:
            # función no soporta params; llamar sin params y paginar aquí
            # (fallback) incluir store si la función lo soporta
            rows = search_products_with_stock_and_price(q, store_code=store_param) or []
            print(f"[api_products_search] fallback call returned {len(rows)} rows; offset={offset} limit={limit}")
            total = len(rows)
            items = rows[offset: offset+limit]
            return jsonify({"ok": True, "items": items, "total": total})

        # fallback si no entra en los casos anteriores
        return jsonify({"ok": True, "items": [], "total": 0})
    except Exception as e:
        print(f"[api_products_search] EXCEPTION: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@inventory_bp.route("/api/product_failure/get_minmax", methods=["GET"])
def api_get_minmax_product_failure():
    """Devuelve minimal_stock y maximum_stock para un producto en un depósito destino.
    Si no existe registro en products_failures retorna valores None.
    Parámetros:
      - product_code (str)
      - store_code (str, opcional si existe en session['store_code_destination'])
    """
    product_code = request.args.get("product_code")
    if product_code:
        product_code = product_code.strip().upper()
    store_code = request.args.get("store_code") or session.get("store_code_destination")
    if store_code:
        store_code = str(store_code).strip().upper()
    if not product_code or not store_code:
        return jsonify({"ok": False, "error": "Faltan product_code o store_code"}), 400
    try:
        rows = search_product_failure(product_code, store_code) or []
        minimal_stock = None
        maximum_stock = None
        if rows:
            r = rows[0]
            minimal_stock = r.get("minimal_stock")
            maximum_stock = r.get("maximum_stock")
        return jsonify({
            "ok": True,
            "product_code": product_code,
            "store_code": store_code,
            "minimal_stock": minimal_stock,
            "maximum_stock": maximum_stock
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@inventory_bp.route("/check_order_collection", methods=["GET"])
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
        except Exception as e:
            print("Error cargando ORDER_COLLECTION:", e)
    return render_template("check_order_collection.html", correlative=correlative, header=header, items=details, validated=validated)


@inventory_bp.route("/api/collection_order/product_info", methods=["GET"])
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


@inventory_bp.route("/api/products/get-by-code", methods=["GET"])
def api_get_product_by_code():
    """Busca un producto directamente por código principal o código alterno (other_code).

    Parámetro query: código a buscar
    Retorna JSON: {ok: True, product: {...}} o 404 si no se encuentra
    """
    code = (request.args.get("code") or request.args.get("query") or "").strip()
    if not code:
        return jsonify({"ok": False, "error": "Falta code"}), 400
    try:
        prod = get_product_by_code_or_other_code(code)
        if not prod:
            return jsonify({"ok": False, "error": "Producto no encontrado"}), 404
        return jsonify({"ok": True, "product": prod})
    except Exception as e:
        print("[api_get_product_by_code] ERROR:", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@inventory_bp.route("/api/products/get-by-code-all-units", methods=["GET"])
def api_get_product_by_code_all_units():
    """Busca un producto por código principal u other_code y devuelve todas las unidades.

    Útil cuando la UI necesita listar unidades alternas sin que la consulta inicial filtre por main_unit.
    """
    code = (request.args.get("code") or request.args.get("query") or "").strip()
    if not code:
        return jsonify({"ok": False, "error": "Falta code"}), 400
    try:
        prod = get_product_with_all_units(code)
        if not prod:
            return jsonify({"ok": False, "error": "Producto no encontrado"}), 404
        return jsonify({"ok": True, "product": prod})
    except Exception as e:
        print("[api_get_product_by_code_all_units] ERROR:", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@inventory_bp.route("/api/products/stocks-by-product", methods=["GET"])
def api_products_stocks_by_product():
    """Devuelve el stock por depósito para un producto dado.

    Parámetros: `code` o `query` (código de producto)
    Retorna: { ok: True, code: ..., stocks: [ {store_code, store_description, stock}, ... ] }
    """
    code = (request.args.get("code") or request.args.get("query") or "").strip()
    if not code:
        return jsonify({"ok": False, "error": "Falta code"}), 400
    try:
        # Preferir override en sesión (wizard) si existe
        origin_code = (session.get('store_manual_collection_order_origin') or os.environ.get("DEFAULT_STORE_ORIGIN_CODE") or "").strip()
        stores = get_stores() or []
        result = []
        for s in stores:
            # intentar detectar el código y la descripción según las claves disponibles
            scode = (s.get("code") or s.get("store_code") or s.get("store") or s.get("codigo") or "").strip()
            sdesc = s.get("description") or s.get("name") or s.get("description_store") or scode
            try:
                stock = get_product_stock(code, scode) or 0
            except Exception:
                stock = 0
            try:
                stock_val = float(stock)
            except Exception:
                stock_val = 0.0
            result.append({"store_code": scode, "store_description": sdesc, "stock": stock_val, "is_origin": (str(scode) == str(origin_code))})

        # Ordenar: primero el depósito origen (si existe), luego el resto alphabeticamente por store_description
        def sort_key(item):
            # item with is_origin True should come first -> sort key False (0)
            return (not item.get("is_origin", False), (item.get("store_description") or "").lower())

        result.sort(key=sort_key)
        return jsonify({"ok": True, "code": code, "stocks": result})
    except Exception as e:
        print("[api_products_stocks_by_product] ERROR:", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@inventory_bp.route("/api/collection_order/update_count", methods=["POST"])
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


@inventory_bp.route("/api/collection_order/confirm_transfer", methods=["POST"])
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

@inventory_bp.route("/api/collection_order/product_stock", methods=["GET"])
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



@inventory_bp.route("/api/collection_order/delete_item", methods=["POST"])
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


@inventory_bp.route("/api/collection_order/add_item", methods=["POST"])
def api_collection_order_add_item():
    """Agrega un producto nuevo (no presente) a una ORDER_COLLECTION existente.
    Requiere: correlative, product_code, description, quantity (>0).
    Usa save_transfer_order_items reutilizando la lógica de inserción de detalles.
    """
    correlative = request.form.get("correlative", type=int)
    product_code_input = (request.form.get("product_code") or "").strip()
    quantity_raw = (request.form.get("quantity") or "").replace(",", ".")
    #Validación granular para dar feedback más claro
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



@inventory_bp.route("/api/product_failure/minmax", methods=["POST"])
def api_update_minmax_product_failure():
    """Actualiza mínimo y máximo para un producto/depósito. Devuelve JSON.
    Usa el depósito desde sesión (session['store']) si no se envía store_code explícito.
    """
    product_code = request.form.get("product_code")
    # Normalizar a MAYÚSCULAS para consistencia con la base
    if product_code:
        product_code = product_code.strip().upper()
    # Permitir recibir store_code explícito (fallback a sesión) y normalizar a MAYÚSCULAS
    store_code = request.form.get("store_code")
    if store_code:
        store_code = str(store_code).strip().upper()
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


@inventory_bp.route("/api/reception/resolve_code", methods=["GET"])
def api_reception_resolve_code():
    correlative = request.args.get("correlative", type=int)
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


@inventory_bp.route("/api/reception/confirm", methods=["POST"])
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


@inventory_bp.route("/check_transfer_reception", methods=["GET"])
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
                details = get_inventory_operations_details_by_correlative(correlative)
                # Ignorar estado de descripción para permitir múltiples validaciones
                print("esto es el detalle: ", details)
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


@inventory_bp.route("/api/reception/update_count", methods=["POST"])
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


@inventory_bp.route("/collection/preview.pdf", methods=["POST", "GET"])
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

    base_path = os.path.dirname(os.path.abspath(__file__))
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

    resp = make_response(pdf)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = (
        'inline; filename="orden_recoleccion_preview.pdf"'
    )
    return resp



@inventory_bp.route("/config_param_product_store")
def config_param_product_store():
    stores = get_stores()
    return render_template("config_param_product_store.html", stores=stores)

@inventory_bp.route("/config_param_product", methods=["POST"])
def config_param_product():
    # Inicializar valores por defecto
    product = None
    search_store = None
    product_not_found = False

    # Recuperar el código de store de la sesión (si existe)
    session_store_code = session.get("store")
    if isinstance(session_store_code, str):
        session_store_code = session_store_code.strip()

    product_stock = None
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
            if product:
                try:
                    product_stock = get_product_stock(product_code, session_store_code)
                except Exception:
                    product_stock = None
            else:
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
        product_stock=product_stock,
    )

@inventory_bp.route("/save_config_param_product", methods=["POST"])
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
            return redirect(url_for("inventory.config_param_product"))

        try:
            # save_product_failure espera un dict con las claves usadas en db.py
            save_product_failure(data)
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return (
                    jsonify({"ok": True, "message": "Producto guardado correctamente"}),
                    200,
                )
            return redirect(url_for("inventory.config_param_product"))
        except Exception as e:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"ok": False, "error": str(e)}), 500
            # En no-AJAX redirigir mostrando el error en logs; podrías usar flash para mostrar al usuario
            print("Error guardando parámetros:", e)
            return redirect(url_for("inventory.config_param_product"))


@inventory_bp.route("/form_destination_store_for_location", methods=["POST", "GET"])
def form_destination_store_for_location():
    stores = get_stores()
    return render_template("form_destination_store_for_location.html", stores=stores )



@inventory_bp.route("/save_session_select_store_destination_for_location", methods=["POST", "GET"])
def save_session_select_store_destination_for_location():
    store_code = session.get("store_location")
    store = get_store_by_code(store_code)
    print("store_code ->", store)
    store_location = request.form.get("store_code_location")

    session['store_location'] = store_location
    return redirect(url_for("inventory.update_locations_products_failures_products", store_code=store_location))

@inventory_bp.route("/update_location_products", methods=["POST"])
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
                        update_locations_products_failures(
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


@inventory_bp.route("/update_locations_products_failures", methods=["GET", "POST"])
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


@inventory_bp.route("/clear", methods=["POST"])
def clear():
    store_code = session.get("store_location")
    session.pop("products", None)
    session.pop("location", None)
    return redirect(url_for("inventory.update_locations_products_failures_products", store_code=store_code))


# Eliminar ítem de la sesión por código
def delete_item_product_session(code):
    session_products = session.get("products", [])
    session_products = [p for p in session_products if p.get("code") != code]
    session["products"] = session_products


@inventory_bp.route("/update_location_products_failures", methods=["GET", "POST"])
@inventory_bp.route("/<store_code>/update_location_products_failures", methods=["GET", "POST"])
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
        return redirect(url_for("inventory.update_locations_products_failures", store_code=store_code))

    # GET: mostrar siempre el depósito y la ubicación actual (si existe)
    return render_template(
        "form_location.html",
        store=store,
        location=session.get("location", ""),
    )

@inventory_bp.route("/delete_product/<code>", methods=["POST"])
def delete_product(code):
    delete_item_product_session(code)
    return redirect(url_for("inventory.update_locations_products_failures"))

#crea orden de recollecion manual
@inventory_bp.route('/products-modal')
def products_modal():
    """Devuelve el partial HTML del modal de búsqueda de productos."""
    store_code = os.environ.get("DEFAULT_STORE_ORIGIN_CODE")
    store = get_store_by_code(store_code)
    return render_template("partials/products_search_inventory_modal.html", store=store)



@inventory_bp.route('/api/manual_collection_order/set_stores', methods=['POST'])
def api_manual_collection_order_set_stores():
    """API AJAX para establecer depósito origen y destino para la creación manual.

    Espera form-encoded o JSON con keys: origin (store code) y destination (store code).
    Guarda en sesión:
      - session['store_manual_collection_order_origin'] = origin
      - session['store_manual_collection_order'] = destination
    Retorna JSON {ok: True}.
    """
    try:
        origin = request.form.get('origin') or (request.get_json(silent=True) or {}).get('origin')
        destination = request.form.get('destination') or (request.get_json(silent=True) or {}).get('destination')
        if origin:
            session['store_manual_collection_order_origin'] = origin
        if destination:
            session['store_manual_collection_order'] = destination
        return jsonify({'ok': True, 'origin': origin, 'destination': destination})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@inventory_bp.route("/select_store/manual_collection_order", methods=['GET', 'POST'])
def select_store_manual_collection_order():
    """Wizard: seleccionar depósito origen y destino antes de crear una orden manual.

    GET: mostrar formulario con selects de origen y destino.
    POST: guardar selección en sesión y redirigir a `manual_collection_order`.
    """
    stores = get_stores()
    if request.method == 'POST':
        origin = (request.form.get('origin') or '').strip()
        destination = (request.form.get('destination') or '').strip()
        # Validación: exigir ambos valores y que no sean iguales
        if not origin or not destination:
            error = 'Debe seleccionar depósito origen y destino para continuar.'
            return render_template("wizard_select_stores_manual.html", stores=stores, error=error, sel_origin=origin, sel_destination=destination)
        if origin == destination:
            error = 'El depósito de origen y destino no pueden ser el mismo.'
            return render_template("wizard_select_stores_manual.html", stores=stores, error=error, sel_origin=origin, sel_destination=destination)
        # Guardar en sesión y continuar
        session['store_manual_collection_order_origin'] = origin
        session['store_manual_collection_order'] = destination
        return redirect(url_for('inventory.manual_collection_order'))
    return render_template("wizard_select_stores_manual.html", stores=stores)





@inventory_bp.route("/manual_collection_order", methods=['GET', 'POST'])
def manual_collection_order():
    """Pantalla para crear orden de recolección manual.

    - `store_origin` se obtiene por defecto desde la variable de entorno
      `DEFAULT_STORE_ORIGIN_CODE` (leer con `get_store_by_code`).
    - `store_destination` se obtiene desde `session['store_manual_collection_order']` si existe.
    """
    # origen por defecto: permitir override por sesión, si existe usarlo
    store_origin_code = session.get('store_manual_collection_order_origin') or os.environ.get("DEFAULT_STORE_ORIGIN_CODE")
    store_origin = get_store_by_code(store_origin_code) if store_origin_code else None

    # lista de stores para el wizard (selección de origen/destino)
    stores = get_stores()

    # destino desde sesión por defecto
    store_destination = get_store_by_code(session.get('store_manual_collection_order')) if session.get('store_manual_collection_order') else None

    # permitir actualizar destino por POST
    if request.method == 'POST':
        store_destination_code = request.form.get("store_code_destination")
        if store_destination_code:
            session['store_manual_collection_order'] = store_destination_code
            store_destination = get_store_by_code(store_destination_code)

    return render_template(
        "manual_collection_order.html",
        store_origin=store_origin,
        store_destination=store_destination,
        destination_store_code=session.get('store_manual_collection_order'),
        origin_store_code=store_origin_code,
        stores=stores,
    )


@inventory_bp.route('/manual_collection_order/create', methods=['POST'])
def manual_collection_order_create():
    """Crear ORDER_COLLECTION desde la UI manual y redirigir al PDF de la orden creada."""
    selected = request.form.getlist('selected_products')
    product_codes = [c for c in selected if c]
    products_info = ({p['code']: p for p in get_products_by_codes(product_codes)} if product_codes else {})

    stock_store_origin = request.form.get('stock_store_origin') or os.environ.get('DEFAULT_STORE_ORIGIN_CODE', '01')
    store_stock_destination = session.get('store_manual_collection_order') or session.get('store_code_destination')

    items = []
    for code in product_codes:
        raw = request.form.get(f'to_transfer_{code}', '0')
        if isinstance(raw, str):
            raw = raw.replace(',', '.')
        try:
            qty = float(raw)
        except Exception:
            qty = 0.0
        if qty <= 0:
            continue

        unit_raw = request.form.get(f'unit_for_{code}')
        try:
            unit_corr = int(unit_raw) if unit_raw and str(unit_raw).strip() != '' else get_correlative_product_unit(code)
        except Exception:
            unit_corr = get_correlative_product_unit(code)

        prod = products_info.get(code, {})
        item = {
            'product_code': code,
            'description': prod.get('description') if prod else None,
            'quantity': qty,
            'from_store': stock_store_origin,
            'to_store': store_stock_destination,
            'unit': int(unit_corr) if unit_corr else 1,
            'conversion_factor': 1.0,
            'unit_type': 1,
            'unit_price': 0.0,
            'total_price': 0.0,
            'total_cost': 0.0,
            'coin_code': '02',
        }
        items.append(item)

    if not items:
        print('No hay items válidos para procesar (manual)')
        return redirect(url_for('inventory.manual_collection_order'))

    transfer_data = {
        'emission_date': datetime.date.today(),
        'wait': True,
        'user_code': session.get('user_id', '01'),
        'station': '00',
        'store': stock_store_origin,
        'locations': '00',
        'destination_store': store_stock_destination,
        'operation_comments': 'Orden creada desde interfaz manual',
        'total': sum([it['quantity'] for it in items]),
    }

    try:
        order_id = save_transfer_order_in_wait(transfer_data, 'La operacion aun no ha sido validada')
        if not order_id:
            print('No se pudo crear la orden de transferencia (manual)')
            return redirect(url_for('inventory.manual_collection_order'))
        save_transfer_order_items(order_id, items)
    except Exception as e:
        print('Error creando orden manual:', e)
        return redirect(url_for('inventory.manual_collection_order'))

    return redirect(url_for('inventory.collection_preview_pdf', correlative=order_id, wait='true', operation_type='TRANSFER'))


@inventory_bp.route('/manual_collection_order/create_ajax', methods=['POST'])
def manual_collection_order_create_ajax():
    """Crear ORDER_COLLECTION vía AJAX y devolver JSON con URL del PDF y ruta de redirección."""
    try:
        selected = request.form.getlist('selected_products')
        product_codes = [c for c in selected if c]
        products_info = ({p['code']: p for p in get_products_by_codes(product_codes)} if product_codes else {})

        stock_store_origin = request.form.get('stock_store_origin') or os.environ.get('DEFAULT_STORE_ORIGIN_CODE', '01')
        # actualizar destino en sesión si viene
        if request.form.get('store_code_destination'):
            session['store_code_destination'] = request.form.get('store_code_destination')
        store_stock_destination = session.get('store_manual_collection_order') or session.get('store_code_destination')

        items = []
        for code in product_codes:
            raw = request.form.get(f'to_transfer_{code}', '0')
            if isinstance(raw, str):
                raw = raw.replace(',', '.')
            try:
                qty = float(raw)
            except Exception:
                qty = 0.0
            if qty <= 0:
                continue

            unit_raw = request.form.get(f'unit_for_{code}')
            try:
                unit_corr = int(unit_raw) if unit_raw and str(unit_raw).strip() != '' else get_correlative_product_unit(code)
            except Exception:
                unit_corr = get_correlative_product_unit(code)

            prod = products_info.get(code, {})
            item = {
                'product_code': code,
                'description': prod.get('description') if prod else None,
                'quantity': qty,
                'from_store': stock_store_origin,
                'to_store': store_stock_destination,
                'unit': int(unit_corr) if unit_corr else 1,
                'conversion_factor': 1.0,
                'unit_type': 1,
                'unit_price': 0.0,
                'total_price': 0.0,
                'total_cost': 0.0,
                'coin_code': '02',
            }
            items.append(item)

        if not items:
            return jsonify({'ok': False, 'error': 'No hay items válidos para procesar'}), 400

        transfer_data = {
            'emission_date': datetime.date.today(),
            'wait': True,
            'user_code': session.get('user_id', '01'),
            'station': '00',
            'store': stock_store_origin,
            'locations': '00',
            'destination_store': store_stock_destination,
            'operation_comments': 'Orden creada desde interfaz manual',
            'total': sum([it['quantity'] for it in items]),
        }

        order_id = save_transfer_order_in_wait(transfer_data, 'La operacion aun no ha sido validada')
        if not order_id:
            return jsonify({'ok': False, 'error': 'No se pudo crear la orden de transferencia'}), 500
        save_transfer_order_items(order_id, items)

        pdf_url = url_for('inventory.collection_preview_pdf', correlative=order_id, wait='true', operation_type='TRANSFER')
        redirect_to = url_for('inventory.select_store_manual_collection_order')
        return jsonify({'ok': True, 'pdf_url': pdf_url, 'redirect': redirect_to})
    except Exception as e:
        print('Error creando orden manual (ajax):', e)
        return jsonify({'ok': False, 'error': str(e)}), 500