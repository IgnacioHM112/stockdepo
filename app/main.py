"""Servidor de StockDepo (FastAPI). Ejecutar con: python -m app  (o iniciar.bat)."""
import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db, servicios

_DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


async def _bucle_tareas_programadas():
    """Revisa cada 60 s si corresponde hacer el respaldo diario o enviar el resumen semanal."""
    while True:
        try:
            hoy = datetime.now().strftime("%Y-%m-%d")
            existentes = servicios.listar_respaldos()
            if not any(r["nombre"].startswith(f"stockdepo_{hoy}") for r in existentes):
                servicios.crear_respaldo("diario")

            ahora_dt = datetime.now()
            dia_actual = _DIAS_SEMANA[ahora_dt.weekday()]
            hora_actual = ahora_dt.strftime("%H:%M")
            with db.transaccion() as con:
                cfg = servicios.leer_mapa_config(con)
                if (
                    cfg.get("mail_on") == "1"
                    and cfg.get("mail_week") == "1"
                    and cfg.get("mail_day") == dia_actual
                    and cfg.get("mail_hour") == hora_actual
                    and cfg.get("ultimo_resumen_semanal") != hoy
                ):
                    servicios.disparar_resumen_semanal(con)
                    con.execute(
                        "INSERT OR REPLACE INTO config (clave, valor) VALUES ('ultimo_resumen_semanal', ?)",
                        (hoy,),
                    )
        except Exception:
            pass
        await asyncio.sleep(60)


@asynccontextmanager
async def _ciclo_de_vida(_app):
    db.inicializar()
    with db.transaccion() as con:
        servicios.asegurar_config(con)
    tarea = asyncio.create_task(_bucle_tareas_programadas())
    try:
        yield
    finally:
        tarea.cancel()
        with suppress(asyncio.CancelledError):
            await tarea


app = FastAPI(title="StockDepo", docs_url="/api/docs", redoc_url=None, lifespan=_ciclo_de_vida)
STATIC_DIR = db.BASE_DIR / "static"


def _usuario(nombre: str) -> str:
    if nombre not in db.USUARIOS:
        raise HTTPException(400, f"Usuario desconocido: {nombre}")
    return nombre


def _recetas_por_producto(con) -> dict[int, list[dict]]:
    sql = """SELECT r.producto_id, r.componente_id, r.cantidad,
                    c.nombre, c.unidad, c.stock
             FROM recetas r
             JOIN articulos c ON c.id = r.componente_id
             ORDER BY c.orden, c.id"""
    res: dict[int, list[dict]] = {}
    for row in con.execute(sql):
        res.setdefault(row["producto_id"], []).append({
            "componente_id": row["componente_id"],
            "nombre": row["nombre"],
            "unidad": row["unidad"],
            "stock": row["stock"],
            "cantidad": row["cantidad"],
        })
    return res


