"""Servicios de StockDepo: Avisos/Gmail (Fase 4), Red/QR/Respaldos (Fase 5), Previsión/Asistente (Fase 6) y Planilla por Foto (Fase 7)."""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import smtplib
import socket
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path
from typing import Optional

from . import db

BACKUPS_DIR = db.BASE_DIR / "backups"

CONFIG_DEFAULTS = {
    # Avisos App
    "app_on": "1",
    "app_desp": "1",
    "app_photo": "1",
    "app_low": "1",
    "app_crit": "1",
    # Avisos Gmail
    "mail_on": "0",
    "mail_from": "enfocadosmendoza@gmail.com",
    "mail_desp": "0",
    "mail_low": "1",
    "mail_crit": "1",
    "mail_week": "1",
    "mail_day": "Lunes",
    "mail_hour": "09:00",
    "mail_emails": '["pablo@gmail.com","mauricio@gmail.com"]',
    # Claves (nunca se exponen en texto plano al listar config)
    "gmail_app_password": "",
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    # Control de tareas programadas
    "ultimo_resumen_semanal": "",
    # Regla establecida de cajas por cantidad
    "caja_chica_capacidad": "2",
    "caja_mediana_desde_unidades": "3",
    "caja_mediana_capacidad": "9",
    "caja_grande_desde_unidades": "10",
    "unidades_por_caja_grande": "15",
    "respetar_caja_minima_producto": "0",
}


def obtener_regla_cajas(con) -> dict:
    c = leer_mapa_config(con)
    chica_cap = int(c.get("caja_chica_capacidad") or 2)
    med_desde = int(c.get("caja_mediana_desde_unidades") or 3)
    med_cap = int(c.get("caja_mediana_capacidad") or 9)
    gra_desde = int(c.get("caja_grande_desde_unidades") or 10)
    gra_cap = int(c.get("unidades_por_caja_grande") or 15)
    resp_min = c.get("respetar_caja_minima_producto", "0") == "1"
    return {
        "chica_capacidad": chica_cap,
        "mediana_desde": med_desde,
        "mediana_capacidad": med_cap,
        "grande_desde": gra_desde,
        "grande_capacidad": gra_cap,
        "respetar_caja_minima": resp_min,
        # Alias de compatibilidad
        "caja_grande_desde_unidades": gra_desde,
        "unidades_por_caja_grande": gra_cap,
    }


def guardar_regla_cajas(con, data: dict) -> dict:
    asegurar_config(con)
    actual = obtener_regla_cajas(con)
    chica_cap = int(data.get("chica_capacidad") or actual["chica_capacidad"])
    med_desde = int(data.get("mediana_desde") or actual["mediana_desde"])
    med_cap = int(data.get("mediana_capacidad") or actual["mediana_capacidad"])
    gra_desde = int(data.get("grande_desde") or data.get("caja_grande_desde_unidades") or actual["grande_desde"])
    gra_cap = int(data.get("grande_capacidad") or data.get("unidades_por_caja_grande") or actual["grande_capacidad"])
    resp_min = data.get("respetar_caja_minima", actual["respetar_caja_minima"])

    pares = {
        "caja_chica_capacidad": str(max(1, chica_cap)),
        "caja_mediana_desde_unidades": str(max(2, med_desde)),
        "caja_mediana_capacidad": str(max(1, med_cap)),
        "caja_grande_desde_unidades": str(max(med_desde + 1, gra_desde)),
        "unidades_por_caja_grande": str(max(1, gra_cap)),
        "respetar_caja_minima_producto": "1" if resp_min else "0",
    }
    for k, v in pares.items():
        con.execute("INSERT OR REPLACE INTO config (clave, valor) VALUES (?, ?)", (k, v))
    return obtener_regla_cajas(con)


def calcular_cajas_pedido(con, articulos: dict[int, dict], pedidos: dict[int, int]) -> dict[int, int]:
    """Calcula qué caja(s) corresponden según la cantidad total de productos del pedido."""
    rc = obtener_regla_cajas(con)
    total_u = sum(
        cant for aid, cant in pedidos.items()
        if aid in articulos and articulos[aid]["tipo"] == "producto"
    )
    if total_u <= 0:
        return {}

    cajas = [a for a in articulos.values() if a["activo"] and a["tipo"] == "insumo" and a["nombre"].lower().startswith("caja")]
    c_chica = next((a for a in cajas if "chica" in a["nombre"].lower()), None)
    c_mediana = next((a for a in cajas if "mediana" in a["nombre"].lower()), None)
    c_grande = next((a for a in cajas if "grande" in a["nombre"].lower()), None)

    if c_grande and total_u >= rc["grande_desde"]:
        return {c_grande["id"]: math.ceil(total_u / max(1, rc["grande_capacidad"]))}
    if c_mediana and total_u >= rc["mediana_desde"]:
        return {c_mediana["id"]: math.ceil(total_u / max(1, rc["mediana_capacidad"]))}

    # Pedido chico (< mediana_desde, ej. 1 o 2 unidades)
    if rc["respetar_caja_minima"]:
        res: dict[int, int] = {}
        for aid, cant in pedidos.items():
            a = articulos.get(aid)
            if a and a["tipo"] == "producto":
                cid = a.get("caja_id") or (c_chica["id"] if c_chica else None)
                if cid:
                    res[cid] = res.get(cid, 0) + cant
        return res

    if c_chica:
        return {c_chica["id"]: math.ceil(total_u / max(1, rc["chica_capacidad"]))}
    return {}


def asegurar_config(con):
    for k, v in CONFIG_DEFAULTS.items():
        con.execute("INSERT OR IGNORE INTO config (clave, valor) VALUES (?, ?)", (k, v))


def leer_mapa_config(con) -> dict[str, str]:
    asegurar_config(con)
    return dict(con.execute("SELECT clave, valor FROM config").fetchall())


def estado_avisos_config(con) -> dict:
    c = leer_mapa_config(con)
    try:
        emails = json.loads(c.get("mail_emails") or "[]")
    except Exception:
        emails = []
    return {
        "app": {
            "on": c.get("app_on", "1") == "1",
            "desp": c.get("app_desp", "1") == "1",
            "photo": c.get("app_photo", "1") == "1",
            "low": c.get("app_low", "1") == "1",
            "crit": c.get("app_crit", "1") == "1",
        },
        "mail": {
            "on": c.get("mail_on", "0") == "1",
            "from": c.get("mail_from", ""),
            "desp": c.get("mail_desp", "0") == "1",
            "low": c.get("mail_low", "1") == "1",
            "crit": c.get("mail_crit", "1") == "1",
            "week": c.get("mail_week", "1") == "1",
            "day": c.get("mail_day", "Lunes"),
            "hour": c.get("mail_hour", "09:00"),
            "emails": emails,
            "tiene_clave": bool(c.get("gmail_app_password", "").strip()),
        },
    }


def guardar_avisos_config(con, data: dict) -> dict:
    asegurar_config(con)
    app_cfg = data.get("app") or {}
    mail_cfg = data.get("mail") or {}
    pares = {
        "app_on": "1" if app_cfg.get("on", True) else "0",
        "app_desp": "1" if app_cfg.get("desp", True) else "0",
        "app_photo": "1" if app_cfg.get("photo", True) else "0",
        "app_low": "1" if app_cfg.get("low", True) else "0",
        "app_crit": "1" if app_cfg.get("crit", True) else "0",
        "mail_on": "1" if mail_cfg.get("on", False) else "0",
        "mail_from": str(mail_cfg.get("from", "")).strip(),
        "mail_desp": "1" if mail_cfg.get("desp", False) else "0",
        "mail_low": "1" if mail_cfg.get("low", True) else "0",
        "mail_crit": "1" if mail_cfg.get("crit", True) else "0",
        "mail_week": "1" if mail_cfg.get("week", True) else "0",
        "mail_day": str(mail_cfg.get("day", "Lunes")),
        "mail_hour": str(mail_cfg.get("hour", "09:00")),
        "mail_emails": json.dumps([str(e).strip() for e in (mail_cfg.get("emails") or []) if str(e).strip()]),
    }
    for k, v in pares.items():
        con.execute("INSERT OR REPLACE INTO config (clave, valor) VALUES (?, ?)", (k, v))
    return estado_avisos_config(con)


