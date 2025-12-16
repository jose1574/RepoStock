from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
import sqlite3
from db_sqlite import (
    create_profile as db_create_profile,
    get_profile_by_description,
    get_menus,
    assign_menus_to_profile,
    assign_profile_to_user,
)


systems_bp = Blueprint(
    "systems", __name__, template_folder="./templates", url_prefix="/systems"
)


@systems_bp.route("/setup", methods=["GET"])
def setup():
    return render_template("setup.html")


@systems_bp.route("/api/user/<int:user_code>", methods=["GET"])
def api_get_user(user_code):
    try:
        conn = sqlite3.connect('repostock.db')
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT id, description, profile_id FROM users WHERE id = ?', (user_code,))
        row = cur.fetchone()
        conn.close()
        if row:
            return jsonify(dict(row)), 200
        return jsonify({"error": "User not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@systems_bp.route('/profile/create', methods=['GET', 'POST'])
def create_profile():
    if request.method == 'GET':
        menus = get_menus(active_only=False)
        return render_template('create_profile.html', menus=menus)

    # POST -> crear perfil
    description = (request.form.get('description') or '').strip()
    if not description:
        flash('La descripción del perfil es requerida', 'warning')
        return redirect(url_for('systems.create_profile'))

    existing = get_profile_by_description(description)
    if existing:
        flash('Ya existe un perfil con esa descripción', 'warning')
        return redirect(url_for('systems.create_profile'))

    try:
        profile_id = db_create_profile(description)
        selected = request.form.getlist('menus')
        if selected:
            menu_ids = [int(x) for x in selected if x.isdigit()]
            assign_menus_to_profile(profile_id, menu_ids)
        flash('Perfil creado correctamente', 'success')
    except Exception as e:
        flash(f'Error creando perfil: {e}', 'danger')

    return redirect(url_for('systems.setup'))


@systems_bp.route('/profile/assign', methods=['GET', 'POST'])
def assign_profile():
    if request.method == 'GET':
        conn = sqlite3.connect('repostock.db')
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT id, description FROM profile ORDER BY id')
        rows = cur.fetchall()
        profiles = [dict(r) for r in rows]
        conn.close()
        return render_template('assign_profile.html', profiles=profiles)

    # POST -> asignar
    try:
        user_id = int(request.form.get('user_id'))
        profile_id = int(request.form.get('profile_id'))
    except Exception:
        flash('Valores inválidos', 'warning')
        return redirect(url_for('systems.assign_profile'))

    try:
        assign_profile_to_user(user_id, profile_id)
        flash('Perfil asignado correctamente', 'success')
    except Exception as e:
        flash(f'Error asignando perfil: {e}', 'danger')

    return redirect(url_for('systems.setup'))

    return redirect(url_for('systems.setup'))
