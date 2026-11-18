# Manual de Uso Rápido — StockDepo (Enfocados Mendoza)

Sistema local y gratuito de control de stock, armado, despacho, previsión y lectura de planillas por foto para **Nacho, Pablo y Mauricio**.

---

## 1. Cómo encender y abrir el sistema

1. En la notebook principal, hacé doble clic en **[`iniciar.bat`](../iniciar.bat)**.
2. Se abrirá automáticamente el navegador en **`http://localhost:8000`**.
3. **Para entrar desde el celular (o desde otra compu de la casa/depósito):**
   - Asegurate de estar conectado al **mismo Wi-Fi**.
   - En la notebook, andá a **⚙️ Configuración** y escaneá el **código QR** con la cámara del teléfono (o escribí la dirección `http://192.168.x.x:8000` que figura ahí).
4. Arriba a la derecha elegí tu nombre (**Nacho**, **Pablo** o **Mauricio**) para que todos los movimientos queden registrados a tu nombre.

---

## 2. Cómo se organizan los artículos (`📋 Stock`)

El stock se divide en 3 categorías:
- **🏷️ Productos (venta):** Los estuches listos para vender (`Estuche para copas`, `Estuche Asador`, `Estuche Asador con Cubiertos Premium`, `Estuche Coctelero`, `Mochila Campestre Térmica`, `Estuche Fernetero`, `Estuche Fernetero Doble`, `Estuche Familiar (2 Personas)`, `Estuche Familiar (4 Personas)` y `Tabla de Algarrobo Artesanal con Manijas`).
- **🧩 Componentes (armado):** Las piezas que compran por separado para armar los estuches (`Estuche vacío A/B/C/Fe/Fa`, `Mochila vacía`, `Correa para estuche`, copas, vasos, cubiertos, fundas, tablas de pino/algarrobo/eucalipto, etc.).
- **🧰 Insumos (embalaje):** `Caja chica`, `Caja mediana`, `Caja grande`, `Cinta de embalaje`, `Film negro de embalaje` y `Rollo de burbujas`.

---

## 3. Operaciones de todos los días

### 📥 Ingreso (cuando compran o entra mercadería)
- Andá a **📥 Ingreso**, elegí el artículo (componente, insumo o producto), poné la cantidad que entró y opcionalmente el proveedor y precio.
- Tocá **«📥 Sumar al stock»**.

### 🛠️ Armado de estuches (de dos formas)
1. **Desde la pestaña `🛠️ Armado`:**
   - Elegí qué estuche armaste y cuántos hiciste.
   - El sistema te muestra qué piezas va a descontar automáticamente según su receta y suma los estuches terminados.
2. **Desde el chat (`💬 Asistente y Previsión`) en la notebook o el teléfono:**
   - Escribí por ejemplo: **«hice 10 estuches ferneteros»** o **«armé 5 estuche asador y 3 cocteleros»**.
   - El bot te muestra el detalle exacto de lo que va a sumar y qué piezas va a descontar, y te pide confirmación.
   - Tocá **«✅ Confirmar y cargar»** (o respondé **«sí»**) y se carga automáticamente.

### 🚚 Despacho manual (cuando sale un pedido)
- Elegí el canal (**Local**, **Revendedor**, **Mercado Libre** o **Tienda Nube**). Si es **Revendedor**, elegí el medio de envío (*Terminal de ómnibus*, *Andreani* o *Retira en local*).
- Agregá los productos vendidos.
- El sistema calcula solo las **cajas de envío** según la regla establecida (configurable con el botón **«⚙️ Configurar cantidades por caja»**):
  - **1 a 2 unidades** → `Caja chica`
  - **3 a 9 unidades** → `Caja mediana`
  - **10 o más unidades** → `Caja grande`

### 📸 Cargar planilla de papel por foto (con control anti-duplicados)
1. En **📸 Planilla**, elegí cuál de las 3 planillas vas a cargar:
   - **📋 DIARIA 4 ok** (*Local, Revendedores o extras*)
   - **🛍️ Tienda Nube 1**
   - **🟡 Mercado Libre** (si necesitás hojas nuevas para imprimir, tocá **«🖨️ Imprimir hoja Mercado Libre»**).
2. Sacale una foto con el celular o subí la imagen y tocá **«🔍 Analizar foto con IA»**.
3. Revisá la tabla antes de confirmar:
   - **🆕 Nueva:** viene tildada, lista para descontar.
   - **✔️ Ya cargada:** viene **destildada automáticamente** para que nunca se descuente dos veces aunque saques foto a la misma hoja varios días seguidos.
   - **✏️ Modificada / ❓ Posible duplicado:** resaltada para que la revises.
4. Tocá **«✅ Confirmar filas tildadas y descontar stock»**.

---

## 4. Previsión a futuro (`💬 Asistente y Previsión`)

- **🔮 Simulador «¿Me alcanza?»:** Cargá un posible pedido grande para ver al instante si te alcanza con el stock armado, cuánto stock te quedaría, cuántos más podés armar con tus piezas actuales, qué piezas te faltarían comprar y cuántas cajas lleva.
- **📌 Pedidos futuros / Reservas:** Agendá pedidos confirmados para más adelante; el sistema reserva ese stock (*comprometido*) para no contarlo dos veces.
- **📈 Proyección:** Muestra el ritmo de salida diario y para cuántos días alcanza cada artículo.

---

## 5. Configuración de claves gratuitas y respaldos (`⚙️ Configuración`)

- **Clave de Gemini (gratis):** Necesaria para leer fotos reales de planillas y redacción avanzada del chat. Se obtiene sin tarjeta en [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
- **Contraseña de aplicación de Gmail (gratis):** Para recibir alertas de stock crítico y el resumen semanal por correo.
- **Respaldos automáticos:** El sistema guarda una copia automática por día en la carpeta `backups/`. También podés descargar una copia manual cuando quieras.