def enviar_gmail(con, asunto: str, cuerpo: str) -> tuple[bool, str]:
    c = leer_mapa_config(con)
    remitente = c.get("mail_from", "").strip()
    clave = c.get("gmail_app_password", "").strip().replace(" ", "")
    try:
        destinatarios = [e.strip() for e in json.loads(c.get("mail_emails") or "[]") if e.strip()]
    except Exception:
        destinatarios = []

    if not remitente or not clave:
        return False, "Falta configurar la cuenta Gmail o la contraseña de aplicación en Configuración."
    if not destinatarios:
        return False, "No hay destinatarios cargados en Avisos por Gmail."

    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = remitente
    msg["To"] = ", ".join(destinatarios)
    msg.set_content(cuerpo)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
            smtp.login(remitente, clave)
            smtp.send_message(msg)
        return True, f"Enviado a {len(destinatarios)} destinatario(s)"
    except Exception as ex:
        return False, f"Error SMTP Gmail: {ex}"


def texto_resumen_semanal(con) -> str:
    activos = con.execute("SELECT * FROM articulos WHERE activo = 1 ORDER BY orden, id").fetchall()
    criticos = [a for a in activos if db.estado(a["stock"], a["minimo"], a["critico"]) == "crit"]
    bajos = [a for a in activos if db.estado(a["stock"], a["minimo"], a["critico"]) == "low"]
    desde_7d = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
    despachos = con.execute("SELECT * FROM despachos WHERE fecha >= ?", (desde_7d,)).fetchall()

    lineas = [
        "📊 RESUMEN SEMANAL — StockDepo (Enfocados Mendoza)",
        f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
        f"• Despachos últimos 7 días: {len(despachos)}",
    ]
    for canal in db.CANALES:
        n = sum(1 for d in despachos if d["canal"] == canal)
        if n:
            lineas.append(f"  - {canal}: {n}")

    lineas.append("")
    if criticos:
        lineas.append(f"🛑 En nivel CRÍTICO ({len(criticos)}):")
        for a in criticos:
            lineas.append(f"  - {a['nombre']}: {a['stock']} {a['unidad']} (crít. {a['critico']})")
    else:
        lineas.append("🛑 En nivel CRÍTICO: ninguno")

    if bajos:
        lineas.append(f"⚠️ En nivel BAJO ({len(bajos)}):")
        for a in bajos:
            lineas.append(f"  - {a['nombre']}: {a['stock']} {a['unidad']} (mín. {a['minimo']})")
    else:
        lineas.append("⚠️ En nivel BAJO: ninguno")

    lineas.append("")
    lineas.append("📦 Stock completo:")
    for a in activos:
        lineas.append(f"  - {a['nombre']}: {a['stock']} {a['unidad']}")
    return "\n".join(lineas)


def disparar_resumen_semanal(con) -> dict:
    c = leer_mapa_config(con)
    activos = con.execute("SELECT * FROM articulos WHERE activo = 1").fetchall()
    faltantes = [a["nombre"] for a in activos if db.estado(a["stock"], a["minimo"], a["critico"]) != "ok"]
    desde_7d = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
    cant_desp = con.execute("SELECT COUNT(*) FROM despachos WHERE fecha >= ?", (desde_7d,)).fetchone()[0]
    try:
        destinatarios = json.loads(c.get("mail_emails") or "[]")
    except Exception:
        destinatarios = []

    cuerpo = texto_resumen_semanal(con)
    mail_enviado = False
    detalle_mail = "Modo local (sin contraseña de Gmail configurada)"
    if c.get("mail_on") == "1" and c.get("gmail_app_password", "").strip():
        mail_enviado, detalle_mail = enviar_gmail(con, "📊 Resumen semanal de stock — Enfocados Mendoza", cuerpo)

    resumen_corto = (
        f"Resumen semanal: {cant_desp} despacho(s) en 7 días · "
        f"en alerta: {', '.join(faltantes[:5]) + ('...' if len(faltantes) > 5 else '') if faltantes else 'ninguno'}."
    )
    con.execute(
        "INSERT INTO notificaciones (fecha, tipo, mensaje, leida, enviada_mail) VALUES (?,?,?,0,?)",
        (db.ahora(), "week", resumen_corto, 1 if mail_enviado else 0),
    )
    return {"ok": True, "mail_enviado": mail_enviado, "detalle": detalle_mail, "mensaje": resumen_corto}


# ---------- Red LAN, QR y Respaldos (Fase 5) ----------
def obtener_ip_lan() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def generar_qr_svg(url: str) -> str:
    try:
        import qrcode
        import qrcode.image.svg
        img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
        buf = BytesIO()
        img.save(buf)
        return buf.getvalue().decode("utf-8")
    except Exception:
        return ""


