# PROYECTO STOCKDEPO — Documento maestro para cualquier IA / desarrollador

> **LEER ESTO PRIMERO.** Este archivo describe QUÉ estamos construyendo, POR QUÉ, las DECISIONES ya tomadas
> y en QUÉ FASE estamos. Si sos una IA que retoma el proyecto: leé todo, revisá la sección
> "Estado actual" y el "Registro de avances", y continuá desde la primera tarea sin tildar.
> **Al terminar cada tarea, actualizá este archivo** (tildá `[x]` y agregá una línea al registro).

- **Idioma:** responder al usuario SIEMPRE en **español** (Argentina, voseo). Código, nombres de tablas y comentarios pueden ir en español.
- **Última actualización:** 2026-11-18
- **Carpeta del proyecto:** `C:\Users\ignam\Desktop\Proyectos\stockdepo\` (movida el 2026-11-11)
- **Mockup de referencia (diseño aprobado v0.2):** `docs/mockup_v0.2.html` (abrir en el navegador; es la guía visual y funcional)

---

## 1. Contexto del negocio

- **Negocio:** Enfocados Mendoza (tienda: https://enfocadosmendoza.mitiendanube.com/). Venden estuches/sets (asador, fernetero, copas, coctelero, etc.).
- **Usuarios:** 3 personas → **Nacho** (encargado de depósito, el usuario), **Pablo**, **Mauricio**. **Sin login/contraseña** por ahora: solo se elige el nombre en un selector.
- **Equipo:** notebook común, **8 GB RAM, Windows 11**, prendida durante el horario laboral. Funcionará como "servidor" local.
- **Situación actual:** el stock NO se anota en ningún lado; las ventas se anotan en **planillas de papel**. Cuando algo se acaba, se avisa al jefe de palabra.
- **Canales de venta:**
  - **Local** (venta presencial)
  - **Revendedor** → con sub-opción de forma de salida: **Terminal de ómnibus**, **Andreani**, **Retira en local**
  - **Mercado Libre**
  - **Tienda Nube**
- **Futuro deseado:** pasar de planillas de papel a planillas virtuales / Google Docs-Sheets.

## 2. Requisitos NO negociables

1. **100 % gratuito** (software, librerías, servicios). Nada pago.
2. **Local**, sin despliegue en la nube. La app corre en la notebook.
3. Accesible desde **celular** por el WiFi del local (red LAN).
4. Debe ser **más rápido que la planilla de papel**, si no, no se usa.
5. Todo lo configurable (avisos, mínimos, destinatarios) debe ser **editable desde la app**.

## 3. Alcance funcional (lo que pidió el usuario)

### Artículos
- Tres tipos: **Productos de venta** (~10, estuches armados), **Componentes** (piezas con las que se arman los estuches: copas, cuchillos, tablas, caja del estuche, etc.) e **Insumos de embalaje**.
- **Todos los estuches los arma Nacho** a partir de componentes → cada producto tiene una **receta** (qué componentes y cuántos lleva). Se registra el **Armado** (ej. "armé 10 Estuche Asador": +10 producto, −componentes según receta). Los componentes reales y las recetas los carga el usuario desde la app.
- **Escala establecida de cajas por cantidad (configurable y guardada desde Despacho):** por defecto **1 a 2 u → Caja chica** (entran 2 u por caja), **3 a 9 u → Caja mediana** (entran 9 u por caja) y **a partir de 10 u → Caja grande** (entran 15 u por caja). Tanto los cortes de cantidad ("pasar a Mediana desde…", "pasar a Grande desde…") como la capacidad máxima de cada caja quedan guardados en la base y son editables desde el botón `⚙️ Configurar cantidades por caja` en Despacho. Se aplican automáticamente en el despacho y en las simulaciones de previsión.
- Productos actuales (de la tienda): Estuche para copas · Estuche Asador · Estuche Asador con Cubiertos Premium · Estuche Coctelero · Mochila Campestre Térmica · Estuche Fernetero · Estuche Fernetero Doble · Estuche Familiar (2 Personas) · Estuche Familiar (4 Personas) · Tabla de Algarrobo Artesanal con Manijas.
- Insumos: Cinta de embalaje (rollos) · Film negro de embalaje (rollos) · Rollo de burbujas (rollos) · Caja chica · Caja mediana · Caja grande. (El usuario cargará otros a mano si aparecen.)
- **Sin códigos de barras.** Se manejan por nombre.
- Cada artículo tiene: stock, unidad, **stock mínimo** (aviso "bajo"), **stock crítico**, proveedor (opcional).
- **Rollos (cinta, film, burbujas): se cuentan rollos enteros.** No se pueden medir: se descuenta 1 cuando un rollo se termina (checkbox en el despacho).
- **Cajas:** cantidad variable por despacho; se carga a mano cuántas de cada tamaño se usaron.

### Pantallas (ver mockup)
1. **Panel:** KPIs (artículos, bajos, críticos, despachos hoy) · "Requiere atención" (bajos/críticos con botón +Ingreso) · **"Pedidos por canal"**: un desplegable por canal (ej. "Pedidos de Mercado Libre") que al abrirse muestra pedidos con productos, unidades y fecha. ⚠️ El usuario NO quiere una lista de movimientos detallada en el panel.
2. **Stock:** tabla con filtro (Todos/Productos/Insumos), búsqueda, barra de nivel, estado (OK/Bajo/Crítico), edición de mín/crít, ajuste rápido ±1. **Ordenamiento:** "Mi orden" (personalizado con flechas ▲▼, se guarda) + Nombre, Menor stock, Críticos primero, Por tipo.
3. **Despacho:** canal (chips) → si es Revendedor, elegir forma de salida (Terminal/Andreani/Retira en local) · cliente/referencia opcional · productos + cantidades · cajas usadas · checkboxes "se terminó un rollo". Al guardar descuenta todo y genera avisos.
4. **Planilla (foto + IA):** subir foto desde el celular (cámara) **o** desde la notebook (archivo). La IA extrae líneas (canal, envío, cliente, producto, cantidad, caja) → **tabla editable de revisión** con nivel de confianza (✅/⚠️/❗) → nada se descuenta hasta "Confirmar". Las líneas se agrupan en despachos.
5. **Ingreso** (antes "Compra"; el usuario pidió este nombre): artículo, cantidad, **proveedor opcional** (persona o empresa, con autocompletado), precio y nota opcionales.
6. **Avisos:** centro de notificaciones + **configuración SEPARADA** en dos tarjetas:
   - 📱 **App:** interruptor general, al cargar despacho, al cargar planilla por foto, stock bajo, stock crítico.
   - ✉️ **Gmail:** interruptor general, cuenta remitente, cada despacho (apagado por defecto), bajo, crítico, **resumen semanal** (día + hora editables), lista de destinatarios editable, botón "enviar prueba".
7. **Asistente (chat):** preguntas en lenguaje natural sobre cantidades, faltantes, proveedores, despachos por día/semana. Debe responder también cuando algo NO existe.
8. **Configuración:** clave Gemini, contraseña de aplicación Gmail, botones "Probar", IP/QR para entrar desde el celular, respaldos.

### Previsión y pedidos futuros (pedido del usuario 2026-11-11)
El asistente no solo responde sobre el stock actual, sino también **a futuro**:
- **Simulación ("¿me alcanza?"):** ej. "Si me piden 40 Estuches Asador y 20 Fernetero para el 15/12, ¿me alcanza?" → responde por artículo: stock actual, lo que se usaría, **cuánto quedaría**, **cuánto falta** (si falta) y en qué estado quedaría (OK/Bajo/Crítico). Si no hay suficientes estuches armados, calcula **cuántos se pueden armar con los componentes** y qué **componentes faltan** (según receta). Incluye cajas estimadas.
- **Pedidos futuros (reservas):** se pueden registrar pedidos grandes conocidos de antemano (cliente, fecha estimada, productos y cantidades). **No descuentan stock**; generan **stock comprometido**. Disponible = stock − comprometido. Al concretarse, se convierte en despacho con un clic (o se cancela).
- **Proyección por consumo:** con el historial de despachos se calcula el consumo promedio y se estima **"te alcanza para ~N días"** / fecha estimada de quiebre por artículo, y sugerencia de cuánto reponer.
- Modelo de datos extra: `pedidos_futuros` (id, fecha_alta, usuario, cliente, fecha_estimada, estado[pendiente|concretado|cancelado], nota), `pedido_futuro_items` (pedido_id, articulo_id, cantidad). Recetas y cajas: ver modelo de datos (sección 4).
- El cálculo lo hace **siempre el backend** (números exactos); Gemini solo interpreta la pregunta y redacta la respuesta. El asistente local por reglas también debe soportar las preguntas básicas de simulación.

## 4. Decisiones técnicas tomadas

| Tema | Decisión | Motivo |
|---|---|---|
| Arquitectura | App web local: servidor en la notebook, se usa desde el navegador (notebook y celulares en la misma WiFi) | Gratis, sin nube, multi-dispositivo |
| Backend | **Python 3.11+ con FastAPI** + Uvicorn (host `0.0.0.0`, puerto `8000`) | Simple, liviano |
| Base de datos | **SQLite** (un archivo `data/stockdepo.db`) | Cero instalación, fácil de respaldar |
| Frontend | HTML + JavaScript vanilla basado en el mockup. **CSS servido localmente** (no depender de CDN; debe funcionar sin internet) | Liviano, offline |
| Avisos en app | Tabla `notificaciones` + campanita (consulta periódica cada ~30 s) | Gratis |
| Email | **Gmail SMTP** (`smtp.gmail.com:465` SSL) con **contraseña de aplicación** | Gratis |
| Tareas programadas | APScheduler dentro del servidor (resumen semanal, respaldo diario) | Sin servicios externos |
| Chat | **Híbrido:** Gemini (nivel gratuito) si hay internet y clave; si no, **asistente local por reglas/palabras clave** (ya prototipado en el mockup, función `answer()`) | IA local con 8 GB RAM sería demasiado lenta |
| Lectura de fotos | **Gemini API nivel gratuito** (modelo Flash con visión), salida en JSON estructurado; validar nombres contra el catálogo | OCR local no lee bien letra manuscrita |
| SDK Gemini | `google-genai` (Python). Modelo configurable desde la app | |
| Seguridad de claves | Claves guardadas solo en la notebook (`data/config.json` o tabla `config`), **nunca** en el código ni en git | |
| Arranque | `iniciar.bat` (doble clic) + opción de inicio automático con Windows. Regla de firewall para red privada | Uso no técnico |
| Respaldos | Copia diaria de la DB a `backups/` (conservar 30) | |

> **Privacidad:** en el nivel gratuito de Gemini, Google puede usar lo enviado para mejorar sus servicios. El usuario fue informado y aceptó. Solo se envían la foto de la planilla y las preguntas del chat con datos de stock.

### Modelo de datos (propuesta inicial)
- `articulos` (id, nombre, tipo[producto|componente|insumo], unidad, stock, minimo, critico, proveedor, orden, activo, caja_id NULL → caja de envío por defecto del producto)
- `recetas` (producto_id, componente_id, cantidad) → de qué está hecho cada estuche
- `armados` (id, fecha, usuario, producto_id, cantidad, nota) → +producto, −componentes (vía movimientos)
- `movimientos` (id, fecha, usuario, articulo_id, delta, motivo, despacho_id NULL, ingreso_id NULL, armado_id NULL)
- `despachos` (id, numero, fecha, usuario, canal, envio NULL, cliente NULL, origen[manual|foto])
- `despacho_items` (id, despacho_id, articulo_id, cantidad)
- `ingresos` (id, fecha, usuario, articulo_id, cantidad, proveedor, precio, nota)
- `notificaciones` (id, fecha, tipo[desp|low|crit|week|foto], mensaje, leida, enviada_mail)
- `config` (clave, valor) → toggles de avisos, destinatarios, día/hora resumen, claves API
- `planillas_foto` (id, fecha, usuario, ruta_imagen, json_extraido, estado[pendiente|confirmada|descartada])

Regla: **todo cambio de stock pasa por una única función** que registra el movimiento y evalúa transiciones de estado (OK→Bajo→Crítico) para disparar avisos.

## 5. Fases de desarrollo

### Fase 0 — Definición y mockup ✅
- [x] Relevamiento de requisitos con el usuario
- [x] Mockup v0.1 y revisión manuscrita del usuario
- [x] Mockup v0.2 con correcciones (`docs/mockup_v0.2.html`)
- [x] Decisiones técnicas (sección 4)

### Fase 1 — Base del sistema ✅
- [x] Verificar/instalar Python en la notebook; crear entorno virtual y `requirements.txt`
- [x] Estructura de carpetas (`app/`, `static/`, `data/`, `backups/`, `docs/`)
- [x] Crear base SQLite y tablas; cargar artículos iniciales (sección 3)
- [x] API: artículos (listar, crear, editar, mín/crít, orden), movimientos, ajuste ±
- [x] Pantalla **Stock** funcional (filtros, búsqueda, ordenamiento, "Mi orden")

### Fase 2 — Despachos e ingresos ✅
- [x] API + pantalla **Despacho** (canal, revendedor→envío, cliente, productos, cajas, rollos)
- [x] API + pantalla **Ingreso** (proveedor opcional con autocompletado)
- [x] Selector de usuario (Nacho/Pablo/Mauricio) guardado en el navegador
- [x] **Componentes y recetas:** editor de receta por producto (componentes + cantidades) y caja de envío por defecto
- [x] **Armado:** pantalla/acción "Armé N estuches" → suma producto y descuenta componentes; avisa si no alcanzan
- [x] Sugerencia automática de cajas en el despacho (regla chica/mediana/grande configurable)

### Fase 3 — Panel ✅
- [x] KPIs, "Requiere atención"
- [x] "Pedidos por canal" con desplegables (productos, unidades, fecha)

### Fase 4 — Avisos ✅
- [x] Notificaciones en la app + campanita
- [x] Envío por Gmail (contraseña de aplicación) + botón de prueba
- [x] Resumen semanal programado (día/hora editables)
- [x] Pantalla Avisos con configuración App y Gmail **separadas**

### Fase 5 — Uso diario real ✅
- [x] Acceso desde celular por WiFi (IP + código QR en Configuración)
- [x] `iniciar.bat`, inicio automático opcional, regla de firewall
- [x] Respaldo automático diario + restaurar
- [x] Pantalla Configuración con guía para crear claves (Gemini y Gmail)

### Fase 6 — Asistente (chat) ✅
- [x] Asistente local por reglas (portar `answer()` del mockup al backend)
- [x] Integración Gemini con contexto del stock actual; fallback automático al local sin internet
- [x] **Previsión:** API de simulación "¿me alcanza?" (faltantes, stock resultante, estado final, insumos estimados)
- [x] **Pedidos futuros:** registrar/editar/cancelar, stock comprometido y disponible, convertir en despacho
- [x] **Proyección por consumo:** consumo promedio, días de cobertura, fecha estimada de quiebre, sugerencia de reposición
- [x] El chat (Gemini y local) responde preguntas a futuro usando esas funciones
- [x] **Carga de armados por chat con confirmación:** al escribir «hice / armé N estuches...», el bot detalla qué sumará y qué piezas descontará, pide confirmación (`✅ Confirmar y cargar` o escribir «sí») y registra el armado

### Fase 7 — Carga de planilla por foto ✅
- [x] Subida desde celular (cámara) y desde notebook (archivo) + modo de prueba con ejemplos reales
- [x] Prompt + esquema JSON adaptado a las 3 planillas reales (`DIARIA 4 ok` para Local/Revendedor/extras, `Tienda Nube 1` y `Mercado Libre`) según `planillas en blanco NUEVA.xlsx`
- [x] Coincidencia de nombres y códigos con el catálogo (`A Neg/cam Azul`, `B`, `B Prem`, `Fernetero Simple/Doble`, `Familiar Doble/P4`, `C`, `M`)
- [x] Tabla de revisión editable con confianza y **control anti-duplicados** (`planilla_hojas` y `planilla_filas`: 🆕 Nueva, ✔️ Ya cargada, ✏️ Modificada, ❓ Posible duplicado); confirmar → despachos + cajas sugeridas
- [x] Generar **planilla imprimible de Mercado Libre** (`/api/planillas/imprimible-ml`) con las columnas exactas (`N° · Fecha · # de Pedido · Nombre · Producto · Correa · Cantidad · Factura · ✓ Sist.`) y descarga del Excel original (`/api/planillas/excel`)

