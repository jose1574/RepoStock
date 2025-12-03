from flask import Blueprint, render_template, request, redirect, url_for, session

sales_bp = Blueprint(
    "sales", __name__, template_folder="/sales/templates", url_prefix="/sales"
)


@sales_bp.route("/", methods=["GET"])
def sales_home():
    return render_template("sales/home.html")