def _articulo_dict(
    r,
    recetas_map: Optional[dict[int, list[dict]]] = None,
    comp_map: Optional[dict[int, int]] = None,
) -> dict:
    d = dict(r)
    d["estado"] = db.estado(d["stock"], d["minimo"], d["critico"])
    comprometido = (comp_map or {}).get(d["id"], 0)
    d["comprometido"] = comprometido
    d["disponible"] = max(0, d["stock"] - comprometido)
    if d["tipo"] == "producto":
        rec = (recetas_map or {}).get(d["id"], [])
        d["receta"] = rec
        d["armables"] = min((c["stock"] // c["cantidad"] for c in rec), default=None) if rec else None
    else:
        d["receta"] = []
        d["armables"] = None
    return d


def _articulo_con_receta(con, articulo_id: int) -> dict:
    r = con.execute("SELECT * FROM articulos WHERE id = ?", (articulo_id,)).fetchone()
    if r is None:
        raise HTTPException(404, "Artículo inexistente")
    return _articulo_dict(r, _recetas_por_producto(con), servicios.mapa_comprometido(con))


def _regla_cajas(con) -> dict:
    return servicios.obtener_regla_cajas(con)


# ---------- Meta y configuración de cajas ----------
@app.get("/api/meta")
def meta():
    with db.transaccion() as con:
        return {
            "usuarios": db.USUARIOS,
            "tipos": db.TIPOS,
            "canales": db.CANALES,
            "envios": db.ENVIOS,
            "regla_cajas": _regla_cajas(con),
        }


class ReglaCajasIn(BaseModel):
    chica_capacidad: Optional[int] = Field(None, ge=1, le=100)
    mediana_desde: Optional[int] = Field(None, ge=2, le=100)
    mediana_capacidad: Optional[int] = Field(None, ge=1, le=100)
    grande_desde: Optional[int] = Field(None, ge=2, le=500)
    grande_capacidad: Optional[int] = Field(None, ge=1, le=500)
    respetar_caja_minima: Optional[bool] = None
    # Alias de compatibilidad
    caja_grande_desde_unidades: Optional[int] = Field(None, ge=1, le=500)
    unidades_por_caja_grande: Optional[int] = Field(None, ge=1, le=500)


@app.put("/api/config/cajas")
def guardar_regla_cajas(rc: ReglaCajasIn):
    with db.transaccion() as con:
        return servicios.guardar_regla_cajas(con, rc.model_dump(exclude_none=True))


# ---------- Artículos ----------
class ArticuloNuevo(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    tipo: str
    unidad: str = "u"
    stock: int = Field(0, ge=0)
    minimo: int = Field(0, ge=0)
    critico: int = Field(0, ge=0)
    proveedor: str = ""
    caja_id: Optional[int] = None
    usuario: str


class ArticuloEdicion(BaseModel):
    nombre: Optional[str] = Field(None, min_length=1, max_length=120)
    unidad: Optional[str] = None
    minimo: Optional[int] = Field(None, ge=0)
    critico: Optional[int] = Field(None, ge=0)
    proveedor: Optional[str] = None
    caja_id: Optional[int] = None
    activo: Optional[bool] = None


class Ajuste(BaseModel):
    delta: int
    usuario: str
    motivo: str = "Ajuste manual"


class Orden(BaseModel):
    ids: list[int]


class RecetaItemIn(BaseModel):
    componente_id: int
    cantidad: int = Field(gt=0)


class RecetaIn(BaseModel):
    items: list[RecetaItemIn]


@app.get("/api/articulos")
def listar_articulos(incluir_inactivos: bool = False):
    with db.transaccion() as con:
        rec_map = _recetas_por_producto(con)
        comp_map = servicios.mapa_comprometido(con)
        sql = "SELECT * FROM articulos" + ("" if incluir_inactivos else " WHERE activo = 1") + " ORDER BY orden, id"
        return [_articulo_dict(r, rec_map, comp_map) for r in con.execute(sql)]


@app.post("/api/articulos", status_code=201)
def crear_articulo(a: ArticuloNuevo):
    _usuario(a.usuario)
    if a.tipo not in db.TIPOS:
        raise HTTPException(400, "Tipo inválido")
    if a.critico > a.minimo:
        raise HTTPException(400, "El crítico no puede ser mayor que el mínimo")
    with db.transaccion() as con:
        if con.execute("SELECT 1 FROM articulos WHERE nombre = ?", (a.nombre.strip(),)).fetchone():
            raise HTTPException(409, "Ya existe un artículo con ese nombre")
        orden = con.execute("SELECT COALESCE(MAX(orden), -1) + 1 FROM articulos").fetchone()[0]
        cur = con.execute(
            """INSERT INTO articulos (nombre, tipo, unidad, minimo, critico, proveedor, caja_id, orden)
               VALUES (?,?,?,?,?,?,?,?)""",
            (a.nombre.strip(), a.tipo, a.unidad.strip() or "u", a.minimo, a.critico,
             a.proveedor.strip(), a.caja_id, orden),
        )
        nuevo_id = cur.lastrowid
        if a.stock:
            db.cambiar_stock(con, nuevo_id, a.stock, a.usuario, "Stock inicial")
        return _articulo_con_receta(con, nuevo_id)


@app.patch("/api/articulos/{articulo_id}")
def editar_articulo(articulo_id: int, e: ArticuloEdicion):
    cambios = e.model_dump(exclude_unset=True)
    if not cambios:
        raise HTTPException(400, "Nada para cambiar")
    with db.transaccion() as con:
        a = con.execute("SELECT * FROM articulos WHERE id = ?", (articulo_id,)).fetchone()
        if a is None:
            raise HTTPException(404, "Artículo inexistente")
        minimo = cambios.get("minimo", a["minimo"])
        critico = cambios.get("critico", a["critico"])
        if critico > minimo:
            raise HTTPException(400, "El crítico no puede ser mayor que el mínimo")
        if "nombre" in cambios:
            cambios["nombre"] = cambios["nombre"].strip()
            dup = con.execute("SELECT 1 FROM articulos WHERE nombre = ? AND id <> ?",
                              (cambios["nombre"], articulo_id)).fetchone()
            if dup:
                raise HTTPException(409, "Ya existe un artículo con ese nombre")
        if "activo" in cambios:
            cambios["activo"] = int(cambios["activo"])
        sets = ", ".join(f"{k} = ?" for k in cambios)
        con.execute(f"UPDATE articulos SET {sets} WHERE id = ?", (*cambios.values(), articulo_id))
        return _articulo_con_receta(con, articulo_id)


@app.post("/api/articulos/{articulo_id}/ajuste")
def ajustar_stock(articulo_id: int, aj: Ajuste):
    _usuario(aj.usuario)
    if aj.delta == 0:
        raise HTTPException(400, "El ajuste no puede ser 0")
    with db.transaccion() as con:
        try:
            db.cambiar_stock(con, articulo_id, aj.delta, aj.usuario, aj.motivo.strip() or "Ajuste manual")
        except ValueError as ex:
            raise HTTPException(404, str(ex))
        return _articulo_con_receta(con, articulo_id)


@app.put("/api/articulos/orden")
def guardar_orden(o: Orden):
    with db.transaccion() as con:
        for i, aid in enumerate(o.ids):
            con.execute("UPDATE articulos SET orden = ? WHERE id = ?", (i, aid))
    return {"ok": True}


@app.put("/api/articulos/{producto_id}/receta")
def guardar_receta(producto_id: int, rec: RecetaIn):
    with db.transaccion() as con:
        prod = con.execute("SELECT * FROM articulos WHERE id = ?", (producto_id,)).fetchone()
        if prod is None or prod["tipo"] != "producto":
            raise HTTPException(400, "Solo los productos pueden tener receta de armado")
        agregados: dict[int, int] = {}
        for it in rec.items:
            if it.componente_id == producto_id:
                raise HTTPException(400, "Un producto no puede ser componente de sí mismo")
            comp = con.execute("SELECT * FROM articulos WHERE id = ?", (it.componente_id,)).fetchone()
            if comp is None or comp["tipo"] == "producto":
                raise HTTPException(400, f"Componente inválido ({it.componente_id})")
            agregados[it.componente_id] = agregados.get(it.componente_id, 0) + it.cantidad
        con.execute("DELETE FROM recetas WHERE producto_id = ?", (producto_id,))
        for cid, cant in agregados.items():
            con.execute(
                "INSERT INTO recetas (producto_id, componente_id, cantidad) VALUES (?,?,?)",
                (producto_id, cid, cant),
            )
        return _articulo_con_receta(con, producto_id)


# ---------- Armados (producción de estuches) ----------
class ArmadoNuevo(BaseModel):
    usuario: str
    producto_id: int
    cantidad: int = Field(gt=0)
    nota: str = ""
    forzar: bool = False


@app.get("/api/armados")
def listar_armados(limite: int = 20):
    with db.transaccion() as con:
        sql = """SELECT ar.*, a.nombre AS producto_nombre
                 FROM armados ar
                 JOIN articulos a ON a.id = ar.producto_id
                 ORDER BY ar.id DESC LIMIT ?"""
        return [dict(r) for r in con.execute(sql, (min(max(limite, 1), 200),))]


@app.post("/api/armados", status_code=201)
def registrar_armado(ar: ArmadoNuevo):
    _usuario(ar.usuario)
    with db.transaccion() as con:
        prod = con.execute("SELECT * FROM articulos WHERE id = ?", (ar.producto_id,)).fetchone()
        if prod is None or prod["tipo"] != "producto":
            raise HTTPException(400, "Producto inválido")
        receta = _recetas_por_producto(con).get(ar.producto_id, [])
        faltantes = []
        for comp in receta:
            req = comp["cantidad"] * ar.cantidad
            if comp["stock"] < req:
                faltantes.append(f"{comp['nombre']} (necesitás {req} {comp['unidad']}, hay {comp['stock']})")
        if faltantes and not ar.forzar:
            raise HTTPException(400, "No alcanzan los componentes: " + ", ".join(faltantes))

        nota = ar.nota.strip()
        cur = con.execute(
            "INSERT INTO armados (fecha, usuario, producto_id, cantidad, nota) VALUES (?,?,?,?,?)",
            (db.ahora(), ar.usuario, ar.producto_id, ar.cantidad, nota or None),
        )
        armado_id = cur.lastrowid
        motivo_prod = f"Armado #{armado_id}" + (f" · {nota}" if nota else "")
        db.cambiar_stock(con, ar.producto_id, ar.cantidad, ar.usuario, motivo_prod, armado_id=armado_id)
        for comp in receta:
            req = comp["cantidad"] * ar.cantidad
            motivo_comp = f"Armado #{armado_id} ({ar.cantidad}× {prod['nombre']})"
            db.cambiar_stock(con, comp["componente_id"], -req, ar.usuario, motivo_comp, armado_id=armado_id)
        return {
            "id": armado_id,
            "producto": _articulo_con_receta(con, ar.producto_id),
            "componentes_descontados": len(receta),
        }


# ---------- Ingresos (compras / reposición) ----------
class IngresoNuevo(BaseModel):
    usuario: str
    articulo_id: int
    cantidad: int = Field(gt=0)
    proveedor: str = ""
    precio: Optional[float] = Field(None, ge=0)
    nota: str = ""


@app.get("/api/ingresos")
def listar_ingresos(limite: int = 25):
    with db.transaccion() as con:
        sql = """SELECT i.*, a.nombre AS articulo_nombre, a.unidad, a.tipo
                 FROM ingresos i
                 JOIN articulos a ON a.id = i.articulo_id
                 ORDER BY i.id DESC LIMIT ?"""
        return [dict(r) for r in con.execute(sql, (min(max(limite, 1), 200),))]


@app.post("/api/ingresos", status_code=201)
def registrar_ingreso(ing: IngresoNuevo):
    _usuario(ing.usuario)
    with db.transaccion() as con:
        a = con.execute("SELECT * FROM articulos WHERE id = ?", (ing.articulo_id,)).fetchone()
        if a is None:
            raise HTTPException(404, "Artículo inexistente")
        prov = ing.proveedor.strip()
        nota = ing.nota.strip()
        cur = con.execute(
            """INSERT INTO ingresos (fecha, usuario, articulo_id, cantidad, proveedor, precio, nota)
               VALUES (?,?,?,?,?,?,?)""",
            (db.ahora(), ing.usuario, ing.articulo_id, ing.cantidad, prov or None, ing.precio, nota or None),
        )
        ingreso_id = cur.lastrowid
        if prov:
            con.execute("UPDATE articulos SET proveedor = ? WHERE id = ?", (prov, ing.articulo_id))
        motivo = f"Ingreso #{ingreso_id}" + (f" · {prov}" if prov else "") + (f" ({nota})" if nota else "")
        db.cambiar_stock(con, ing.articulo_id, ing.cantidad, ing.usuario, motivo, ingreso_id=ingreso_id)
        return {
            "id": ingreso_id,
            "articulo": _articulo_con_receta(con, ing.articulo_id),
        }


# ---------- Despachos (ventas / salidas) ----------
class DespachoItemIn(BaseModel):
    articulo_id: int
    cantidad: int = Field(gt=0)


class DespachoNuevo(BaseModel):
    usuario: str
    canal: str
    envio: str = ""
    cliente: str = ""
    origen: str = "manual"
    items: list[DespachoItemIn]


def _hidratar_despachos(con, filas) -> list[dict]:
    if not filas:
        return []
    ids = [r["id"] for r in filas]
    placeholders = ",".join("?" * len(ids))
    sql_items = f"""SELECT di.despacho_id, di.articulo_id, di.cantidad,
                           a.nombre, a.tipo, a.unidad
                    FROM despacho_items di
                    JOIN articulos a ON a.id = di.articulo_id
                    WHERE di.despacho_id IN ({placeholders})
                    ORDER BY di.id"""
    items_map: dict[int, list[dict]] = {}
    for it in con.execute(sql_items, ids):
        items_map.setdefault(it["despacho_id"], []).append({
            "articulo_id": it["articulo_id"],
            "nombre": it["nombre"],
            "tipo": it["tipo"],
            "unidad": it["unidad"],
            "cantidad": it["cantidad"],
        })
    res = []
    for r in filas:
        d = dict(r)
        d["items"] = items_map.get(d["id"], [])
        res.append(d)
    return res


def _crear_despacho_en_tx(con, d: DespachoNuevo) -> dict:
    _usuario(d.usuario)
    if d.canal not in db.CANALES:
        raise HTTPException(400, f"Canal inválido: {d.canal}")
    envio = d.envio.strip() if d.canal == "Revendedor" else ""
    if d.canal == "Revendedor" and envio not in db.ENVIOS:
        raise HTTPException(400, "Elegí la forma de envío del revendedor")
    if not d.items:
        raise HTTPException(400, "Agregá al menos un producto o insumo al despacho")

    agregados: dict[int, int] = {}
    for it in d.items:
        agregados[it.articulo_id] = agregados.get(it.articulo_id, 0) + it.cantidad

    nombres: dict[int, str] = {}
    for aid in agregados:
        row = con.execute("SELECT id, nombre FROM articulos WHERE id = ?", (aid,)).fetchone()
        if row is None:
            raise HTTPException(404, f"Artículo {aid} inexistente")
        nombres[aid] = row["nombre"]

    cli = d.cliente.strip()
    origen = "foto" if d.origen == "foto" else "manual"
    cur = con.execute(
        "INSERT INTO despachos (fecha, usuario, canal, envio, cliente, origen) VALUES (?,?,?,?,?,?)",
        (db.ahora(), d.usuario, d.canal, envio or None, cli or None, origen),
    )
    desp_id = cur.lastrowid
    ref = f"Despacho #{desp_id} · {d.canal}" + (f" ({envio})" if envio else "") + (f" · {cli}" if cli else "")

    resumen = []
    for aid, cant in agregados.items():
        con.execute(
            "INSERT INTO despacho_items (despacho_id, articulo_id, cantidad) VALUES (?,?,?)",
            (desp_id, aid, cant),
        )
        db.cambiar_stock(con, aid, -cant, d.usuario, ref, despacho_id=desp_id)
        resumen.append(f"−{cant} {nombres[aid]}")

    msg_notif = (
        f"Despacho #{desp_id} ({d.canal}{' · ' + envio if envio else ''}) "
        f"cargado por {d.usuario}{' (desde foto)' if origen == 'foto' else ''}: {', '.join(resumen)}."
    )
    db.notificar(con, "desp", msg_notif)

    fila = con.execute("SELECT * FROM despachos WHERE id = ?", (desp_id,)).fetchone()
    return _hidratar_despachos(con, [fila])[0]


@app.get("/api/despachos")
def listar_despachos(dias: Optional[int] = None, limite: int = 50):
    with db.transaccion() as con:
        params: list = []
        sql = "SELECT * FROM despachos"
        if dias is not None and dias > 0:
            desde = (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")
            sql += " WHERE fecha >= ?"
            params.append(desde)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(min(max(limite, 1), 500))
        filas = con.execute(sql, params).fetchall()
        return _hidratar_despachos(con, filas)


@app.post("/api/despachos", status_code=201)
def registrar_despacho(d: DespachoNuevo):
    with db.transaccion() as con:
        return _crear_despacho_en_tx(con, d)


# ---------- Panel ----------
@app.get("/api/panel")
def datos_panel():
    with db.transaccion() as con:
        hoy_prefijo = datetime.now().strftime("%Y-%m-%d")
        despachos_hoy = con.execute(
            "SELECT COUNT(*) FROM despachos WHERE fecha LIKE ?", (f"{hoy_prefijo}%",)
        ).fetchone()[0]
        desde_7d = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
        filas_sem = con.execute(
            "SELECT * FROM despachos WHERE fecha >= ? ORDER BY id DESC", (desde_7d,)
        ).fetchall()
        return {
            "despachos_hoy": despachos_hoy,
            "despachos_semana": _hidratar_despachos(con, filas_sem),
        }


# ---------- Avisos (Fase 4) ----------
@app.get("/api/notificaciones/no-leidas")
def notificaciones_no_leidas():
    with db.transaccion() as con:
        return {"cantidad": con.execute("SELECT COUNT(*) FROM notificaciones WHERE leida = 0").fetchone()[0]}


@app.get("/api/avisos")
def obtener_avisos(limite: int = 50):
    with db.transaccion() as con:
        notifs = [
            dict(r)
            for r in con.execute(
                "SELECT * FROM notificaciones ORDER BY id DESC LIMIT ?", (min(max(limite, 1), 200),)
            )
        ]
        return {
            "notificaciones": notifs,
            "config": servicios.estado_avisos_config(con),
        }


@app.put("/api/avisos/config")
def actualizar_config_avisos(cfg: dict):
    with db.transaccion() as con:
        return servicios.guardar_avisos_config(con, cfg)


@app.post("/api/avisos/leer-todas")
def marcar_avisos_leidos():
    with db.transaccion() as con:
        con.execute("UPDATE notificaciones SET leida = 1 WHERE leida = 0")
    return {"ok": True}


@app.post("/api/avisos/resumen-prueba")
def enviar_resumen_prueba():
    with db.transaccion() as con:
        return servicios.disparar_resumen_semanal(con)


# ---------- Configuración, Red LAN/QR y Respaldos (Fase 5) ----------
class ClavesIn(BaseModel):
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    gmail_app_password: Optional[str] = None
    mail_from: Optional[str] = None


class RestaurarIn(BaseModel):
    nombre: str


@app.get("/api/sistema/info")
def info_sistema():
    ip = servicios.obtener_ip_lan()
    url_lan = f"http://{ip}:8000"
    with db.transaccion() as con:
        c = servicios.leer_mapa_config(con)
        return {
            "ip_lan": ip,
            "url_lan": url_lan,
            "qr_svg": servicios.generar_qr_svg(url_lan),
            "tiene_gemini_key": bool(c.get("gemini_api_key", "").strip()),
            "gemini_model": c.get("gemini_model", "gemini-2.5-flash"),
            "tiene_gmail_pass": bool(c.get("gmail_app_password", "").strip()),
            "mail_from": c.get("mail_from", ""),
            "respaldos": servicios.listar_respaldos(),
        }


@app.put("/api/sistema/claves")
def guardar_claves(cl: ClavesIn):
    with db.transaccion() as con:
        servicios.asegurar_config(con)
        if cl.gemini_api_key is not None:
            con.execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('gemini_api_key', ?)",
                        (cl.gemini_api_key.strip(),))
        if cl.gemini_model is not None and cl.gemini_model.strip():
            con.execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('gemini_model', ?)",
                        (cl.gemini_model.strip(),))
        if cl.gmail_app_password is not None:
            con.execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('gmail_app_password', ?)",
                        (cl.gmail_app_password.strip(),))
        if cl.mail_from is not None:
            con.execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('mail_from', ?)",
                        (cl.mail_from.strip(),))
    return info_sistema()