#### Lógica anti-duplicados de la planilla por foto (acordada 2026-11-11)
Problema: la misma hoja se fotografía varias veces a medida que se agregan pedidos; no debe cargarse dos veces lo mismo.
1. **Identificar la hoja:** la planilla tiene encabezado con **fecha y/o N° de hoja**. La IA lo lee; la app busca si esa hoja ya fue procesada.
2. **Identificar cada fila:** filas **numeradas** (1, 2, 3…) y, si existe, el **N° de pedido** (ML/TN). Se guarda una "huella" por fila: hoja + n° fila + canal + cliente + producto + cantidad.
3. **Comparar contra lo ya cargado** y clasificar cada fila en la tabla de revisión:
   - 🆕 **Nueva** → tildada para cargar.
   - ✔️ **Ya cargada** (misma huella) → gris, destildada, no se descuenta.
   - ✏️ **Modificada** (misma fila, contenido distinto, ej. cambió la cantidad) → resaltada; el usuario decide si aplicar solo la **diferencia** como ajuste.
   - ❓ **Posible duplicado** (sin número de fila/pedido pero muy parecida a una ya cargada) → destildada con advertencia.
4. **Refuerzo opcional:** columna "✓ Sistema" en la planilla; tras confirmar, se marca con una tilde a mano y la IA ignora filas tildadas.
5. **Nunca** se descuenta nada sin que el usuario confirme. Tablas extra: `planilla_hojas` (id, fecha_hoja, nro_hoja) y `planilla_filas` (hoja_id, nro_fila, huella, despacho_id).
Con planillas virtuales (Fase 9) el problema desaparece.