def crear_respaldo(etiqueta: str = "manual") -> dict:
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    limpio = re.sub(r"[^a-zA-Z0-9_-]", "", etiqueta) or "manual"
    destino = BACKUPS_DIR / f"stockdepo_{ts}_{limpio}.db"

    origen_con = sqlite3.connect(db.DB_PATH)
    dest_con = sqlite3.connect(destino)
    try:
        origen_con.backup(dest_con)
    finally:
        dest_con.close()
        origen_con.close()

    # Conservar los 30 respaldos más recientes
    archivos = sorted(BACKUPS_DIR.glob("stockdepo_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for viejo in archivos[30:]:
        try:
            viejo.unlink()
        except Exception:
            pass

    st = destino.stat()
    return {
        "nombre": destino.name,
        "fecha": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
        "tamano_kb": round(st.st_size / 1024, 1),
    }


def listar_respaldos() -> list[dict]:
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    res = []
    for p in sorted(BACKUPS_DIR.glob("stockdepo_*.db"), key=lambda x: x.stat().st_mtime, reverse=True):
        st = p.stat()
        res.append({
            "nombre": p.name,
            "fecha": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
            "tamano_kb": round(st.st_size / 1024, 1),
        })
    return res


def restaurar_respaldo(nombre: str) -> dict:
    if "/" in nombre or "\\" in nombre or not nombre.endswith(".db"):
        raise ValueError("Nombre de archivo inválido")
    origen = BACKUPS_DIR / nombre
    if not origen.exists():
        raise ValueError("El archivo de respaldo no existe")
    # Hacer copia de seguridad previa antes de restaurar
    crear_respaldo("pre_restauracion")
    src = sqlite3.connect(origen)
    dst = sqlite3.connect(db.DB_PATH)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return {"ok": True, "restaurado": nombre}


# ---------- Previsión, Pedidos futuros y Proyección (Fase 6) ----------
def mapa_comprometido(con) -> dict[int, int]:
    """Devuelve {articulo_id: cantidad_comprometida} sumando todos los pedidos futuros pendientes."""
    sql = """SELECT pfi.articulo_id, COALESCE(SUM(pfi.cantidad), 0) AS total
             FROM pedido_futuro_items pfi
             JOIN pedidos_futuros pf ON pf.id = pfi.pedido_id
             WHERE pf.estado = 'pendiente'
             GROUP BY pfi.articulo_id"""
    return {r["articulo_id"]: r["total"] for r in con.execute(sql)}


def listar_pedidos_futuros(con, incluir_cerrados: bool = False) -> list[dict]:
    sql = "SELECT * FROM pedidos_futuros" + ("" if incluir_cerrados else " WHERE estado = 'pendiente'")
    sql += " ORDER BY COALESCE(fecha_estimada, '9999-99-99'), id DESC"
    filas = con.execute(sql).fetchall()
    if not filas:
        return []
    ids = [r["id"] for r in filas]
    placeholders = ",".join("?" * len(ids))
    sql_it = f"""SELECT pfi.pedido_id, pfi.articulo_id, pfi.cantidad,
                        a.nombre, a.unidad, a.stock, a.tipo
                 FROM pedido_futuro_items pfi
                 JOIN articulos a ON a.id = pfi.articulo_id
                 WHERE pfi.pedido_id IN ({placeholders})"""
    items_map: dict[int, list[dict]] = {}
    for it in con.execute(sql_it, ids):
        items_map.setdefault(it["pedido_id"], []).append(dict(it))
    res = []
    for r in filas:
        d = dict(r)
        d["items"] = items_map.get(d["id"], [])
        res.append(d)
    return res


def simular_pedido(con, items: list[dict], descontar_comprometido: bool = True) -> dict:
    """Simula qué pasaría si entra un pedido futuro con [{articulo_id, cantidad}].
    Calcula stock actual, comprometido, disponible, cuánto quedaría, cuánto falta,
    cuántos se pueden armar con componentes, qué componentes faltan y cuántas cajas lleva."""
    comp_map = mapa_comprometido(con) if descontar_comprometido else {}
    articulos = {r["id"]: dict(r) for r in con.execute("SELECT * FROM articulos").fetchall()}
    recetas: dict[int, list[dict]] = {}
    for r in con.execute("SELECT * FROM recetas"):
        recetas.setdefault(r["producto_id"], []).append({"componente_id": r["componente_id"], "cantidad": r["cantidad"]})

    # Agrupar cantidades pedidas por artículo
    pedidos: dict[int, int] = {}
    for it in items:
        aid = int(it["articulo_id"])
        q = int(it["cantidad"])
        if q > 0 and aid in articulos:
            pedidos[aid] = pedidos.get(aid, 0) + q

    resultado_prods = []
    demanda_componentes: dict[int, int] = {}
    total_unidades_prod = 0
    alcanza_stock_directo = True

    for aid, cant_pedida in pedidos.items():
        a = articulos[aid]
        comprometido = comp_map.get(aid, 0)
        disponible = max(0, a["stock"] - comprometido)
        usado = min(disponible, cant_pedida)
        quedaria = disponible - usado
        faltante = max(0, cant_pedida - disponible)
        est_final = db.estado(quedaria, a["minimo"], a["critico"])

        rec = recetas.get(aid, [])
        armables = None
        if faltante > 0:
            alcanza_stock_directo = False
        if a["tipo"] == "producto":
            total_unidades_prod += cant_pedida
            if rec:
                armables = min(
                    max(0, articulos[c["componente_id"]]["stock"] - comp_map.get(c["componente_id"], 0)) // c["cantidad"]
                    for c in rec
                )
            if faltante > 0:
                for c in rec:
                    cid = c["componente_id"]
                    demanda_componentes[cid] = demanda_componentes.get(cid, 0) + faltante * c["cantidad"]

        resultado_prods.append({
            "articulo_id": aid,
            "nombre": a["nombre"],
            "tipo": a["tipo"],
            "unidad": a["unidad"],
            "stock_actual": a["stock"],
            "comprometido": comprometido,
            "disponible": disponible,
            "pedido": cant_pedida,
            "quedaria": quedaria,
            "faltante": faltante,
            "armables_con_stock": armables,
            "tiene_receta": bool(rec),
            "estado_final": est_final,
        })

    # Evaluar componentes necesarios para armar los productos faltantes
    componentes_necesarios = []
    alcanzan_componentes = True
    for cid, req in demanda_componentes.items():
        comp = articulos[cid]
        disp_c = max(0, comp["stock"] - comp_map.get(cid, 0))
        queda_c = max(0, disp_c - req)
        falta_c = max(0, req - disp_c)
        if falta_c > 0:
            alcanzan_componentes = False
        componentes_necesarios.append({
            "componente_id": cid,
            "nombre": comp["nombre"],
            "unidad": comp["unidad"],
            "proveedor": comp["proveedor"],
            "stock_actual": disp_c,
            "necesario": req,
            "quedaria": queda_c,
            "faltante": falta_c,
            "estado_final": db.estado(queda_c, comp["minimo"], comp["critico"]),
        })

    # Estimar cajas de envío según la regla establecida por cantidades
    cajas_por_id = calcular_cajas_pedido(con, articulos, pedidos)

    cajas_estimadas = []
    alcanzan_cajas = True
    for cid, req in cajas_por_id.items():
        caja = articulos[cid]
        disp_caja = max(0, caja["stock"] - comp_map.get(cid, 0))
        queda_caja = max(0, disp_caja - req)
        falta_caja = max(0, req - disp_caja)
        if falta_caja > 0:
            alcanzan_cajas = False
        cajas_estimadas.append({
            "articulo_id": cid,
            "nombre": caja["nombre"],
            "stock_actual": disp_caja,
            "necesarias": req,
            "quedaria": queda_caja,
            "faltante": falta_caja,
            "estado_final": db.estado(queda_caja, caja["minimo"], caja["critico"]),
        })

    # Armar resumen en texto claro
    lineas_txt = []
    if alcanza_stock_directo and alcanzan_cajas:
        lineas_txt.append("✅ ¡Te alcanza con el stock armado actual!")
    elif not alcanza_stock_directo and componentes_necesarios and alcanzan_componentes:
        lineas_txt.append("🛠️ No alcanza con los estuches ya armados, pero SÍ tenés componentes para armar los que faltan.")
    else:
        lineas_txt.append("⚠️ No alcanza con el stock actual: hace falta armar o reponer mercadería.")

    for p in resultado_prods:
        comp_txt = f" (comprometido: {p['comprometido']})" if p["comprometido"] else ""
        if p["faltante"] == 0:
            lineas_txt.append(
                f"• {p['nombre']}: pedís {p['pedido']}, tenés {p['disponible']} disp.{comp_txt} → "
                f"te quedarían {p['quedaria']} {p['unidad']} ({p['estado_final'].upper()})."
            )
        else:
            extra_arm = ""
            if p["tiene_receta"] and p["armables_con_stock"] is not None:
                extra_arm = f" (podés armar hasta {p['armables_con_stock']} con tus piezas actuales)"
            lineas_txt.append(
                f"• {p['nombre']}: pedís {p['pedido']}, tenés {p['disponible']} disp.{comp_txt} → "
                f"te quedarían 0 y FALTAN {p['faltante']} {p['unidad']}{extra_arm}."
            )

    if componentes_necesarios:
        lineas_txt.append("\n🧩 Componentes para armar los faltantes:")
        for c in componentes_necesarios:
            if c["faltante"] == 0:
                lineas_txt.append(f"• {c['nombre']}: necesitás {c['necesario']}, hay {c['stock_actual']} → quedan {c['quedaria']}.")
            else:
                lineas_txt.append(f"• {c['nombre']}: necesitás {c['necesario']}, hay {c['stock_actual']} → FALTAN COMPRAR {c['faltante']} {c['unidad']}.")

    if cajas_estimadas:
        lineas_txt.append("\n📦 Cajas de envío estimadas:")
        for cj in cajas_estimadas:
            if cj["faltante"] == 0:
                lineas_txt.append(f"• {cj['nombre']}: lleva {cj['necesarias']}, hay {cj['stock_actual']} → quedan {cj['quedaria']}.")
            else:
                lineas_txt.append(f"• {cj['nombre']}: lleva {cj['necesarias']}, hay {cj['stock_actual']} → FALTAN {cj['faltante']}.")

    return {
        "alcanza_stock_directo": alcanza_stock_directo,
        "alcanzan_componentes": alcanzan_componentes,
        "alcanzan_cajas": alcanzan_cajas,
        "productos": resultado_prods,
        "componentes_necesarios": componentes_necesarios,
        "cajas_estimadas": cajas_estimadas,
        "resumen_texto": "\n".join(lineas_txt),
    }


def proyeccion_consumo(con, dias_historial: int = 30, dias_objetivo: int = 14) -> list[dict]:
    """Calcula consumo diario promedio, días de cobertura restantes y sugerencia de reposición."""
    desde = (datetime.now() - timedelta(days=dias_historial)).isoformat(timespec="seconds")
    comp_map = mapa_comprometido(con)

    # Cuántos días reales abarca el historial de salidas (mínimo 1 día para no inflar)
    primera = con.execute("SELECT MIN(fecha) FROM movimientos WHERE delta < 0 AND fecha >= ?", (desde,)).fetchone()[0]
    if primera:
        dias_reales = max(1.0, (datetime.now() - datetime.fromisoformat(primera)).total_seconds() / 86400.0)
    else:
        dias_reales = float(dias_historial)

    salidas = dict(
        con.execute(
            "SELECT articulo_id, COALESCE(SUM(-delta), 0) FROM movimientos WHERE delta < 0 AND fecha >= ? GROUP BY articulo_id",
            (desde,),
        ).fetchall()
    )

    res = []
    for a in con.execute("SELECT * FROM articulos WHERE activo = 1 ORDER BY orden, id"):
        sal = salidas.get(a["id"], 0)
        comp = comp_map.get(a["id"], 0)
        disp = max(0, a["stock"] - comp)
        diario = round(sal / dias_reales, 2) if sal > 0 else 0.0
        dias_cob = round(disp / diario, 1) if diario > 0 else None
        fecha_quiebre = (
            (datetime.now() + timedelta(days=disp / diario)).strftime("%d/%m/%Y")
            if diario > 0 else None
        )
        meta_stock = math.ceil(diario * dias_objetivo) + a["minimo"] + comp
        reponer = max(0, meta_stock - a["stock"])
        res.append({
            "articulo_id": a["id"],
            "nombre": a["nombre"],
            "tipo": a["tipo"],
            "unidad": a["unidad"],
            "stock": a["stock"],
            "comprometido": comp,
            "disponible": disp,
            "minimo": a["minimo"],
            "salidas_periodo": sal,
            "consumo_diario": diario,
            "dias_cobertura": dias_cob,
            "fecha_quiebre": fecha_quiebre,
            "sugerencia_reponer": reponer,
            "proveedor": a["proveedor"],
        })
    return res


# ---------- Asistente de Chat (Reglas locales + Gemini híbrido + Acciones con confirmación) ----------
_STOPWORDS = {"estuche", "estuches", "embalaje", "personas", "artesanal", "manijas", "para", "con", "rollo", "rollos"}

# Alias de productos usados en las planillas físicas (DIARIA 4 ok / Tienda Nube 1) y el habla cotidiana
_ALIAS_PRODUCTOS: list[tuple[str, str]] = [
    (r"\b(b\s*prem|asador\s+prem|cubiertos\s+prem)", "Estuche Asador con Cubiertos Premium"),
    (r"\b(fernetero\s+doble|fe\s+doble)", "Estuche Fernetero Doble"),
    (r"\b(fernetero|ferneteros|estuche\s+fe\b)", "Estuche Fernetero"),
    (r"\b(familiar\s*(p\s*4|para\s*4|4)|4\s*personas)", "Estuche Familiar (4 Personas)"),
    (r"\b(familiar\s*(doble|2|para\s*2)|2\s*personas|estuche\s+fa\b)", "Estuche Familiar (2 Personas)"),
    (r"\b(familiar|familiares)\b", "Estuche Familiar (2 Personas)"),
    (r"\b(estuche\s+a\b|a\s+neg|a\s+cam\s+azul|para\s+copas)", "Estuche para copas"),
    (r"\b(estuche\s+b\b|asador|asadores)\b", "Estuche Asador"),
    (r"\b(estuche\s+c\b|coctelero|cocteleros)\b", "Estuche Coctelero"),
    (r"\b(mochila|mochilas|campestre)\b", "Mochila Campestre Térmica"),
    (r"\b(tabla\s+con\s+manija|tabla\s+artesanal|manijas)\b", "Tabla de Algarrobo Artesanal con Manijas"),
]


def _norm(s: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[¿?¡!.,;:()\[\]\"'/]", " ", sin_tildes)


def _stem(w: str) -> str:
    return re.sub(r"(es|s)$", "", w)


def resolver_producto_por_alias(articulos: list[dict], texto_norm: str) -> Optional[dict]:
    por_nombre = {a["nombre"].lower(): a for a in articulos if a["tipo"] == "producto"}
    for patron, nombre_oficial in _ALIAS_PRODUCTOS:
        if re.search(patron, texto_norm):
            encontrado = por_nombre.get(nombre_oficial.lower())
            if encontrado:
                return encontrado
    return None


def buscar_articulos_en_texto(articulos: list[dict], texto_norm: str) -> list[dict]:
    best = 0
    res = []
    for a in articulos:
        palabras = [w for w in _norm(a["nombre"]).split() if len(w) >= 3 and w not in _STOPWORDS]
        score = sum(1 for w in palabras if _stem(w) in texto_norm)
        if score > best:
            best = score
            res = [a]
        elif score == best and score > 0:
            res.append(a)
    if not res:
        alias = resolver_producto_por_alias(articulos, texto_norm)
        if alias:
            return [alias]
    return res


def extraer_items_pedido_de_pregunta(articulos: list[dict], pregunta: str) -> list[dict]:
    """Extrae pares (cantidad, articulo) de frases como 'si me piden 40 asador y 20 fernetero' o 'armé 10 estuches ferneteros'."""
    n = _norm(pregunta)
    bloques = re.findall(r"(\d+)\s+([a-z0-9\s]{1,45}?)(?=\s+y\s+\d+|\s*,\s*\d+|\s+o\s+\d+|$)", n)
    items = []
    for cant_str, frag in bloques:
        cant = int(cant_str)
        if cant <= 0 or cant > 10000:
            continue
        if re.match(r"^(dia|dias|semana|semanas|mes|meses|ano|anos)\b", frag.strip()):
            continue
        alias_prod = resolver_producto_por_alias(articulos, frag)
        if alias_prod:
            items.append({"articulo_id": alias_prod["id"], "cantidad": cant})
            continue
        coincidencias = buscar_articulos_en_texto(articulos, frag)
        if coincidencias:
            elegido = min(coincidencias, key=lambda a: (0 if a["tipo"] == "producto" else 1, len(a["nombre"])))
            items.append({"articulo_id": elegido["id"], "cantidad": cant})
    return items


def es_comando_armado(texto_norm: str) -> bool:
    """Detecta si el usuario está informando que armó/produjo estuches para cargarlos al stock."""
    if re.search(r"\b(cuanto|cuantos|puedo|podemos|falta|faltan|hay que|si arm|para armar|me piden)\b", texto_norm):
        return False
    return bool(
        re.search(
            r"\b(hice|hicimos|arme|armamos|prepare|preparamos|produje|produjimos|termine de armar|cargar armado|registrar armado)\b",
            texto_norm,
        )
    )


def preparar_propuesta_armado(con, pregunta: str) -> Optional[dict]:
    """Si el mensaje es del tipo 'hice o armé 10 estuches ferneteros', arma la propuesta con confirmación."""
    n = _norm(pregunta)
    if not es_comando_armado(n):
        return None
    articulos = [dict(r) for r in con.execute("SELECT * FROM articulos WHERE activo = 1 ORDER BY orden, id")]
    art_map = {a["id"]: a for a in articulos}
    items_extraidos = extraer_items_pedido_de_pregunta(articulos, pregunta)
    items_prod = [it for it in items_extraidos if art_map.get(it["articulo_id"], {}).get("tipo") == "producto"]
    if not items_prod:
        return None

    # Agrupar por si repitió el mismo producto en la frase
    agrupados: dict[int, int] = {}
    for it in items_prod:
        aid = it["articulo_id"]
        agrupados[aid] = agrupados.get(aid, 0) + int(it["cantidad"])

    recetas = _recetas_dict(con)
    propuesta_items = []
    hay_faltantes = False
    lineas = [
        "🛠️ Confirmación de armado:",
        "¿Confirmás que está bien lo que voy a cargar en el stock?\n",
    ]
    consumo_acum: dict[int, int] = {}

    for aid, cant in agrupados.items():
        prod = art_map[aid]
        rec = recetas.get(aid, [])
        stock_nuevo = prod["stock"] + cant
        lineas.append(
            f"• +{cant} {prod['unidad']} de {prod['nombre']} (stock: pasa de {prod['stock']} a {stock_nuevo} {prod['unidad']})"
        )
        comps_det = []
        faltantes_prod = []
        if rec:
            lineas.append("  Piezas a descontar:")
            for c in rec:
                comp = art_map.get(c["componente_id"])
                if not comp:
                    continue
                req = c["cantidad"] * cant
                usado_previo = consumo_acum.get(comp["id"], 0)
                disp_antes = max(0, comp["stock"] - usado_previo)
                consumo_acum[comp["id"]] = usado_previo + req
                queda = max(0, disp_antes - req)
                falta = max(0, req - disp_antes)
                if falta > 0:
                    hay_faltantes = True
                    faltantes_prod.append(f"{comp['nombre']} (faltan {falta})")
                    lineas.append(
                        f"  - {comp['nombre']}: -{req} {comp['unidad']} (hay {disp_antes} → queda en 0, ⚠️ faltan {falta})"
                    )
                else:
                    lineas.append(
                        f"  - {comp['nombre']}: -{req} {comp['unidad']} (hay {disp_antes} → quedan {queda})"
                    )
                comps_det.append({
                    "componente_id": comp["id"],
                    "nombre": comp["nombre"],
                    "unidad": comp["unidad"],
                    "necesario": req,
                    "stock_actual": disp_antes,
                    "quedaria": queda,
                    "faltante": falta,
                })
        propuesta_items.append({
            "producto_id": prod["id"],
            "nombre": prod["nombre"],
            "unidad": prod["unidad"],
            "cantidad": cant,
            "stock_actual": prod["stock"],
            "stock_nuevo": stock_nuevo,
            "componentes": comps_det,
            "faltantes": faltantes_prod,
        })

    if hay_faltantes:
        lineas.append(
            "\n⚠️ Nota: Algunas piezas tienen stock registrado menor al necesario; si confirmás, esas piezas quedarán en 0."
        )
    lineas.append("\n👉 Tocá «✅ Confirmar y cargar» abajo (o escribí «sí») para registrarlo, o «✕ Cancelar».")

    return {
        "mensaje": "\n".join(lineas),
        "accion": {
            "tipo": "armado",
            "requiere_forzar": hay_faltantes,
            "items": propuesta_items,
        },
    }


def responder_chat_local(con, pregunta: str) -> str:
    prop = preparar_propuesta_armado(con, pregunta)
    if prop:
        return prop["mensaje"]

    n = _norm(pregunta)
    articulos = [dict(r) for r in con.execute("SELECT * FROM articulos WHERE activo = 1 ORDER BY orden, id")]
    comp_map = mapa_comprometido(con)
    recetas = _recetas_dict(con)
    est_label = {"ok": "OK", "low": "Bajo", "crit": "Crítico"}

    def linea_art(a: dict) -> str:
        est = db.estado(a["stock"], a["minimo"], a["critico"])
        comp = comp_map.get(a["id"], 0)
        extra = f" · comprometido: {comp} (disp: {max(0, a['stock'] - comp)})" if comp else ""
        if a["tipo"] == "producto" and a["id"] in recetas:
            arm = min(
                max(0, next((x["stock"] for x in articulos if x["id"] == c["componente_id"]), 0)) // c["cantidad"]
                for c in recetas[a["id"]]
            )
            extra += f" · armables: {arm}"
        return f"• {a['nombre']}: {a['stock']} {a['unidad']} ({est_label[est]}){extra}"

    # 1. ¿Es una pregunta de simulación / pedido grande con cantidades?
    items_sim = extraer_items_pedido_de_pregunta(articulos, pregunta)
    es_intencion_futura = bool(
        re.search(r"alcanz|costear|piden|pedido|encarg|futuro|quedaria|quedan si|necesit|simul|armar", n)
    )
    if items_sim and (es_intencion_futura or len(items_sim) >= 1):
        sim = simular_pedido(con, items_sim, descontar_comprometido=True)
        return sim["resumen_texto"]

    # 2. ¿Pregunta por pedidos futuros / reservas / stock comprometido?
    if re.search(r"pedido.*futuro|futuro.*pedido|reserva|comprometid", n):
        pfs = listar_pedidos_futuros(con, incluir_cerrados=False)
        if not pfs:
            return "No tenés pedidos futuros pendientes cargados en este momento. Podés agendarlos en la pestaña '🔮 Previsión y Pedidos Futuros'."
        lineas = [f"📌 Tenés {len(pfs)} pedido(s) futuro(s) pendiente(s):"]
        for p in pfs:
            det = ", ".join(f"{it['cantidad']}× {it['nombre']}" for it in p["items"])
            fecha_txt = f" (para {p['fecha_estimada']})" if p["fecha_estimada"] else ""
            lineas.append(f"• {p['cliente'] or 'Sin cliente'}{fecha_txt}: {det}")
        return "\n".join(lineas)

    # 3. ¿Pregunta por proyección / para cuántos días alcanza / consumo a futuro?
    coincidencias = buscar_articulos_en_texto(articulos, n)
    if re.search(r"cuantos dias|durar|dura|proyeccion|prever|preveer|prevision|consumo|cuando se acaba", n):
        proy = proyeccion_consumo(con)
        if coincidencias:
            ids_c = {a["id"] for a in coincidencias}
            proy = [p for p in proy if p["articulo_id"] in ids_c]
        con_consumo = [p for p in proy if p["consumo_diario"] > 0]
        if not con_consumo:
            return (
                "Todavía hay pocos despachos registrados para calcular el ritmo de consumo diario.\n"
                "Mientras tanto, podés preguntarme simulaciones directas, por ejemplo:\n"
                "👉 «¿Si me piden 20 Estuche Asador y 10 Fernetero me alcanza y cuánto me queda?»"
            )
        lineas = ["📈 Proyección según el ritmo de salidas:"]
        for p in con_consumo[:10]:
            lineas.append(
                f"• {p['nombre']}: disp. {p['disponible']} {p['unidad']} · sale ~{p['consumo_diario']}/día → "
                f"alcanza para ~{p['dias_cobertura']} días (hasta {p['fecha_quiebre']}). "
                f"Sugerido reponer: {p['sugerencia_reponer']} {p['unidad']}."
            )
        return "\n".join(lineas)

    # 4. Proveedores
    if re.search(r"proveedor|quien.*(vende|compra)|compramos|a quien", n):
        if coincidencias:
            return "\n".join(f"• {a['nombre']}: {a['proveedor'] or 'sin proveedor cargado'}" for a in coincidencias)
        con_prov = [a for a in articulos if a["proveedor"]]
        if not con_prov:
            return "Todavía no hay proveedores cargados."
        return "Proveedores cargados:\n" + "\n".join(f"• {a['nombre']} → {a['proveedor']}" for a in con_prov)

    # 5. Despachos hoy / semana
    if re.search(r"despacho|envio|vend", n):
        dias = 7 if "semana" in n else 1
        desde = (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")
        ds = con.execute("SELECT * FROM despachos WHERE fecha >= ?", (desde,)).fetchall()
        titulo = "Hoy" if dias == 1 else "En los últimos 7 días"
        por_canal = [f"• {c}: {sum(1 for d in ds if d['canal'] == c)}" for c in db.CANALES if any(d["canal"] == c for d in ds)]
        return f"{titulo} hubo {len(ds)} despacho(s)." + ("\n" + "\n".join(por_canal) if por_canal else "")

    # 6. Artículo(s) específico(s)
    if coincidencias and not re.search(r"falta|reponer|bajo|critic", n):
        if len(coincidencias) == 1:
            a = coincidencias[0]
            est = db.estado(a["stock"], a["minimo"], a["critico"])
            comp = comp_map.get(a["id"], 0)
            disp = max(0, a["stock"] - comp)
            txt = f"Hay {a['stock']} {a['unidad']} de {a['nombre']}. Estado: {est_label[est]} (mínimo {a['minimo']}, crítico {a['critico']})."
            if comp:
                txt += f"\n📌 Comprometido en pedidos futuros: {comp} {a['unidad']} → Disponible real: {disp} {a['unidad']}."
            if a["tipo"] == "producto" and a["id"] in recetas:
                arm = min(
                    max(0, next((x["stock"] for x in articulos if x["id"] == c["componente_id"]), 0)) // c["cantidad"]
                    for c in recetas[a["id"]]
                )
                txt += f"\n🛠️ Con tus componentes actuales podés armar {arm} u más."
            if est != "ok":
                txt += f"\n⚠️ Conviene reponer{(' — proveedor: ' + a['proveedor']) if a['proveedor'] else ''}."
            return txt
        total = sum(a["stock"] for a in coincidencias)
        return "Encontré varios:\n" + "\n".join(linea_art(a) for a in coincidencias) + f"\nTotal: {total}"

    # 7. Críticos / faltantes / bajos
    if "critic" in n:
        crits = [a for a in articulos if db.estado(a["stock"], a["minimo"], a["critico"]) == "crit"]
        return "En nivel crítico:\n" + "\n".join(linea_art(a) for a in crits) if crits else "No hay nada en nivel crítico ✅"
    if re.search(r"falta|bajo|poco|reponer|comprar|acaba", n):
        bajos = [a for a in articulos if db.estado(a["stock"], a["minimo"], a["critico"]) != "ok"]
        if not bajos:
            return "No falta nada, está todo por encima del mínimo ✅"
        return "Hay que reponer o armar:\n" + "\n".join(
            linea_art(a) + (f" → {a['proveedor']}" if a["proveedor"] else "") for a in bajos
        )

    # 8. Listados por categoría o general
    if "insumo" in n:
        return "Insumos de embalaje:\n" + "\n".join(linea_art(a) for a in articulos if a["tipo"] == "insumo")
    if "componente" in n or "pieza" in n:
        comps = [a for a in articulos if a["tipo"] == "componente"]
        return "Componentes:\n" + "\n".join(linea_art(a) for a in comps) if comps else "Todavía no cargaste componentes."
    if "producto" in n or "estuche" in n:
        return "Productos de venta:\n" + "\n".join(linea_art(a) for a in articulos if a["tipo"] == "producto")
    if re.search(r"todo|stock|inventario|hay|resumen", n):
        return "Stock completo:\n" + "\n".join(linea_art(a) for a in articulos)

    return (
        "No encontré ese artículo en el catálogo 🤔\n"
        "Podés preguntarme por ejemplo:\n"
        "• «Armé 10 estuches ferneteros» (para confirmar y cargar el armado)\n"
        "• «¿Cuántos Estuche Asador hay?»\n"
        "• «¿Qué falta comprar o armar?»\n"
        "• «Si me piden 30 Estuche Asador y 15 Fernetero, ¿me alcanza y cuánto me queda?»"
    )


def _recetas_dict(con) -> dict[int, list[dict]]:
    res: dict[int, list[dict]] = {}
    for r in con.execute("SELECT * FROM recetas"):
        res.setdefault(r["producto_id"], []).append({"componente_id": r["componente_id"], "cantidad": r["cantidad"]})
    return res


def responder_chat(con, pregunta: str) -> dict:
    """Intenta responder con Gemini usando los cálculos exactos del backend; si es un comando de armado pide confirmación."""
    prop = preparar_propuesta_armado(con, pregunta)
    if prop:
        return {
            "respuesta": prop["mensaje"],
            "modo": "accion",
            "accion_pendiente": prop["accion"],
        }

    respuesta_local = responder_chat_local(con, pregunta)
    c = leer_mapa_config(con)
    api_key = c.get("gemini_api_key", "").strip()
    modelo = c.get("gemini_model", "gemini-2.5-flash").strip() or "gemini-2.5-flash"

    if not api_key:
        return {"respuesta": respuesta_local, "modo": "local"}

    # Preparar contexto exacto para Gemini
    articulos = [dict(r) for r in con.execute("SELECT * FROM articulos WHERE activo = 1 ORDER BY orden, id")]
    items_sim = extraer_items_pedido_de_pregunta(articulos, pregunta)
    sim_txt = simular_pedido(con, items_sim)["resumen_texto"] if items_sim else ""
    proy = proyeccion_consumo(con)
    pfs = listar_pedidos_futuros(con, incluir_cerrados=False)

    contexto = (
        "Sos el asistente de depósito de Enfocados Mendoza (hablá en español argentino, voseo, claro y breve).\n"
        "REGLA ESTRICTA: Usá ÚNICAMENTE los números exactos calculados por el sistema que te paso abajo. No inventes cantidades.\n\n"
        f"RESPUESTA EXACTA CALCULADA POR EL SISTEMA:\n{respuesta_local}\n\n"
    )
    if sim_txt:
        contexto += f"SIMULACIÓN EXACTA DEL PEDIDO:\n{sim_txt}\n\n"
    contexto += "STOCK ACTUAL:\n" + "\n".join(
        f"- {a['nombre']} ({a['tipo']}): stock={a['stock']} {a['unidad']}, mín={a['minimo']}, crít={a['critico']}, prov={a['proveedor'] or '-'}"
        for a in articulos
    )
    if pfs:
        contexto += "\n\nPEDIDOS FUTUROS PENDIENTES:\n" + "\n".join(
            f"- {p['cliente'] or 'Cliente'} ({p['fecha_estimada'] or 'sin fecha'}): " +
            ", ".join(f"{i['cantidad']}x {i['nombre']}" for i in p["items"])
            for p in pfs
        )
    con_cons = [p for p in proy if p["consumo_diario"] > 0]
    if con_cons:
        contexto += "\n\nPROYECCIÓN DE CONSUMO:\n" + "\n".join(
            f"- {p['nombre']}: disp={p['disponible']}, consumo/día={p['consumo_diario']}, cobertura={p['dias_cobertura']} días, sugerido reponer={p['sugerencia_reponer']}"
            for p in con_cons
        )

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=modelo,
            contents=f"{contexto}\n\nPREGUNTA DEL USUARIO: {pregunta}",
        )
        texto = (resp.text or "").strip()
        if texto:
            return {"respuesta": texto, "modo": "gemini"}
    except Exception:
        pass

    return {"respuesta": respuesta_local, "modo": "local"}


# ---------- Lector de Planillas por Foto y Anti-duplicados (Fase 7) ----------
TIPOS_PLANILLA = {
    "diaria": {
        "id": "diaria",
        "titulo": "📋 DIARIA 4 ok (Local / Revendedores / Extras)",
        "canal_defecto": "Local",
        "columnas_ref": "N° · Total unid. · A (Neg./cam Azul) · B · B Prem · Fernetero (Simple/Doble) · Familiar (Doble/P4) · Correa (N/M) · C · M · Fecha · Comprador · Local o Transporte",
    },
    "tiendanube": {
        "id": "tiendanube",
        "titulo": "🛍️ Tienda Nube 1",
        "canal_defecto": "Tienda Nube",
        "columnas_ref": "# (N° pedido) · Total unidades · A (Neg./cam Azul) · B · B Prem · Fernetero (Simple/Doble) · Familiar (Doble/P4) · Correa (N/M) · C · M · Fecha · Comprador · Retiro por local",
    },
    "mercadolibre": {
        "id": "mercadolibre",
        "titulo": "🟡 Mercado Libre",
        "canal_defecto": "Mercado Libre",
        "columnas_ref": "N° de pedido · Fecha · # de pedido · Nombre · Producto · Correa · Cantidad · Factura",
    },
}


def calcular_huella_fila(canal: str, cliente: str, items: list[dict]) -> str:
    """Genera una huella determinística para detectar filas ya cargadas o posibles duplicados."""
    pares = sorted((int(i["articulo_id"]), int(i["cantidad"])) for i in items if int(i.get("cantidad", 0)) > 0)
    base = f"{canal.strip().lower()}|{_norm(cliente or '').strip()}|" + ",".join(f"{a}:{q}" for a, q in pares)
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def enriquecer_y_clasificar_filas(con, tipo_planilla: str, filas_crudas: list[dict]) -> list[dict]:
    """Agrega cajas sugeridas por regla de cantidades y clasifica cada fila contra planilla_filas (anti-duplicados)."""
    articulos = {r["id"]: dict(r) for r in con.execute("SELECT * FROM articulos").fetchall()}
    hace_7d = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
    recientes = [
        dict(r)
        for r in con.execute(
            "SELECT * FROM planilla_filas WHERE fecha >= ? ORDER BY id DESC", (hace_7d,)
        ).fetchall()
    ]

    resultado = []
    for idx, f in enumerate(filas_crudas, start=1):
        nro_fila = str(f.get("nro_fila") or f.get("pedido_nro") or idx).strip()
        canal = f.get("canal") or TIPOS_PLANILLA.get(tipo_planilla, {}).get("canal_defecto", "Local")
        if canal not in db.CANALES:
            canal = TIPOS_PLANILLA.get(tipo_planilla, {}).get("canal_defecto", "Local")
        envio = (f.get("envio") or "").strip()
        if canal == "Revendedor" and envio not in db.ENVIOS:
            envio = "Terminal de ómnibus"
        elif canal != "Revendedor":
            envio = ""

        items_limpios = []
        cant_por_prod: dict[int, int] = {}
        for it in f.get("items", []):
            aid = int(it.get("articulo_id") or 0)
            cant = int(it.get("cantidad") or 0)
            if aid in articulos and cant > 0:
                a = articulos[aid]
                items_limpios.append({
                    "articulo_id": aid,
                    "nombre": a["nombre"],
                    "tipo": a["tipo"],
                    "unidad": a["unidad"],
                    "cantidad": cant,
                })
                if a["tipo"] == "producto":
                    cant_por_prod[aid] = cant_por_prod.get(aid, 0) + cant

        if not items_limpios:
            continue

        # Calcular cajas sugeridas según regla establecida en Despacho
        cajas_map = calcular_cajas_pedido(con, articulos, cant_por_prod)
        cajas_sugeridas = [
            {
                "articulo_id": cid,
                "nombre": articulos[cid]["nombre"],
                "cantidad": req,
            }
            for cid, req in cajas_map.items()
            if cid in articulos and req > 0
        ]

        cliente = (f.get("cliente") or "").strip()
        huella = calcular_huella_fila(canal, cliente, items_limpios)

        # Buscar en planilla_filas por (tipo_planilla, nro_fila)
        existente = con.execute(
            "SELECT * FROM planilla_filas WHERE tipo_planilla = ? AND nro_fila = ? ORDER BY id DESC LIMIT 1",
            (tipo_planilla, nro_fila),
        ).fetchone()

        if existente:
            if existente["huella"] == huella:
                estado_dup = "ya_cargada"
                seleccionada = False
                detalle_dup = f"Ya cargada el {existente['fecha'][:10]} (Despacho #{existente['despacho_id']})"
            else:
                estado_dup = "modificada"
                seleccionada = False
                detalle_dup = f"La fila {nro_fila} ya fue cargada antes con otros datos (Despacho #{existente['despacho_id']})"
        else:
            dup_huella = next((r for r in recientes if r["huella"] == huella), None)
            if dup_huella:
                estado_dup = "posible_duplicado"
                seleccionada = False
                detalle_dup = f"Mismo cliente y productos que fila {dup_huella['nro_fila']} ({dup_huella['fecha'][:10]})"
            else:
                estado_dup = "nueva"
                seleccionada = True
                detalle_dup = "Fila nueva · lista para descontar"

        resultado.append({
            "nro_fila": nro_fila,
            "pedido_nro": (f.get("pedido_nro") or "").strip(),
            "fecha": (f.get("fecha") or datetime.now().strftime("%d/%m")).strip(),
            "canal": canal,
            "envio": envio,
            "cliente": cliente,
            "correa": (f.get("correa") or "").strip(),
            "factura": (f.get("factura") or "").strip(),
            "confianza": f.get("confianza") if f.get("confianza") in ("alta", "media", "baja") else "alta",
            "nota_ia": (f.get("nota_ia") or "").strip(),
            "items": items_limpios,
            "cajas_sugeridas": cajas_sugeridas,
            "incluir_cajas": canal != "Local",
            "huella": huella,
            "estado_dup": estado_dup,
            "seleccionada": seleccionada,
            "detalle_dup": detalle_dup,
        })
    return resultado


def generar_ejemplo_planilla(con, tipo_planilla: str) -> list[dict]:
    """Genera filas de ejemplo realistas basadas en las planillas reales ('DIARIA 4 ok', 'Tienda Nube 1', 'Mercado Libre')."""
    articulos = [dict(r) for r in con.execute("SELECT * FROM articulos WHERE activo = 1").fetchall()]
    por_nom = {a["nombre"]: a["id"] for a in articulos}
    hoy = datetime.now().strftime("%d/%m")

    id_copas = por_nom.get("Estuche para copas", 1)
    id_asador = por_nom.get("Estuche Asador", 2)
    id_asador_prem = por_nom.get("Estuche Asador con Cubiertos Premium", 3)
    id_coctelero = por_nom.get("Estuche Coctelero", 4)
    id_mochila = por_nom.get("Mochila Campestre Térmica", 5)
    id_fernetero = por_nom.get("Estuche Fernetero", 6)
    id_fernetero_dob = por_nom.get("Estuche Fernetero Doble", 7)
    id_fam2 = por_nom.get("Estuche Familiar (2 Personas)", 8)
    id_fam4 = por_nom.get("Estuche Familiar (4 Personas)", 9)

    if tipo_planilla == "tiendanube":
        crudas = [
            {
                "nro_fila": "#1059",
                "pedido_nro": "#1059",
                "fecha": hoy,
                "canal": "Tienda Nube",
                "cliente": "Lucía Fernández",
                "correa": "Negra",
                "confianza": "alta",
                "nota_ia": "Columna C (1) + Fernetero Doble (1) · Correa N",
                "items": [
                    {"articulo_id": id_coctelero, "cantidad": 1},
                    {"articulo_id": id_fernetero_dob, "cantidad": 1},
                ],
            },
            {
                "nro_fila": "#1060",
                "pedido_nro": "#1060",
                "fecha": hoy,
                "canal": "Tienda Nube",
                "cliente": "Martín Gómez (Retiro local)",
                "correa": "",
                "confianza": "alta",
                "nota_ia": "Columna M (2) · Marcado Retiro por local",
                "items": [
                    {"articulo_id": id_mochila, "cantidad": 2},
                ],
            },
            {
                "nro_fila": "#1061",
                "pedido_nro": "#1061",
                "fecha": hoy,
                "canal": "Tienda Nube",
                "cliente": "Sofía Pereyra",
                "correa": "Marrón",
                "confianza": "media",
                "nota_ia": "Caligrafía dudosa en apellido · Columna Familiar Doble (1)",
                "items": [
                    {"articulo_id": id_fam2, "cantidad": 1},
                ],
            },
        ]
    elif tipo_planilla == "mercadolibre":
        crudas = [
            {
                "nro_fila": "1",
                "pedido_nro": "#2000008910",
                "fecha": hoy,
                "canal": "Mercado Libre",
                "cliente": "Carlos Rodríguez",
                "correa": "Negra",
                "factura": "B",
                "confianza": "alta",
                "nota_ia": "Pedido #2000008910 · Factura B",
                "items": [
                    {"articulo_id": id_fernetero, "cantidad": 2},
                ],
            },
            {
                "nro_fila": "2",
                "pedido_nro": "#2000008915",
                "fecha": hoy,
                "canal": "Mercado Libre",
                "cliente": "Ana María López",
                "correa": "Marrón",
                "factura": "A",
                "confianza": "alta",
                "nota_ia": "Pedido #2000008915 · Factura A",
                "items": [
                    {"articulo_id": id_asador_prem, "cantidad": 1},
                ],
            },
            {
                "nro_fila": "3",
                "pedido_nro": "#2000008922",
                "fecha": hoy,
                "canal": "Mercado Libre",
                "cliente": "Diego Sosa",
                "correa": "Negra",
                "factura": "B",
                "confianza": "media",
                "nota_ia": "Correa anotada al margen ('N')",
                "items": [
                    {"articulo_id": id_fam4, "cantidad": 1},
                ],
            },
        ]
    else:
        # DIARIA 4 ok (Local / Revendedor / Extras)
        crudas = [
            {
                "nro_fila": "1409",
                "fecha": hoy,
                "canal": "Revendedor",
                "envio": "Andreani",
                "cliente": "Vinoteca Don Mario",
                "correa": "Negra",
                "confianza": "alta",
                "nota_ia": "Columna B (4) + Fernetero Simple (2) · Transporte: Andreani",
                "items": [
                    {"articulo_id": id_asador, "cantidad": 4},
                    {"articulo_id": id_fernetero, "cantidad": 2},
                ],
            },
            {
                "nro_fila": "1410",
                "fecha": hoy,
                "canal": "Local",
                "envio": "",
                "cliente": "Venta mostrador",
                "correa": "",
                "confianza": "alta",
                "nota_ia": "Columna A Neg. (1) · Local",
                "items": [
                    {"articulo_id": id_copas, "cantidad": 1},
                ],
            },
            {
                "nro_fila": "1411",
                "fecha": hoy,
                "canal": "Revendedor",
                "envio": "Terminal de ómnibus",
                "cliente": "Regalos Empresariales Sur",
                "correa": "Marrón",
                "confianza": "media",
                "nota_ia": "Número corregido a mano en Familiar P/4 (se leyó 2) · Transporte: Terminal",
                "items": [
                    {"articulo_id": id_asador_prem, "cantidad": 3},
                    {"articulo_id": id_fam4, "cantidad": 2},
                ],
            },
        ]

    return enriquecer_y_clasificar_filas(con, tipo_planilla, crudas)


def analizar_planilla_foto(con, tipo_planilla: str, imagen_base64: Optional[str] = None, usar_ejemplo: bool = False) -> dict:
    """Analiza una foto de planilla con Gemini Vision o genera una lectura de ejemplo."""
    if tipo_planilla not in TIPOS_PLANILLA:
        tipo_planilla = "diaria"
    meta_tipo = TIPOS_PLANILLA[tipo_planilla]

    if usar_ejemplo or not imagen_base64:
        filas = generar_ejemplo_planilla(con, tipo_planilla)
        return {
            "modo": "ejemplo",
            "tipo_planilla": tipo_planilla,
            "titulo_planilla": meta_tipo["titulo"],
            "filas": filas,
        }

    c = leer_mapa_config(con)
    api_key = c.get("gemini_api_key", "").strip()
    modelo = c.get("gemini_model", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    if not api_key:
        raise ValueError(
            "Para leer fotos reales con IA necesitás guardar tu clave gratuita de Gemini en ⚙️ Configuración (o tocá «🧪 Probar con ejemplo» para probar el flujo ahora)."
        )

    # Decodificar imagen base64
    raw_b64 = imagen_base64.strip()
    mime_type = "image/jpeg"
    if raw_b64.startswith("data:"):
        cab, _, raw_b64 = raw_b64.partition(",")
        if "image/png" in cab:
            mime_type = "image/png"
        elif "image/webp" in cab:
            mime_type = "image/webp"
    img_bytes = base64.b64decode(raw_b64)

    articulos = [dict(r) for r in con.execute("SELECT * FROM articulos WHERE activo = 1 AND tipo = 'producto' ORDER BY orden, id")]
    catalogo_txt = "\n".join(f"- id={a['id']}: {a['nombre']}" for a in articulos)

    instrucciones_tipo = {
        "diaria": (
            "La imagen es la planilla física 'DIARIA 4 ok' de Enfocados Mendoza.\n"
            "Columnas de izquierda a derecha:\n"
            "- Columna 'N°': número preimpreso de fila (ej: 1409, 1410...).\n"
            "- 'Total unid.': total de unidades de la fila.\n"
            "- 'A Neg.' y 'A cam Azul': corresponden a 'Estuche para copas'.\n"
            "- 'B': corresponde a 'Estuche Asador'.\n"
            "- 'B Prem': corresponde a 'Estuche Asador con Cubiertos Premium'.\n"
            "- 'Fernetero Simple': corresponde a 'Estuche Fernetero'.\n"
            "- 'Fernetero Doble Premium': corresponde a 'Estuche Fernetero Doble'.\n"
            "- 'Familiar Doble Premium': corresponde a 'Estuche Familiar (2 Personas)'.\n"
            "- 'Familiar P/4': corresponde a 'Estuche Familiar (4 Personas)'.\n"
            "- 'Correa N' (Negra) y 'Correa M' (Marrón).\n"
            "- 'C': corresponde a 'Estuche Coctelero'.\n"
            "- 'M': corresponde a 'Mochila Campestre Térmica'.\n"
            "- 'Fecha', 'Ingreso Pauli/Macro', 'Babi', 'Forma de pago', 'Comprador', 'Local o Transporte'.\n"
            "Si en 'Local o Transporte' dice transporte/envío/interior/revendedor, canal='Revendedor' (envio='Terminal de ómnibus' o 'Andreani'); si dice local/mostrador o está vacío, canal='Local'."
        ),
        "tiendanube": (
            "La imagen es la planilla física 'Tienda Nube 1' de Enfocados Mendoza.\n"
            "Columnas de izquierda a derecha:\n"
            "- '#': número preimpreso de pedido (ej: #1059, #1060...).\n"
            "- 'Total unidades', seguido de las columnas de productos: A (Neg/cam Azul = Estuche para copas), B (Estuche Asador), B Prem (Estuche Asador con Cubiertos Premium), Fernetero Simple (Estuche Fernetero), Fernetero Doble Premium (Estuche Fernetero Doble), Familiar Doble Premium (Estuche Familiar (2 Personas)), Familiar P/4 (Estuche Familiar (4 Personas)), Correa (N/M), C (Estuche Coctelero), M (Mochila Campestre Térmica).\n"
            "- 'Fecha', 'Comprador', 'Cuit-Cuil', 'M. Pago', 'Transf', 'Pago de Envío', 'Retiro por local'.\n"
            "El canal siempre es 'Tienda Nube'."
        ),
        "mercadolibre": (
            "La imagen es la planilla física de 'Mercado Libre' de Enfocados Mendoza.\n"
            "Columnas de izquierda a derecha:\n"
            "- 'N° / numero de pedido' (nro_fila)\n"
            "- 'Fecha'\n"
            "- '# de pedido' (pedido_nro)\n"
            "- 'Nombre' (cliente)\n"
            "- 'Producto' (mapear al producto del catálogo)\n"
            "- 'Correa' (Negra / Marrón)\n"
            "- 'Cantidad'\n"
            "- 'Factura'\n"
            "El canal siempre es 'Mercado Libre'."
        ),
    }[tipo_planilla]

    prompt = (
        f"{instrucciones_tipo}\n\n"
        f"CATÁLOGO OFICIAL DE PRODUCTOS (usá estos articulo_id exactos):\n{catalogo_txt}\n\n"
        "Extraé ÚNICAMENTE las filas que estén escritas/completadas a mano (ignorá filas en blanco).\n"
        "Devolvé un JSON con la forma exacta:\n"
        '{"filas": [{"nro_fila": "1409", "pedido_nro": "", "fecha": "11/11", "canal": "Local|Revendedor|Tienda Nube|Mercado Libre", '
        '"envio": "Terminal de ómnibus|Andreani|Retira en local|", "cliente": "Nombre", "correa": "Negra|Marrón|", "factura": "", '
        '"confianza": "alta|media|baja", "nota_ia": "observación breve si hay tachaduras o letra dudosa", '
        '"items": [{"articulo_id": 2, "cantidad": 1}]}]}'
    )

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=modelo,
        contents=[
            types.Part.from_bytes(data=img_bytes, mime_type=mime_type),
            prompt,
        ],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    data_json = json.loads((resp.text or "{}").strip())
    filas_crudas = data_json.get("filas", []) if isinstance(data_json, dict) else []
    filas = enriquecer_y_clasificar_filas(con, tipo_planilla, filas_crudas)
    return {
        "modo": "gemini",
        "tipo_planilla": tipo_planilla,
        "titulo_planilla": meta_tipo["titulo"],
        "filas": filas,
    }


def listar_historial_planillas(con, limite: int = 15) -> list[dict]:
    hojas = [
        dict(r)
        for r in con.execute(
            "SELECT * FROM planilla_hojas ORDER BY id DESC LIMIT ?", (min(max(limite, 1), 100),)
        ).fetchall()
    ]
    for h in hojas:
        h["filas_cargadas"] = con.execute(
            "SELECT COUNT(*) FROM planilla_filas WHERE hoja_id = ?", (h["id"],)
        ).fetchone()[0]
    return hojas


def generar_html_imprimible_ml(desde_nro: int = 1, cantidad_filas: int = 25) -> str:
    """Genera una hoja A4 horizontal imprimible para Mercado Libre con las columnas exactas indicadas por Nacho."""
    filas_html = "\n".join(
        f"""<tr>
          <td class="num">{n}</td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <td class="center">N / M</td>
          <td></td>
          <td></td>
          <td class="center">☐</td>
        </tr>"""
        for n in range(desde_nro, desde_nro + cantidad_filas)
    )
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Planilla Mercado Libre — Enfocados Mendoza</title>
  <style>
    @page {{ size: A4 landscape; margin: 10mm; }}
    body {{ font-family: Arial, sans-serif; color: #111; margin: 0; padding: 12px; }}
    .top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
    h1 {{ font-size: 18px; margin: 0; }}
    .sub {{ font-size: 12px; color: #444; }}
    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
    th, td {{ border: 1.5px solid #222; padding: 6px 6px; font-size: 12px; height: 22px; }}
    th {{ background: #f3f4f6; font-weight: 700; text-transform: uppercase; font-size: 11px; }}
    .num {{ width: 42px; text-align: center; font-weight: bold; background: #fafafa; }}
    .center {{ text-align: center; color: #888; font-size: 11px; }}
    .no-print {{ margin-bottom: 12px; padding: 10px; background: #fef3c7; border: 1px solid #f59e0b; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; }}
    .btn {{ background: #d97706; color: #fff; border: none; padding: 8px 14px; border-radius: 6px; font-weight: bold; cursor: pointer; }}
    @media print {{ .no-print {{ display: none; }} body {{ padding: 0; }} }}
  </style>
</head>
<body>
  <div class="no-print">
    <span>🖨️ <b>Planilla de Mercado Libre lista para imprimir (A4 Horizontal)</b> — Filas prenumeradas para control anti-duplicados</span>
    <button class="btn" onclick="window.print()">Imprimir hoja</button>
  </div>
  <div class="top">
    <div>
      <h1>🟡 ENFOCADOS MENDOZA — PLANILLA MERCADO LIBRE</h1>
      <div class="sub">Códigos rápidos: A (Copas) · B (Asador) · B Prem (Asador Prem.) · Fe (Fernetero) · Fe Doble · Fa Doble (2p) · Fa P/4 (4p) · C (Coctelero) · M (Mochila)</div>
    </div>
    <div class="sub">Hoja N°: _________ &nbsp;&nbsp; Mes/Año: _____________</div>
  </div>
  <table>
    <thead>
      <tr>
        <th style="width:45px">N°</th>
        <th style="width:70px">Fecha</th>
        <th style="width:115px"># de Pedido</th>
        <th style="width:190px">Nombre</th>
        <th>Producto</th>
        <th style="width:70px">Correa</th>
        <th style="width:65px">Cantidad</th>
        <th style="width:75px">Factura</th>
        <th style="width:55px">✓ Sist.</th>
      </tr>
    </thead>
    <tbody>
      {filas_html}
    </tbody>
  </table>
</body>
</html>"""

