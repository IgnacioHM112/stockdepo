"""Base de datos SQLite de StockDepo: esquema, datos iniciales y la función única de cambio de stock."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "stockdepo.db"

USUARIOS = ["Nacho", "Pablo", "Mauricio"]
TIPOS = ["producto", "componente", "insumo"]
CANALES = ["Local", "Revendedor", "Mercado Libre", "Tienda Nube"]
ENVIOS = ["Terminal de ómnibus", "Andreani", "Retira en local"]

ESQUEMA = """
CREATE TABLE IF NOT EXISTS articulos (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre    TEXT NOT NULL UNIQUE COLLATE NOCASE,
    tipo      TEXT NOT NULL CHECK (tipo IN ('producto','componente','insumo')),
    unidad    TEXT NOT NULL DEFAULT 'u',
    stock     INTEGER NOT NULL DEFAULT 0,
    minimo    INTEGER NOT NULL DEFAULT 0,
    critico   INTEGER NOT NULL DEFAULT 0,
    proveedor TEXT NOT NULL DEFAULT '',
    orden     INTEGER NOT NULL DEFAULT 0,
    activo    INTEGER NOT NULL DEFAULT 1,
    caja_id   INTEGER REFERENCES articulos(id)  -- caja de envío por defecto (productos)
);

CREATE TABLE IF NOT EXISTS recetas (
    producto_id   INTEGER NOT NULL REFERENCES articulos(id),
    componente_id INTEGER NOT NULL REFERENCES articulos(id),
    cantidad      INTEGER NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (producto_id, componente_id)
);

CREATE TABLE IF NOT EXISTS despachos (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha   TEXT NOT NULL,
    usuario TEXT NOT NULL,
    canal   TEXT NOT NULL,
    envio   TEXT,
    cliente TEXT,
    origen  TEXT NOT NULL DEFAULT 'manual'
);

CREATE TABLE IF NOT EXISTS despacho_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    despacho_id INTEGER NOT NULL REFERENCES despachos(id),
    articulo_id INTEGER NOT NULL REFERENCES articulos(id),
    cantidad    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ingresos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha       TEXT NOT NULL,
    usuario     TEXT NOT NULL,
    articulo_id INTEGER NOT NULL REFERENCES articulos(id),
    cantidad    INTEGER NOT NULL,
    proveedor   TEXT,
    precio      REAL,
    nota        TEXT
);

CREATE TABLE IF NOT EXISTS armados (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha       TEXT NOT NULL,
    usuario     TEXT NOT NULL,
    producto_id INTEGER NOT NULL REFERENCES articulos(id),
    cantidad    INTEGER NOT NULL,
    nota        TEXT
);

CREATE TABLE IF NOT EXISTS movimientos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha       TEXT NOT NULL,
    usuario     TEXT NOT NULL,
    articulo_id INTEGER NOT NULL REFERENCES articulos(id),
    delta       INTEGER NOT NULL,
    stock_final INTEGER NOT NULL,
    motivo      TEXT NOT NULL,
    despacho_id INTEGER REFERENCES despachos(id),
    ingreso_id  INTEGER REFERENCES ingresos(id),
    armado_id   INTEGER REFERENCES armados(id)
);
CREATE INDEX IF NOT EXISTS ix_mov_articulo ON movimientos(articulo_id, fecha);

CREATE TABLE IF NOT EXISTS pedidos_futuros (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_alta     TEXT NOT NULL,
    usuario        TEXT NOT NULL,
    cliente        TEXT,
    fecha_estimada TEXT,
    estado         TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente','concretado','cancelado')),
    nota           TEXT
);

