"""Punto de entrada: python -m app"""
import os
import sys
import threading
import time
import urllib.request
import webbrowser
import uvicorn


def _esperar_y_abrir_navegador():
    """Espera a que el servidor FastAPI esté respondiendo antes de abrir el navegador."""
    if "--no-browser" in sys.argv or os.environ.get("STOCKDEPO_NO_BROWSER") == "1":
        return
    url = "http://localhost:8000"
    ping_url = "http://127.0.0.1:8000/api/meta"
    for _ in range(40):  # hasta 16 segundos máximo
        time.sleep(0.4)
        try:
            with urllib.request.urlopen(ping_url, timeout=1) as resp:
                if resp.status == 200:
                    webbrowser.open(url)
                    return
        except Exception:
            pass


if __name__ == "__main__":
    threading.Thread(target=_esperar_y_abrir_navegador, daemon=True).start()
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
