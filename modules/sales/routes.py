from flask import Blueprint, render_template, request, jsonify
from db import get_stores, get_coins, search_products_for_sales

sales_bp = Blueprint(
    "sales", __name__, template_folder="./templates", url_prefix="/sales"
)


@sales_bp.route("/budget", methods=["GET"])
def budget():
    stores = get_stores() or []
    coins = get_coins() or []
    price_types = [
        {"code": "1", "description": "Precio 1"},
        {"code": "2", "description": "Precio 2"},
        {"code": "3", "description": "Precio 3"},
        {"code": "4", "description": "Precio 4"},
    ]
    return render_template(
        "budget.html", stores=stores, coins=coins, price_types=price_types
    )


@sales_bp.route("/api/products/search", methods=["GET"])
def api_products_search():
    """Endpoint para el modal de presupuesto: busca productos por texto.

    Parámetro `q` y devuelve lista con code, description, unit_description,
    unit_correlative y offer_price.
    """
    q = (request.args.get("q") or "").strip()
    try:
        items = search_products_for_sales() or []
        return jsonify({"ok": True, "items": items})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


#añade items al presupuesto
@sales_bp.route("/api/budget/add_item", methods=["POST"])
def api_budget_add_item():
    """Añade un item al presupuesto (simulado en sesión por ahora).

    Parámetros JSON: code, description, unit_description, unit_correlative,
    offer_price, quantity.

    Devuelve el item añadido con total_price.
    """
    data = request.get_json() or {}
    try:
        code = data.get("code", "").strip()
        description = data.get("description", "").strip()
        unit_description = data.get("unit_description", "").strip()
        unit_correlative = data.get("unit_correlative", "").strip()
        offer_price = float(data.get("offer_price", 0))
        quantity = float(data.get("quantity", 0))

        if not code or not description or not unit_description or not unit_correlative:
            raise ValueError("Faltan datos obligatorios del producto.")
        if offer_price < 0 or quantity <= 0:
            raise ValueError("Precio u cantidad inválidos.")

        total_price = round(offer_price * quantity, 2)

        item = {
            "code": code,
            "description": description,
            "unit_description": unit_description,
            "unit_correlative": unit_correlative,
            "offer_price": offer_price,
            "quantity": quantity,
            "total_price": total_price,
        }

        # Aquí se podría guardar en sesión o base de datos

        return jsonify({"ok": True, "item": item})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500