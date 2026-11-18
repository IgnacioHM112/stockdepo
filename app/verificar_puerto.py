"""Verifica si StockDepo ya está activo o si el puerto 8000 está ocupado."""
import socket
import sys
import urllib.request

# 1. ¿StockDepo ya responde?
try:
    with urllib.request.urlopen("http://127.0.0.1:8000/api/meta", timeout=1) as resp:
        if resp.status == 200:
            print("RUNNING")
            sys.exit(0)
except Exception:
    pass

# 2. ¿Puerto 8000 tomado por otro proceso que no responde?
s = socket.socket()
res = s.connect_ex(("127.0.0.1", 8000))
s.close()
if res == 0:
    print("BUSY")
    sys.exit(2)

print("CLEAN")
sys.exit(1)
