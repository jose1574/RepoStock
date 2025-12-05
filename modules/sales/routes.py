from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
import db

sales_bp = Blueprint(
    "sales", __name__, template_folder="./templates", url_prefix="/sales"
)


@sales_bp.route("/budget", methods=["GET"])
def budget():
    return render_template("budget.html")


@sales_bp.route("/product-search-modal", methods=["GET"])
def product_search_modal():
    return render_template("partials/product_search_modal.html")


@sales_bp.route("/api/products/search", methods=["GET"])
def api_products_search():
    q = (request.args.get("q") or "").strip()
    try:
        rows = db.search_products_with_stock_and_price(q) or []
        return jsonify({"ok": True, "items": rows})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@sales_bp.route("/api/budget/add_item", methods=["POST"])
def api_budget_add_item():
    code = request.form.get("code") or ""
    item_get_db = g
    description = request.form.get("description") or ""
    unit_description = request.form.get("unit_description") or ""
    unit_correlative = request.form.get("unit_correlative") or ""
    try:
        offer_price = float(request.form.get("offer_price") or 0)
        quantity = float(request.form.get("quantity") or 1)
    except ValueError:
        offer_price = 0.0
        quantity = 1.0
    item = {
        "code": code,
        "description": "description",
        "unit_description": unit_description,
        "unit_correlative": unit_correlative,
        "offer_price": offer_price,
        "quantity": quantity,
        "subtotal": round(offer_price * quantity, 2),
    }
    return jsonify({"ok": True, "item": item})


@sales_bp.route("/clients-search-modal", methods=["GET"])
def clients_search_modal():
    return render_template("partials/clients_search_modal.html")


@sales_bp.route("/api/clients/search", methods=["GET"])
def api_clients_search():
    q = (request.args.get("q") or "").strip().lower()
    try:
        items = db.get_clients() or []
      
        return jsonify({"ok": True, "items": items})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@sales_bp.route("/api/clients/<code>", methods=["GET"])
def api_get_client_by_code(code):
    try:
        client = db.get_client_by_code(code)
        if client:
            return jsonify({"ok": True, "client": client})
        else:
            return jsonify({"ok": False, "error": "Client not found"}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500