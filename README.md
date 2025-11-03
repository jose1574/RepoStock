# RepoStock
Aplicación para reposición de inventario en el sistema Chrystal

## Construcción de instalador (Windows) con PyInstaller

Este proyecto incluye un archivo `app.spec` para empaquetar la app con PyInstaller e incluir:

- Plantillas (`templates/`)
- Archivos estáticos (`static/`)
- Reportes (`reports/`)
- Scripts/SQL (`SQL/`)
- Carpeta `install/` (contiene el instalador de wkhtmltopdf)
- Archivo `.env`

### Requisitos

- Python 3.9+ (recomendado)
- Pip y venv configurados
- PyInstaller

Instala PyInstaller si no lo tienes:

```
pip install pyinstaller
```

### Construir

Desde Windows, ejecuta el script de build:

```
build_windows.bat
```

El ejecutable quedará en `dist/RepoStock/RepoStock.exe`.

### wkhtmltopdf

- Para generar PDF se usa `wkhtmltopdf`. Esta app busca el binario en:
	- Variable de entorno `WKHTMLTOPDF_BIN`, o
	- Rutas típicas: `C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe`.
- En `install/` se incluye el instalador `wkhtmltox-*.exe`. Si al abrir PDF recibes el mensaje de que
	no se encuentra wkhtmltopdf, ejecuta ese instalador una vez (puedes hacerlo manualmente desde la
	carpeta `dist/RepoStock/install/`).

### Ejecutar

```
dist/RepoStock/RepoStock.exe
```

Por defecto abre un servidor en `http://127.0.0.1:5001/`.

### Notas

- Si no quieres ver la consola al ejecutar, cambia `console=True` a `console=False` en `app.spec` y reconstruye.
- Para actualizar dependencias de Python, usa un entorno virtual y asegúrate de que PyInstaller vea esas libs.
