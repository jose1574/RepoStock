import os
import sys
import socket
import win32serviceutil
import win32service
import win32event
import servicemanager

# Importar la app Flask
from app import app

class RepoStockService(win32serviceutil.ServiceFramework):
    _svc_name_ = "RepoStockService"
    _svc_display_name_ = "RepoStock Server Service"
    _svc_description_ = "Servicio de Windows que mantiene activo el servidor Flask de RepoStock en segundo plano."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.stop_requested = False

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.stop_requested = True
        try:
            # Señal para detener; el servidor de desarrollo de Flask no expone un stop limpio,
            # así que simplemente establecemos el evento y dejamos que el proceso termine.
            win32event.SetEvent(self.hWaitStop)
        except Exception:
            pass

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, "iniciado"),
        )
        self.main()

    def main(self):
        # Asegurar que el servidor escuche en todas las interfaces sin recarga/depuración
        host = os.environ.get("REPOSTOCK_HOST", "0.0.0.0")
        try:
            port = int(os.environ.get("REPOSTOCK_PORT", "5001"))
        except Exception:
            port = 5001

        # Ejecutar con waitress (WSGI producción). Si falla, fallback a Flask.
        try:
            from waitress import serve
            threads = int(os.environ.get("REPOSTOCK_THREADS", "8"))
            serve(app, host=host, port=port, threads=threads)
        except Exception as e:
            try:
                servicemanager.LogInfoMsg(
                    f"Waitress no disponible ({e}). Usando servidor Flask sin reloader."
                )
            except Exception:
                pass
            try:
                app.run(host=host, port=port, debug=False, use_reloader=False)
            except Exception as e2:
                try:
                    servicemanager.LogErrorMsg(f"RepoStockService error: {e2}")
                except Exception:
                    pass

if __name__ == '__main__':
    # Permite CLI: install, remove, start, stop, restart, debug
    win32serviceutil.HandleCommandLine(RepoStockService)