### Fase 8 — Pulido y entrega ✅
- [ ] Pruebas con uso real durante unos días y ajustes
- [x] Manual de uso corto en español (`docs/MANUAL.md`)

### Fase 9 — Futuro (no empezar sin pedido del usuario)
- [ ] Planillas virtuales / lectura de Google Sheets
- [ ] Integración con APIs de Mercado Libre y Tienda Nube (traer pedidos automáticamente)
- [ ] Reportes de consumo de insumos por despacho / costo de embalaje

## 6. Pendientes de información del usuario
- [x] Fotos de planillas reales o el archivo Excel que imprimen (`planillas en blanco NUEVA.xlsx`: pestañas `DIARIA 4 ok` y `Tienda Nube 1`, más columnas de `Mercado Libre`)
- [ ] Stock real inicial de cada artículo y mínimos/críticos deseados (se puede cargar desde la app)
- [x] **Lista de componentes y receta de cada estuche** (27 componentes y 9 recetas cargadas según Tienda Nube y definiciones del usuario)
- [ ] Proveedores reales (opcional)
- [ ] Crear clave Gemini (aistudio.google.com) y contraseña de aplicación Gmail (myaccount.google.com/apppasswords) — se cargan en la app, NO en este archivo

## 7. Estado actual
**Fases 1 a 8 completadas y verificadas. El sistema completo (incluyendo carga de armados por chat con confirmación y lector de planillas por foto con anti-duplicados) está corriendo en `http://localhost:8000`.**