CREATE TABLE IF NOT EXISTS pedido_futuro_items (
    pedido_id   INTEGER NOT NULL REFERENCES pedidos_futuros(id),
    articulo_id INTEGER NOT NULL REFERENCES articulos(id),
    cantidad    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS notificaciones (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha        TEXT NOT NULL,
    tipo         TEXT NOT NULL,
    mensaje      TEXT NOT NULL,
    leida        INTEGER NOT NULL DEFAULT 0,
    enviada_mail INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS config (
    clave TEXT PRIMARY KEY,
    valor TEXT
);

CREATE TABLE IF NOT EXISTS planilla_hojas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha         TEXT NOT NULL,
    usuario       TEXT NOT NULL,
    tipo_planilla TEXT NOT NULL,
    id_hoja       TEXT,
    resumen       TEXT
);

CREATE TABLE IF NOT EXISTS planilla_filas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    hoja_id       INTEGER REFERENCES planilla_hojas(id),
    tipo_planilla TEXT NOT NULL,
    nro_fila      TEXT NOT NULL,
    huella        TEXT NOT NULL,
    canal         TEXT NOT NULL,
    envio         TEXT,
    cliente       TEXT,
    correa        TEXT,
    factura       TEXT,
    items_json    TEXT NOT NULL,
    despacho_id   INTEGER REFERENCES despachos(id),
    fecha         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_pf_clave ON planilla_filas(tipo_planilla, nro_fila);
"""

# (nombre, tipo, unidad, minimo, critico, caja por defecto)
ARTICULOS_INICIALES = [
    ("Estuche para copas", "producto", "u", 6, 3, "Caja chica"),
    ("Estuche Asador", "producto", "u", 6, 3, "Caja chica"),
    ("Estuche Asador con Cubiertos Premium", "producto", "u", 5, 2, "Caja mediana"),
    ("Estuche Coctelero", "producto", "u", 4, 2, "Caja chica"),
    ("Mochila Campestre Térmica", "producto", "u", 4, 2, "Caja mediana"),
    ("Estuche Fernetero", "producto", "u", 6, 3, "Caja chica"),
    ("Estuche Fernetero Doble", "producto", "u", 4, 2, "Caja mediana"),
    ("Estuche Familiar (2 Personas)", "producto", "u", 4, 2, "Caja mediana"),
    ("Estuche Familiar (4 Personas)", "producto", "u", 3, 1, "Caja mediana"),
    ("Tabla de Algarrobo Artesanal con Manijas", "producto", "u", 5, 2, "Caja chica"),
    ("Cinta de embalaje", "insumo", "rollos", 4, 2, None),
    ("Film negro de embalaje", "insumo", "rollos", 2, 1, None),
    ("Rollo de burbujas", "insumo", "rollos", 2, 1, None),
    ("Caja chica", "insumo", "u", 20, 10, None),
    ("Caja mediana", "insumo", "u", 15, 6, None),
    ("Caja grande", "insumo", "u", 5, 2, None),
]

# (nombre, unidad, minimo, critico)
COMPONENTES_INICIALES = [
    # Estuches vacíos y correas
    ("Estuche vacío A (Copas)", "u", 6, 3),
    ("Estuche vacío B (Asador)", "u", 8, 4),
    ("Estuche vacío C (Coctelero)", "u", 4, 2),
    ("Estuche vacío Fe (Fernetero)", "u", 8, 4),
    ("Estuche vacío Fa (Familiar)", "u", 6, 3),
    ("Mochila vacía (Campestre)", "u", 4, 2),
    ("Correa para estuche", "u", 15, 6),
    # Copas y vasos
    ("Copa de vino Brunello 390 ml", "u", 20, 8),
    ("Copa coctelera Brunello 600 ml", "u", 6, 3),
    ("Vaso de aluminio 1 L", "u", 10, 4),
    ("Vaso de aluminio 500 ml", "u", 6, 3),
    ("Vaso telescópico", "u", 6, 2),
    ("Vaso (mochila)", "u", 12, 4),
    # Cubiertos y fundas/porta cubiertos
    ("Par de cubiertos comunes", "u", 20, 8),
    ("Par de cubiertos premium", "u", 20, 8),
    ("Funda de gabardina para cubiertos", "u", 12, 5),
    ("Caja de madera porta cubiertos", "u", 4, 2),
    # Tablas y platos
    ("Tabla de madera de pino", "u", 15, 6),
    ("Tabla de algarrobo", "u", 15, 6),
    ("Tabla de eucalipto", "u", 10, 4),
    ("Plato (mochila)", "u", 12, 4),
    # Otros accesorios
    ("Caja truquera", "u", 5, 2),
    ("Destapador", "u", 5, 2),
    ("Set de botánicos", "u", 4, 2),
    ("Bombilla metálica", "u", 4, 2),
    ("Mini botellita de Fernet", "u", 10, 4),
    ("Manta impermeable", "u", 4, 2),
]

# Receta por producto: {nombre_producto: [(nombre_componente, cantidad), ...]}
RECETAS_INICIALES = {
    "Estuche para copas": [
        ("Estuche vacío A (Copas)", 1),
        ("Copa de vino Brunello 390 ml", 2),
    ],
    "Estuche Asador": [
        ("Estuche vacío B (Asador)", 1),
        ("Correa para estuche", 1),
        ("Copa de vino Brunello 390 ml", 1),
        ("Par de cubiertos comunes", 1),
        ("Tabla de madera de pino", 1),
    ],
    "Estuche Asador con Cubiertos Premium": [
        ("Estuche vacío B (Asador)", 1),
        ("Correa para estuche", 1),
        ("Copa de vino Brunello 390 ml", 1),
        ("Par de cubiertos premium", 1),
        ("Tabla de algarrobo", 1),
        ("Caja truquera", 1),
        ("Destapador", 1),
    ],
    "Estuche Coctelero": [
        ("Estuche vacío C (Coctelero)", 1),
        ("Copa coctelera Brunello 600 ml", 1),
        ("Par de cubiertos premium", 1),
        ("Caja de madera porta cubiertos", 1),
        ("Tabla de madera de pino", 1),
        ("Set de botánicos", 1),
        ("Bombilla metálica", 1),
    ],
    "Mochila Campestre Térmica": [
        ("Mochila vacía (Campestre)", 1),
        ("Par de cubiertos comunes", 4),
        ("Plato (mochila)", 4),
        ("Vaso (mochila)", 4),
        ("Tabla de madera de pino", 1),
        ("Manta impermeable", 1),
    ],
    "Estuche Fernetero": [
        ("Estuche vacío Fe (Fernetero)", 1),
        ("Correa para estuche", 1),
        ("Vaso de aluminio 1 L", 1),
        ("Mini botellita de Fernet", 1),
        ("Par de cubiertos premium", 1),
        ("Funda de gabardina para cubiertos", 1),
        ("Tabla de algarrobo", 1),
    ],
    "Estuche Fernetero Doble": [
        ("Estuche vacío Fe (Fernetero)", 1),
        ("Correa para estuche", 1),
        ("Vaso de aluminio 1 L", 1),
        ("Vaso de aluminio 500 ml", 1),
        ("Mini botellita de Fernet", 1),
        ("Par de cubiertos premium", 2),
        ("Funda de gabardina para cubiertos", 1),
        ("Tabla de algarrobo", 2),
    ],
    "Estuche Familiar (2 Personas)": [
        ("Estuche vacío Fa (Familiar)", 1),
        ("Correa para estuche", 1),
        ("Copa de vino Brunello 390 ml", 2),
        ("Par de cubiertos premium", 2),
        ("Funda de gabardina para cubiertos", 1),
        ("Tabla de algarrobo", 2),
    ],
    "Estuche Familiar (4 Personas)": [
        ("Estuche vacío Fa (Familiar)", 1),
        ("Correa para estuche", 1),
        ("Copa de vino Brunello 390 ml", 2),
        ("Par de cubiertos comunes", 4),
        ("Funda de gabardina para cubiertos", 1),
        ("Tabla de madera de pino", 4),
        ("Vaso telescópico", 2),
    ],
}

CONFIG_INICIAL = {
    "orden_inicializado": "1",
    # Regla establecida de cajas por cantidad de unidades (editable en Despacho)
    "caja_chica_capacidad": "2",
    "caja_mediana_desde_unidades": "3",
    "caja_mediana_capacidad": "9",
    "caja_grande_desde_unidades": "10",
    "unidades_por_caja_grande": "15",
    "respetar_caja_minima_producto": "0",
}


def ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def conectar() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


@contextmanager
def transaccion():
    con = conectar()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def inicializar():
    with transaccion() as con:
        con.executescript(ESQUEMA)
        if con.execute("SELECT COUNT(*) FROM articulos").fetchone()[0] == 0:
            for orden, (nombre, tipo, unidad, minimo, critico, _) in enumerate(ARTICULOS_INICIALES):
                con.execute(
                    "INSERT INTO articulos (nombre, tipo, unidad, minimo, critico, orden) VALUES (?,?,?,?,?,?)",
                    (nombre, tipo, unidad, minimo, critico, orden),
                )
            for nombre, *_, caja in ARTICULOS_INICIALES:
                if caja:
                    con.execute(
                        "UPDATE articulos SET caja_id = (SELECT id FROM articulos WHERE nombre = ?) WHERE nombre = ?",
                        (caja, nombre),
                    )
        for k, v in CONFIG_INICIAL.items():
            con.execute("INSERT OR IGNORE INTO config (clave, valor) VALUES (?, ?)", (k, v))

        # Cargar componentes y recetas iniciales si aún no fueron cargados
        rec_init = con.execute("SELECT valor FROM config WHERE clave = 'recetas_inicializadas'").fetchone()
        if not rec_init:
            base_orden = con.execute("SELECT COALESCE(MAX(orden), -1) + 1 FROM articulos").fetchone()[0]
            for idx, (nombre, unidad, minimo, critico) in enumerate(COMPONENTES_INICIALES):
                con.execute(
                    "INSERT OR IGNORE INTO articulos (nombre, tipo, unidad, minimo, critico, orden) VALUES (?,?,?,?,?,?)",
                    (nombre, "componente", unidad, minimo, critico, base_orden + idx),
                )
            for prod_nom, comp_lista in RECETAS_INICIALES.items():
                p_row = con.execute("SELECT id FROM articulos WHERE nombre = ?", (prod_nom,)).fetchone()
                if not p_row:
                    continue
                for comp_nom, cant in comp_lista:
                    c_row = con.execute("SELECT id FROM articulos WHERE nombre = ?", (comp_nom,)).fetchone()
                    if c_row:
                        con.execute(
                            "INSERT OR IGNORE INTO recetas (producto_id, componente_id, cantidad) VALUES (?,?,?)",
                            (p_row["id"], c_row["id"], cant),
                        )
            con.execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('recetas_inicializadas', '1')")


def estado(stock: int, minimo: int, critico: int) -> str:
    if stock <= critico:
        return "crit"
    if stock <= minimo:
        return "low"
    return "ok"


def notificar(con, tipo: str, mensaje: str):
    """Registra una notificación en la app y/o envía Gmail según la configuración."""
    cfg = dict(con.execute("SELECT clave, valor FROM config").fetchall())
    in_app = cfg.get("app_on", "1") == "1" and cfg.get(f"app_{tipo}", "1") == "1"
    by_mail = cfg.get("mail_on", "0") == "1" and cfg.get(f"mail_{tipo}", "0") == "1"
    if not in_app and not by_mail:
        return

    mail_enviado = 0
    if by_mail and cfg.get("gmail_app_password", "").strip():
        try:
            from . import servicios
            ok, _ = servicios.enviar_gmail(con, f"[StockDepo] Aviso ({tipo.upper()})", mensaje)
            mail_enviado = 1 if ok else 0
        except Exception:
            mail_enviado = 0

    con.execute(
        "INSERT INTO notificaciones (fecha, tipo, mensaje, leida, enviada_mail) VALUES (?,?,?,?,?)",
        (ahora(), tipo, mensaje, 0 if in_app else 1, mail_enviado),
    )


def cambiar_stock(con, articulo_id: int, delta: int, usuario: str, motivo: str,
                  despacho_id=None, ingreso_id=None, armado_id=None) -> dict:
    """ÚNICA función que modifica el stock. Registra el movimiento y genera avisos
    cuando el artículo cambia de estado (OK → Bajo → Crítico)."""
    a = con.execute("SELECT * FROM articulos WHERE id = ?", (articulo_id,)).fetchone()
    if a is None:
        raise ValueError(f"Artículo {articulo_id} inexistente")
    antes = estado(a["stock"], a["minimo"], a["critico"])
    nuevo = max(0, a["stock"] + delta)
    delta_real = nuevo - a["stock"]
    con.execute("UPDATE articulos SET stock = ? WHERE id = ?", (nuevo, articulo_id))
    con.execute(
        """INSERT INTO movimientos (fecha, usuario, articulo_id, delta, stock_final, motivo,
                                    despacho_id, ingreso_id, armado_id)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (ahora(), usuario, articulo_id, delta_real, nuevo, motivo, despacho_id, ingreso_id, armado_id),
    )
    despues = estado(nuevo, a["minimo"], a["critico"])
    if despues != antes and despues != "ok" and delta_real < 0:
        if despues == "crit":
            msg = f"{a['nombre']} llegó a nivel CRÍTICO ({nuevo} {a['unidad']})."
        else:
            msg = f"{a['nombre']} está BAJO ({nuevo} {a['unidad']}, mínimo {a['minimo']})."
        notificar(con, despues, msg)
    return {"id": articulo_id, "stock": nuevo, "estado": despues}
