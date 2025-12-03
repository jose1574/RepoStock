from flask import Blueprint, render_template, request, redirect, url_for, session


clients_bp = Blueprint(
    "clients", __name__,
    template_folder="./templates",
    url_prefix="/clients"
    
)
