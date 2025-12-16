"""Prueba rápida para las funciones de `db_sqlite`.

Ejecutar:
  py tests/test_db_sqlite.py

Verifica:
 - crear perfil
 - listar menús
 - asignar menús al perfil
 - recuperar menús asignados
"""
from datetime import datetime
import sys
import os

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

import db_sqlite


def run():
    print('Inicializando DB...')
    db_sqlite.init_db()

    desc = f'test-profile-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}'
    print('Creando perfil:', desc)
    pid = db_sqlite.create_profile(desc)
    assert isinstance(pid, int) and pid > 0, 'profile_id inválido'
    print('Profile creado id=', pid)

    menus = db_sqlite.get_menus(active_only=False)
    print(f'Encontrados {len(menus)} menús (tomando hasta 2)')
    if not menus:
        raise SystemExit('No hay menús sembrados; ejecuta py db_sqlite.py primero')

    menu_ids = [menus[i]['id'] for i in range(min(2, len(menus)))]
    print('Asignando menus:', menu_ids)
    db_sqlite.assign_menus_to_profile(pid, menu_ids)

    assigned = db_sqlite.get_menus_by_profile(pid)
    assigned_ids = [m['id'] for m in assigned]
    print('Menus asignados recuperados:', assigned_ids)

    assert set(menu_ids) == set(assigned_ids), 'Los menús asignados no coinciden'

    print('Prueba completada correctamente')


if __name__ == '__main__':
    try:
        run()
    except AssertionError as e:
        print('FALLÓ:', e)
        raise
    except Exception as e:
        print('Error:', e)
        raise