@app.post("/api/sistema/probar-gemini")
def probar_gemini():
    with db.transaccion() as con:
        c = servicios.leer_mapa_config(con)
        key = c.get("gemini_api_key", "").strip()
        modelo = c.get("gemini_model", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    if not key:
        raise HTTPException(400, "Primero guardá la clave de Gemini")
    try:
        from google import genai
        client = genai.Client(api_key=key)
        r = client.models.generate_content(model=modelo, contents="Respondé únicamente con la palabra: CONECTADO")
        return {"ok": True, "modelo": modelo, "respuesta": (r.text or "").strip()}
    except Exception as ex:
        raise HTTPException(400, f"No se pudo conectar con Gemini: {ex}")


@app.post("/api/sistema/probar-gmail")
def probar_gmail():
    with db.transaccion() as con:
        ok, detalle = servicios.enviar_gmail(
            con,
            "Prueba de conexión — StockDepo (Enfocados Mendoza)",
            "¡Hola! Este es un correo de prueba enviado desde StockDepo para verificar que los avisos por Gmail funcionan correctamente.",
        )
    if not ok:
        raise HTTPException(400, detalle)
    return {"ok": True, "detalle": detalle}


@app.post("/api/sistema/respaldos", status_code=201)
def crear_respaldo_manual():
    return servicios.crear_respaldo("manual")


@app.post("/api/sistema/respaldos/restaurar")
def restaurar_respaldo_endpoint(r: RestaurarIn):
    try:
        return servicios.restaurar_respaldo(r.nombre)
    except ValueError as ex:
        raise HTTPException(400, str(ex))


# ---------- Previsión, Pedidos futuros y Asistente (Fase 6) ----------
class ChatIn(BaseModel):
    pregunta: str = Field(min_length=1, max_length=600)


class SimulacionItemIn(BaseModel):
    articulo_id: int
    cantidad: int = Field(gt=0)


class SimulacionIn(BaseModel):
    items: list[SimulacionItemIn]
    descontar_comprometido: bool = True


class PedidoFuturoNuevo(BaseModel):
    usuario: str
    cliente: str = ""
    fecha_estimada: str = ""
    nota: str = ""
    items: list[SimulacionItemIn]


class ConcretarPedidoIn(BaseModel):
    usuario: str
    canal: str = "Revendedor"
    envio: str = "Retira en local"


@app.post("/api/chat")
def chat_endpoint(ch: ChatIn):
    with db.transaccion() as con:
        return servicios.responder_chat(con, ch.pregunta)


@app.post("/api/prevision/simular")
def simular_endpoint(sim: SimulacionIn):
    if not sim.items:
        raise HTTPException(400, "Agregá al menos un artículo para simular")
    with db.transaccion() as con:
        return servicios.simular_pedido(
            con,
            [{"articulo_id": i.articulo_id, "cantidad": i.cantidad} for i in sim.items],
            descontar_comprometido=sim.descontar_comprometido,
        )


@app.get("/api/prevision/proyeccion")
def proyeccion_endpoint(dias_historial: int = 30, dias_objetivo: int = 14):
    with db.transaccion() as con:
        return servicios.proyeccion_consumo(con, dias_historial=dias_historial, dias_objetivo=dias_objetivo)


@app.get("/api/pedidos-futuros")
def obtener_pedidos_futuros(incluir_cerrados: bool = False):
    with db.transaccion() as con:
        return servicios.listar_pedidos_futuros(con, incluir_cerrados=incluir_cerrados)


@app.post("/api/pedidos-futuros", status_code=201)
def crear_pedido_futuro(pf: PedidoFuturoNuevo):
    _usuario(pf.usuario)
    if not pf.items:
        raise HTTPException(400, "Agregá al menos un artículo al pedido futuro")
    with db.transaccion() as con:
        cur = con.execute(
            """INSERT INTO pedidos_futuros (fecha_alta, usuario, cliente, fecha_estimada, estado, nota)
               VALUES (?,?,?,?,'pendiente',?)""",
            (db.ahora(), pf.usuario, pf.cliente.strip() or None, pf.fecha_estimada.strip() or None, pf.nota.strip() or None),
        )
        pid = cur.lastrowid
        agregados: dict[int, int] = {}
        for it in pf.items:
            agregados[it.articulo_id] = agregados.get(it.articulo_id, 0) + it.cantidad
        for aid, cant in agregados.items():
            if not con.execute("SELECT 1 FROM articulos WHERE id = ?", (aid,)).fetchone():
                raise HTTPException(404, f"Artículo {aid} inexistente")
            con.execute(
                "INSERT INTO pedido_futuro_items (pedido_id, articulo_id, cantidad) VALUES (?,?,?)",
                (pid, aid, cant),
            )
        return next(p for p in servicios.listar_pedidos_futuros(con, incluir_cerrados=True) if p["id"] == pid)


@app.post("/api/pedidos-futuros/{pedido_id}/cancelar")
def cancelar_pedido_futuro(pedido_id: int):
    with db.transaccion() as con:
        p = con.execute("SELECT * FROM pedidos_futuros WHERE id = ?", (pedido_id,)).fetchone()
        if p is None:
            raise HTTPException(404, "Pedido futuro inexistente")
        con.execute("UPDATE pedidos_futuros SET estado = 'cancelado' WHERE id = ?", (pedido_id,))
        return {"ok": True}


@app.post("/api/pedidos-futuros/{pedido_id}/concretar")
def concretar_pedido_futuro(pedido_id: int, cp: ConcretarPedidoIn):
    _usuario(cp.usuario)
    with db.transaccion() as con:
        p = con.execute("SELECT * FROM pedidos_futuros WHERE id = ?", (pedido_id,)).fetchone()
        if p is None or p["estado"] != "pendiente":
            raise HTTPException(400, "El pedido futuro no existe o ya fue procesado")
        items_rows = con.execute(
            "SELECT articulo_id, cantidad FROM pedido_futuro_items WHERE pedido_id = ?", (pedido_id,)
        ).fetchall()
        desp = _crear_despacho_en_tx(
            con,
            DespachoNuevo(
                usuario=cp.usuario,
                canal=cp.canal,
                envio=cp.envio if cp.canal == "Revendedor" else "",
                cliente=p["cliente"] or f"Pedido futuro #{pedido_id}",
                origen="manual",
                items=[DespachoItemIn(articulo_id=r["articulo_id"], cantidad=r["cantidad"]) for r in items_rows],
            ),
        )
        con.execute("UPDATE pedidos_futuros SET estado = 'concretado' WHERE id = ?", (pedido_id,))
        return {"ok": True, "despacho": desp}


# ---------- Lector de Planillas por Foto y Anti-duplicados (Fase 7) ----------
class AnalizarPlanillaIn(BaseModel):
    tipo_planilla: str = "diaria"
    imagen_base64: Optional[str] = None
    usar_ejemplo: bool = False


class PlanillaFilaConfirmarIn(BaseModel):
    nro_fila: str = ""
    pedido_nro: str = ""
    fecha: str = ""
    canal: str
    envio: str = ""
    cliente: str = ""
    correa: str = ""
    factura: str = ""
    incluir_cajas: bool = True
    seleccionada: bool = True
    items: list[DespachoItemIn]
    cajas_sugeridas: list[DespachoItemIn] = []


class ConfirmarPlanillaIn(BaseModel):
    usuario: str
    tipo_planilla: str = "diaria"
    id_hoja: str = ""
    filas: list[PlanillaFilaConfirmarIn]


@app.get("/api/planillas")
def info_planillas():
    excel_path = db.BASE_DIR / "planillas en blanco NUEVA.xlsx"
    with db.transaccion() as con:
        return {
            "tipos": list(servicios.TIPOS_PLANILLA.values()),
            "historial": servicios.listar_historial_planillas(con, limite=15),
            "tiene_excel": excel_path.exists(),
        }


@app.post("/api/planillas/analizar")
def analizar_planilla_endpoint(ap: AnalizarPlanillaIn):
    with db.transaccion() as con:
        try:
            return servicios.analizar_planilla_foto(
                con,
                tipo_planilla=ap.tipo_planilla,
                imagen_base64=ap.imagen_base64,
                usar_ejemplo=ap.usar_ejemplo,
            )
        except ValueError as ex:
            raise HTTPException(400, str(ex))
        except Exception as ex:
            raise HTTPException(400, f"No se pudo analizar la imagen: {ex}")


@app.post("/api/planillas/confirmar", status_code=201)
def confirmar_planilla_endpoint(cp: ConfirmarPlanillaIn):
    _usuario(cp.usuario)
    seleccionadas = [f for f in cp.filas if f.seleccionada and f.items]
    if not seleccionadas:
        raise HTTPException(400, "Tildá al menos una fila con productos para confirmar")

    tipo = cp.tipo_planilla if cp.tipo_planilla in servicios.TIPOS_PLANILLA else "diaria"
    titulo = servicios.TIPOS_PLANILLA[tipo]["titulo"]
    import json as _json

    with db.transaccion() as con:
        cur_h = con.execute(
            "INSERT INTO planilla_hojas (fecha, usuario, tipo_planilla, id_hoja, resumen) VALUES (?,?,?,?,?)",
            (db.ahora(), cp.usuario, tipo, cp.id_hoja.strip() or None, f"{len(seleccionadas)} fila(s)"),
        )
        hoja_id = cur_h.lastrowid
        despachos_creados = []

        for f in seleccionadas:
            items_desp = list(f.items)
            if f.incluir_cajas and f.cajas_sugeridas:
                items_desp.extend(f.cajas_sugeridas)

            cli_partes = [p for p in [f.cliente.strip(), f.pedido_nro.strip(), (f"Correa {f.correa.strip()}" if f.correa.strip() else "")] if p]
            cliente_final = " · ".join(cli_partes) if cli_partes else f"Fila {f.nro_fila}"

            desp = _crear_despacho_en_tx(
                con,
                DespachoNuevo(
                    usuario=cp.usuario,
                    canal=f.canal,
                    envio=f.envio if f.canal == "Revendedor" else "",
                    cliente=cliente_final,
                    origen="foto",
                    items=items_desp,
                ),
            )
            despachos_creados.append(desp)

            items_puros = [{"articulo_id": i.articulo_id, "cantidad": i.cantidad} for i in f.items]
            huella = servicios.calcular_huella_fila(f.canal, f.cliente, items_puros)
            con.execute(
                """INSERT INTO planilla_filas
                   (hoja_id, tipo_planilla, nro_fila, huella, canal, envio, cliente, correa, factura, items_json, despacho_id, fecha)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    hoja_id,
                    tipo,
                    str(f.nro_fila or f.pedido_nro or len(despachos_creados)).strip(),
                    huella,
                    f.canal,
                    f.envio.strip() or None,
                    f.cliente.strip() or None,
                    f.correa.strip() or None,
                    f.factura.strip() or None,
                    _json.dumps(items_puros, ensure_ascii=False),
                    desp["id"],
                    db.ahora(),
                ),
            )

        db.notificar(
            con,
            "photo",
            f"Planilla {titulo} confirmada por {cp.usuario}: {len(despachos_creados)} fila(s) descontadas del stock.",
        )
        return {
            "ok": True,
            "hoja_id": hoja_id,
            "filas_procesadas": len(despachos_creados),
            "despachos": despachos_creados,
        }


@app.get("/api/planillas/imprimible-ml", response_class=HTMLResponse)
def planilla_imprimible_ml(desde: int = 1, filas: int = 25):
    return HTMLResponse(servicios.generar_html_imprimible_ml(desde_nro=max(1, desde), cantidad_filas=min(max(filas, 5), 60)))


@app.get("/api/planillas/excel")
def descargar_excel_planillas():
    excel_path = db.BASE_DIR / "planillas en blanco NUEVA.xlsx"
    if not excel_path.exists():
        raise HTTPException(404, "No se encontró el archivo Excel de planillas")
    return FileResponse(
        excel_path,
        filename="planillas en blanco NUEVA.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------- Movimientos ----------
@app.get("/api/movimientos")
def listar_movimientos(articulo_id: Optional[int] = None, limite: int = 50):
    with db.transaccion() as con:
        sql = """SELECT m.*, a.nombre AS articulo, a.unidad FROM movimientos m
                 JOIN articulos a ON a.id = m.articulo_id"""
        params: list = []
        if articulo_id:
            sql += " WHERE m.articulo_id = ?"
            params.append(articulo_id)
        sql += " ORDER BY m.id DESC LIMIT ?"
        params.append(min(max(limite, 1), 500))
        return [dict(r) for r in con.execute(sql, params)]


# ---------- Frontend ----------
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")
