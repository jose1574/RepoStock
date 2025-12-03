import datetime
import os
import sys
from flask import (Blueprint, render_template, render_template_string, request, redirect, url_for, session)
import pdfkit


from db import delete_inventory_operation_by_correlative, get_inventory_operations, get_inventory_operations_by_correlative, get_inventory_operations_details_by_correlative

manager_bp = Blueprint('manager', __name__, url_prefix='/manager')

manager_bp.template_folder = os.path.join(os.path.dirname(__file__), 'templates')

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


if getattr(sys, "frozen", False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))
#ruta de temp

@manager_bp.route("/")
def document_manager():
    inventory_operations = get_inventory_operations()
    print("Inventory Operations:", inventory_operations[0])
    return render_template("document_manager.html", inventory_operations=inventory_operations)


@manager_bp.route("/document_manager/delete", methods=["POST"])
def delete_inventory_operation():
    """Elimina una orden de traslado por correlativo y vuelve a la lista de reportes."""
    correlative = request.form.get("correlative", type=int)
    if not correlative:
        return redirect(url_for("manager.document_manager"))
    try:
        delete_inventory_operation_by_correlative(correlative)
    except Exception as e:
        # Registra el error y regresa a la lista; opcionalmente usar flash para el usuario
        print(f"No se pudo eliminar la operación {correlative}: {e}")
    return redirect(url_for("manager.document_manager"))


@manager_bp.route("/collection/preview.pdf", methods=["POST", "GET"])
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