## 8. Registro de avances
| Fecha | Quién | Qué se hizo |
|---|---|---|
| 2026-11-10 | IA (Antigravity) | Relevamiento, mockups v0.1 y v0.2, decisiones técnicas, creación de este documento |
| 2026-11-11 | IA (Antigravity) | Definida la lógica anti-duplicados para fotos repetidas de la misma planilla (ver Fase 7) |
| 2026-11-11 | IA (Antigravity) | Agregado requisito de **previsión y pedidos futuros** (sección 3 y Fase 6). Verificado: Python 3.14.5 y git instalados |
| 2026-11-11 | IA (Antigravity) | Usuarios definidos (Nacho, Pablo, Mauricio); agregado soporte para **componentes, recetas y armado de estuches** y **caja de envío por defecto** |
| 2026-11-11 | IA (Antigravity) | **Fase 1 completada:** entorno `.venv`, SQLite (`app/db.py`), API FastAPI (`app/main.py`), pantalla **Stock** (`static/`) con filtros, búsqueda, "Mi orden", edición y alta de artículos, `iniciar.bat` |
| 2026-11-11 | IA (Antigravity) | **Fases 2 y 3 completadas:** API y pantallas de **Despacho** (con sugerencia automática de cajas y regla configurable), **Ingreso** (con autocompletado de proveedores), **Armado** y editor de **Recetas**, y **Panel** (KPIs, "Requiere atención" y "Pedidos por canal" desplegables) |
| 2026-11-11 | IA (Antigravity) | **Fases 4, 5 y 6 completadas:** **Avisos** (centro de avisos + configuración separada App y Gmail + resumen semanal), **Configuración** (IP/QR para celular, claves Gemini/Gmail con prueba, respaldos diarios/manuales y restauración) y **Asistente y Previsión** (`app/servicios.py`: chat híbrido Gemini/local, simulador "¿Me alcanza?", pedidos futuros con stock comprometido y proyección de consumo) |
| 2026-11-11 | IA (Antigravity) | Regla establecida de cajas por cantidad en **Despacho** y **Previsión**: 1–2 u → Caja chica, 3–9 u → Caja mediana, 10+ u → Caja grande, con umbrales y capacidades por caja editables y guardados en SQLite |
| 2026-11-11 | IA (Antigravity) | Cargados en `app/db.py` y `data/stockdepo.db` los **27 componentes** (estuches vacíos A/B/C/Fe/Fa, mochila vacía, correas, copas, vasos, cubiertos, tablas de pino/algarrobo/eucalipto, accesorios) y las **recetas completas de los 9 estuches/mochila** |
| 2026-11-11 | IA (Antigravity) | **Fase 7, mejora de Chat y Manual completados:** carga de armados desde el chat con confirmación («hice/armé 10 estuches ferneteros»), lector de planillas por foto para `DIARIA 4 ok`, `Tienda Nube 1` y `Mercado Libre` con control anti-duplicados, hoja imprimible de Mercado Libre y manual `docs/MANUAL.md` |
| 2026-11-11 | IA (Antigravity) | Preparado paquete liviano `StockDepo_Para_Notebook.zip` (143 KB, con los 43 artículos, 9 recetas y regla de cajas en `data/stockdepo.db`), `configurar_notebook.bat` (acceso directo en Escritorio + regla de Firewall puerto 8000) e `iniciar.bat` con autoinstalación en equipo nuevo |
| 2026-11-11 | IA (Antigravity) | Corregido bug visual en `dlgReceta` (`static/app.js`) donde el botón `✕` escapaba código JS por comillas anidadas, y renombrado «Receta» a **«🧩 Piezas»** / **«🧩 Piezas que incluye»** para mayor claridad |
| 2026-11-11 | IA (Antigravity) | Mejorado diseño *responsive* en `static/estilos.css` y `static/app.js` con puntos de corte graduales (`1220px`, `1024px`, `780px`, `540px`), `flex-wrap` y `min-width: 0` en selectores, filas y tablas; verificado sin desbordes ni superposiciones en notebook (`1366×768`), pantalla dividida (`900×768`) y celular (`375×812`) |
| 2026-11-11 | IA (Antigravity) | Creada e integrada **animación de inicio estilo Neón LED (3.5 s)** con el logo oficial de **Enfocados Mendoza** (se enciende de abajo hacia arriba con haz láser, barra `CARGANDO...` y destello final neón): generado `static/logo_cargando.gif`, capas `static/logo_off.webp` y `static/logo_on.webp`, e integrado el splash screen en `static/index.html`, `static/estilos.css` y `static/app.js` |
| 2026-11-12 | IA (Antigravity) | **Solucionado error de inicio de servidor:** eliminada condición de carrera en `iniciar.bat` (el navegador se abría antes de que FastAPI se enlazara al puerto 8000), agregado reintento automático con backoff y pantalla de recuperación en `static/app.js`, apertura de navegador sincronizada en `app/__main__.py`, y control de instancias duplicadas/puerto ocupado en `app/verificar_puerto.py` e `iniciar.bat` |
| 2026-11-18 | IA (Antigravity) | Creado `README.md` con presentación completa del sistema, ajustado `.gitignore` (excluyendo `.zip` y datos sensibles) y publicado el repositorio público en GitHub (`https://github.com/IgnacioHM112/stockdepo`) |
