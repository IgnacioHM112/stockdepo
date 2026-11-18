/* StockDepo — frontend (JavaScript sin dependencias) */
'use strict';

const VISTAS = [
  ['panel', '🏠', 'Panel', 3],
  ['stock', '📋', 'Stock', 1],
  ['despacho', '🚚', 'Despacho', 2],
  ['armado', '🛠️', 'Armado', 2],
  ['ingreso', '📥', 'Ingreso', 2],
  ['planilla', '📸', 'Planilla', 7],
  ['avisos', '🔔', 'Avisos', 4],
  ['chat', '💬', 'Asistente y Previsión', 6],
  ['config', '⚙️', 'Configuración', 5],
];
const TIPO_LABEL = { producto: '🏷️ Producto', componente: '🧩 Componente', insumo: '🧰 Insumo' };
const FILTROS = [['todos', 'Todos'], ['producto', 'Productos'], ['componente', 'Componentes'], ['insumo', 'Insumos']];
const ORDENES = [['custom', '↕️ Mi orden'], ['nombre', 'Nombre A-Z'], ['stock', 'Menor stock primero'],
  ['estado', 'Críticos primero'], ['tipo', 'Por tipo']];
const EST_LABEL = { ok: 'OK', low: 'Bajo', crit: 'Crítico' };
const CANAL_IC = { 'Local': '🏪', 'Revendedor': '🤝', 'Mercado Libre': '🟡', 'Tienda Nube': '🛍️' };
const ENVIO_IC = { 'Terminal de ómnibus': '🚌', 'Andreani': '📦', 'Retira en local': '🏪' };
const NOTIF_IC = { crit: '🛑', low: '⚠️', desp: '🚚', week: '📊', foto: '📸', photo: '📸' };

const S = {
  vista: localStorage.getItem('vista') || 'panel',
  usuario: localStorage.getItem('usuario') || '',
  usuarios: [],
  canales: ['Local', 'Revendedor', 'Mercado Libre', 'Tienda Nube'],
  envios: ['Terminal de ómnibus', 'Andreani', 'Retira en local'],
  reglaCajas: {
    chica_capacidad: 2,
    mediana_desde: 3,
    mediana_capacidad: 9,
    grande_desde: 10,
    grande_capacidad: 15,
    respetar_caja_minima: false,
  },
  items: [],
  filtro: 'todos', q: '', orden: localStorage.getItem('ordenStock') || 'custom', verInactivos: false,
  // Panel
  panel: { despachos_hoy: 0, despachos_semana: [] },
  canalesAbiertos: {},
  // Despacho
  dCanal: 'Local', dEnvio: 'Terminal de ómnibus', dCli: '',
  lineasDesp: [],
  cajasManuales: false,
  despachos: [],
  // Armado
  preArmado: null, armProdId: null, armCant: 1, armNota: '',
  armados: [],
  // Ingreso
  preIng: null,
  ingresos: [],
  // Planilla por foto (Fase 7)
  planillaTipo: 'diaria',
  planillaHojaId: '',
  planillaImgBase64: null,
  planillaFilas: [],
  planillaAnalizando: false,
  planillasInfo: { tipos: [], historial: [], tiene_excel: true },
  // Avisos (Fase 4)
  notifs: [],
  cfgAvisos: {
    app: { on: true, desp: true, photo: true, low: true, crit: true },
    mail: { on: false, from: '', desp: false, low: true, crit: true, week: true, day: 'Lunes', hour: '09:00', emails: [] },
  },
  // Asistente y Previsión (Fase 6)
  chat: [{
    from: 'bot',
    text: '¡Hola! Preguntame sobre el stock actual, simulá pedidos a futuro o cargá armados por chat.\nEjemplos:\n• "Armé 10 estuches ferneteros" (te pido confirmación y lo cargo)\n• "Si me piden 20 Estuche Asador y 10 Fernetero, ¿me alcanza y cuánto me queda?"\n• "¿Qué falta comprar o armar?"',
  }],
  accionChatPendiente: null,
  tabPrev: 'sim', // 'sim' | 'futuros' | 'proy'
  lineasSim: [],
  resultadoSim: null,
  pedidosFuturos: [],
  proyeccion: [],
  // Configuración (Fase 5)
  sistema: { ip_lan: '127.0.0.1', url_lan: 'http://localhost:8000', qr_svg: '', tiene_gemini_key: false, gemini_model: 'gemini-2.5-flash', tiene_gmail_pass: false, mail_from: '', respaldos: [] },
};

/* ---------- utilidades ---------- */
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const badge = e => `<span class="badge b-${e}">${EST_LABEL[e] || e}</span>`;
const porId = id => S.items.find(i => i.id === Number(id));

function fmtRel(iso) {
  const d = new Date(iso);
  const m = Math.round((Date.now() - d.getTime()) / 60000);
  if (m < 1) return 'recién';
  if (m < 60) return `hace ${m} min`;
  if (m < 1440) return `hace ${Math.round(m / 60)} h`;
  return `hace ${Math.round(m / 1440)} d`;
}

function fmtFechaHora(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit' }) + ' ' +
    d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
}

function toast(msg) {
  const t = $('toast'); t.innerHTML = msg; t.classList.remove('hidden');
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.add('hidden'), 3200);
}

async function api(metodo, url, cuerpo) {
  const r = await fetch(url, {
    method: metodo, headers: cuerpo ? { 'Content-Type': 'application/json' } : {},
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
  });
  if (!r.ok) {
    let msg = `Error ${r.status}`;
    try { const j = await r.json(); msg = typeof j.detail === 'string' ? j.detail : (j.detail?.[0]?.msg || msg); } catch { }
    throw new Error(msg);
  }
  return r.json();
}

/* ---------- navegación ---------- */
async function ir(v) {
  S.vista = v;
  localStorage.setItem('vista', v);
  await cargarDatosVista(v);
  render();
}

async function cargarDatosVista(v) {
  try {
    if (v === 'panel') {
      const [arts, pan] = await Promise.all([
        api('GET', '/api/articulos?incluir_inactivos=true'),
        api('GET', '/api/panel'),
      ]);
      S.items = arts; S.panel = pan;
    } else if (v === 'stock') {
      await cargarArticulos();
    } else if (v === 'despacho') {
      const [arts, desps] = await Promise.all([
        api('GET', '/api/articulos?incluir_inactivos=true'),
        api('GET', '/api/despachos?limite=15'),
      ]);
      S.items = arts; S.despachos = desps;
    } else if (v === 'armado') {
      const [arts, arms] = await Promise.all([
        api('GET', '/api/articulos?incluir_inactivos=true'),
        api('GET', '/api/armados?limite=15'),
      ]);
      S.items = arts; S.armados = arms;
    } else if (v === 'ingreso') {
      const [arts, ings] = await Promise.all([
        api('GET', '/api/articulos?incluir_inactivos=true'),
        api('GET', '/api/ingresos?limite=15'),
      ]);
      S.items = arts; S.ingresos = ings;
    } else if (v === 'planilla') {
      const [arts, pl] = await Promise.all([
        api('GET', '/api/articulos?incluir_inactivos=true'),
        api('GET', '/api/planillas'),
      ]);
      S.items = arts; S.planillasInfo = pl;
    } else if (v === 'avisos') {
      const av = await api('GET', '/api/avisos');
      S.notifs = av.notificaciones;
      S.cfgAvisos = av.config;
    } else if (v === 'chat') {
      const [arts, pfs, proy] = await Promise.all([
        api('GET', '/api/articulos?incluir_inactivos=true'),
        api('GET', '/api/pedidos-futuros'),
        api('GET', '/api/prevision/proyeccion'),
      ]);
      S.items = arts; S.pedidosFuturos = pfs; S.proyeccion = proy;
    } else if (v === 'config') {
      S.sistema = await api('GET', '/api/sistema/info');
    }
  } catch (e) {
    toast('⚠️ ' + esc(e.message));
  }
}

function renderNav() {
  $('sideNav').innerHTML = VISTAS.map(([k, ic, l]) =>
    `<button class="nav-btn ${S.vista === k ? 'active' : ''}" onclick="ir('${k}')"><span>${ic}</span>${l}${k === 'planilla' ? '<span class="tag">IA</span>' : ''}</button>`).join('');
  $('bottomNav').innerHTML = VISTAS.filter(v => ['panel', 'stock', 'despacho', 'armado', 'planilla', 'chat'].includes(v[0])).map(([k, ic, l]) =>
    `<button class="${S.vista === k ? 'active' : ''}" onclick="ir('${k}')"><span class="ic">${ic}</span>${l.split(' ')[0]}</button>`).join('');
  $('titulo').textContent = (VISTAS.find(v => v[0] === S.vista) || VISTAS[0])[2];
}

function render() {
  renderNav();
  const vistas = {
    panel: vPanel,
    stock: vStock,
    despacho: vDespacho,
    armado: vArmado,
    ingreso: vIngreso,
    planilla: vPlanilla,
    avisos: vAvisos,
    chat: vChat,
    config: vConfig,
  };
  $('contenido').innerHTML = (vistas[S.vista] || vProximamente)();
  if (S.vista === 'stock') pintarFilas();
  if (S.vista === 'despacho' && !S.cajasManuales) aplicarCajasSugeridas();
  if (S.vista === 'chat') {
    const m = $('msgs'); if (m) m.scrollTop = m.scrollHeight;
  }
}

function vProximamente() {
  const v = VISTAS.find(x => x[0] === S.vista) || VISTAS[0];
  return `<div class="card empty"><div style="font-size:40px">${v[1]}</div>
    <div class="semi" style="margin-top:8px">${v[2]}: pendiente de fotos reales de planillas (Fase ${v[3]})</div>
    <p class="small muted">Cuando subas una foto de la planilla de papel, configuramos el lector con IA.</p>
    <button class="btn" onclick="ir('panel')">Ir al Panel</button></div>`;
}

/* ---------- usuario ---------- */
function renderUsuarios() {
  const sel = $('usuario');
  if (!S.usuarios.includes(S.usuario)) S.usuario = S.usuarios[0];
  sel.innerHTML = S.usuarios.map(u => `<option ${u === S.usuario ? 'selected' : ''}>${esc(u)}</option>`).join('');
  sel.onchange = () => { S.usuario = sel.value; localStorage.setItem('usuario', sel.value); toast(`Usando como <b>${esc(sel.value)}</b>`); };
}

/* ---------- PANEL (Fase 3) ---------- */
function vPanel() {
  const activos = S.items.filter(i => i.activo);
  const bajos = activos.filter(i => i.estado === 'low');
  const criticos = activos.filter(i => i.estado === 'crit');
  const atencion = activos
    .filter(i => i.estado !== 'ok')
    .sort((a, b) => (a.estado === 'crit' ? 0 : 1) - (b.estado === 'crit' ? 0 : 1) || a.orden - b.orden);

  const kpi = (l, v, ic, cls = '') => `<div class="card p-card"><div class="small muted">${ic} ${l}</div><div class="kpi-val ${cls}">${v}</div></div>`;
  const unidadesProd = d => (d.items || []).filter(it => it.tipo === 'producto').reduce((acc, it) => acc + it.cantidad, 0);

  return `
  <div class="kpi-grid">
    ${kpi('Artículos', activos.length, '📦')}
    ${kpi('Stock bajo', bajos.length, '⚠️', 'text-low')}
    ${kpi('Críticos', criticos.length, '🛑', 'text-crit')}
    ${kpi('Despachos hoy', S.panel.despachos_hoy, '🚚')}
  </div>
  <div class="panel-grid">
    <div class="card p-card">
      <div class="row between" style="margin-bottom:12px">
        <h2 class="semi" style="margin:0;font-size:16px">Requiere atención</h2>
        <button class="small link" onclick="ir('stock')">Ver stock →</button>
      </div>
      ${atencion.length ? atencion.map(i => `
        <div class="list-row">
          <div class="grow">
            <div class="semi">${esc(i.nombre)}</div>
            <div class="xs muted">${TIPO_LABEL[i.tipo]} · quedan <b>${i.stock} ${esc(i.unidad)}</b> (mín. ${i.minimo})${i.proveedor ? ' · ' + esc(i.proveedor) : ''}${i.tipo === 'producto' && i.armables !== null ? ` · armables: <b>${i.armables}</b>` : ''}</div>
          </div>
          <div class="row nowrap">
            ${badge(i.estado)}
            ${i.tipo === 'producto' ? `<button class="btn2 sm" onclick="S.preArmado=${i.id};ir('armado')" title="Armar estuches">🛠️ Armar</button>` : ''}
            <button class="btn2 sm" onclick="S.preIng=${i.id};ir('ingreso')">+ Ingreso</button>
          </div>
        </div>`).join('') : '<p class="muted small" style="margin:0">Todo en orden 🎉</p>'}
    </div>
    <div class="card p-card">
      <h2 class="semi" style="margin:0 0 4px;font-size:16px">Pedidos por canal</h2>
      <p class="xs muted" style="margin:0 0 12px">Últimos 7 días · tocá un canal para ver sus pedidos</p>
      ${S.canales.map(c => {
        const ds = (S.panel.despachos_semana || []).filter(d => d.canal === c);
        const abierto = !!S.canalesAbiertos[c];
        const totalU = ds.reduce((acc, d) => acc + unidadesProd(d), 0);
        return `<div class="canal-box">
          <button class="canal-head" onclick="S.canalesAbiertos['${c}']=!S.canalesAbiertos['${c}'];render()">
            <span class="row semi"><span>${CANAL_IC[c] || '📦'}</span> Pedidos de ${esc(c)}</span>
            <span class="row small"><span class="muted">${totalU} u</span><span class="btn2 sm">${ds.length}</span><span class="muted">${abierto ? '▲' : '▼'}</span></span>
          </button>
          ${abierto ? `<div class="canal-body">
            ${ds.length ? `<table class="tabla small">
              <thead><tr><th>Pedido</th><th>Productos</th><th class="right-al">Fecha</th></tr></thead>
              <tbody>
                ${ds.map(d => {
                  const prods = (d.items || []).filter(it => it.tipo === 'producto');
                  return `<tr>
                    <td class="nowrap" style="vertical-align:top">
                      <b>#${d.id}</b>
                      ${d.cliente ? `<div class="xs muted">${esc(d.cliente)}</div>` : ''}
                      ${d.envio ? `<div style="margin-top:2px"><span class="badge b-ok">${esc(d.envio)}</span></div>` : ''}
                    </td>
                    <td style="vertical-align:top">
                      ${prods.length ? prods.map(it => `<div><b>${it.cantidad}×</b> ${esc(it.nombre)}</div>`).join('') : '<span class="muted">solo insumos</span>'}
                    </td>
                    <td class="right-al muted nowrap" style="vertical-align:top">${fmtFechaHora(d.fecha)}</td>
                  </tr>`;
                }).join('')}
              </tbody>
            </table>` : '<p class="small muted" style="margin:8px 0 0">Sin pedidos esta semana.</p>'}
          </div>` : ''}
        </div>`;
      }).join('')}
    </div>
  </div>`;
}

/* ---------- STOCK (Fase 1 + Recetas Fase 2) ---------- */
async function cargarArticulos() {
  S.items = await api('GET', '/api/articulos?incluir_inactivos=true');
}

function itemsVisibles() {
  const q = S.q.trim().toLowerCase();
  const rangoEst = { crit: 0, low: 1, ok: 2 };
  const cmp = {
    custom: (a, b) => a.orden - b.orden || a.id - b.id,
    nombre: (a, b) => a.nombre.localeCompare(b.nombre, 'es'),
    stock: (a, b) => a.stock - b.stock,
    estado: (a, b) => rangoEst[a.estado] - rangoEst[b.estado] || a.orden - b.orden,
    tipo: (a, b) => a.tipo.localeCompare(b.tipo) || a.orden - b.orden,
  }[S.orden];
  return S.items
    .filter(i => (S.verInactivos || i.activo) && (S.filtro === 'todos' || i.tipo === S.filtro) && i.nombre.toLowerCase().includes(q))
    .sort(cmp);
}

function vStock() {
  const cuenta = t => S.items.filter(i => i.activo && (t === 'todos' || i.tipo === t)).length;
  return `
  <div class="toolbar">
    ${FILTROS.map(([k, l]) => `<button class="chip ${S.filtro === k ? 'on' : ''}" onclick="S.filtro='${k}';render()">${l} <span class="${S.filtro === k ? '' : 'muted'}">${cuenta(k)}</span></button>`).join('')}
    <div class="right">
      <select class="inp auto small" onchange="S.orden=this.value;localStorage.setItem('ordenStock',this.value);render()">
        ${ORDENES.map(([k, l]) => `<option value="${k}" ${S.orden === k ? 'selected' : ''}>${l}</option>`).join('')}
      </select>
      <input class="inp search" placeholder="🔍 Buscar..." value="${esc(S.q)}" oninput="S.q=this.value;pintarFilas()">
      <button class="btn" onclick="dlgNuevo()">+ Nuevo artículo</button>
    </div>
  </div>
  ${S.orden === 'custom' ? '<p class="xs muted">Modo "Mi orden": usá las flechas ▲▼ para acomodar los artículos como quieras. El orden queda guardado.</p>' : ''}
  <div class="card stock-table" style="overflow-x:auto">
    <table class="tabla">
      <thead><tr>${S.orden === 'custom' ? '<th style="width:70px">Orden</th>' : ''}<th>Artículo</th><th>Stock</th><th>Nivel</th><th>Estado</th><th>Mín / Crít</th><th>Proveedor</th><th class="right-al">Ajuste</th></tr></thead>
      <tbody id="tb"></tbody>
    </table>
  </div>
  <div class="card stock-cards" id="cards"></div>
  <div class="row between" style="margin-top:12px;flex-wrap:wrap">
    <p class="xs muted" style="margin:0">💡 Tocá el nombre de un artículo para editarlo, o "🧩 Piezas" en un estuche para ver o cambiar qué cosas incluye adentro.</p>
    <label class="xs muted row"><input type="checkbox" ${S.verInactivos ? 'checked' : ''} onchange="S.verInactivos=this.checked;pintarFilas()"> Mostrar desactivados</label>
  </div>`;
}

function infoRecetaHtml(i) {
  let extra = '';
  if (i.comprometido > 0) {
    extra += ` · <span class="xs text-low" title="Reservado en pedidos futuros">📌 ${i.comprometido} reserv. (disp: ${i.disponible})</span>`;
  }
  if (i.tipo !== 'producto') return extra;
  const n = (i.receta || []).length;
  const caja = i.caja_id ? porId(i.caja_id) : null;
  return extra + ` · <button class="dotted link xs" title="Ver o editar qué cosas incluye este estuche" onclick="dlgReceta(${i.id})">🧩 ${n ? `Piezas (${n})` : 'Qué piezas lleva'}</button>` +
    (i.armables !== null ? ` <span class="xs muted">(armables: <b>${i.armables}</b>)</span>` : '') +
    (caja ? ` · <span class="xs muted">📦 ${esc(caja.nombre.replace('Caja ', ''))}</span>` : '');
}

function pintarFilas() {
  const lista = itemsVisibles();
  const custom = S.orden === 'custom';
  const nivel = i => { const pct = i.minimo > 0 ? Math.min(100, i.stock / (i.minimo * 2) * 100) : (i.stock > 0 ? 100 : 0); return `<div class="bar"><div class="bar-${i.estado}" style="width:${pct}%"></div></div>`; };
  const flechas = i => `<button class="btn2 sm" onclick="mover(${i.id},-1)" title="Subir">▲</button> <button class="btn2 sm" onclick="mover(${i.id},1)" title="Bajar">▼</button>`;
  const ajuste = i => `<button class="btn2" onclick="ajustar(${i.id},-1)" title="Restar 1">−</button> <button class="btn2" onclick="ajustar(${i.id},1)" title="Sumar 1">+</button>`;
  const nombre = i => `<button class="semi" style="text-align:left" onclick="dlgEditar(${i.id})">${esc(i.nombre)}</button>${i.activo ? '' : ' <span class="xs muted">(desactivado)</span>'}`;

  const tb = $('tb'), cards = $('cards');
  if (!tb) return;
  if (!lista.length) {
    const vacio = `<div class="empty muted">No hay artículos${S.q ? ' que coincidan con la búsqueda' : ' en esta categoría'}.</div>`;
    tb.innerHTML = `<tr><td colspan="8">${vacio}</td></tr>`; cards.innerHTML = vacio; return;
  }
  tb.innerHTML = lista.map(i => `<tr class="${i.activo ? '' : 'inactivo'}">
    ${custom ? `<td class="nowrap">${flechas(i)}</td>` : ''}
    <td>${nombre(i)}<div class="xs muted">${TIPO_LABEL[i.tipo]}${infoRecetaHtml(i)}</div></td>
    <td class="num">${i.stock} <span class="muted" style="font-weight:400">${esc(i.unidad)}</span></td>
    <td>${nivel(i)}</td>
    <td>${badge(i.estado)}</td>
    <td><button class="dotted" onclick="dlgLimites(${i.id})">${i.minimo} / ${i.critico}</button></td>
    <td class="muted">${i.proveedor ? esc(i.proveedor) : '<span style="opacity:.5">—</span>'}</td>
    <td class="right-al nowrap">${ajuste(i)}</td></tr>`).join('');
  cards.innerHTML = lista.map(i => `<div class="stock-card ${i.activo ? '' : 'inactivo'}">
    <div class="row between" style="align-items:flex-start;gap:8px"><div class="grow">${nombre(i)}<div class="xs muted" style="margin-top:2px;line-height:1.5">${TIPO_LABEL[i.tipo]} · <button class="dotted" onclick="dlgLimites(${i.id})">mín ${i.minimo} / crít ${i.critico}</button>${infoRecetaHtml(i)}</div></div>${badge(i.estado)}</div>
    <div class="row between" style="margin-top:8px">
      <div class="row">${custom ? flechas(i) : ''}<span class="num" style="margin-left:4px">${i.stock} <span class="muted small" style="font-weight:400">${esc(i.unidad)}</span></span></div>
      <div class="nowrap">${ajuste(i)}</div></div></div>`).join('');
}

async function ajustar(id, delta) {
  try {
    await api('POST', `/api/articulos/${id}/ajuste`, { delta, usuario: S.usuario, motivo: 'Ajuste manual' });
    await cargarArticulos();
    const a = porId(id);
    pintarFilas(); actualizarCampanita();
    toast(`${esc(a.nombre)}: ${delta > 0 ? '+' : ''}${delta} → <b>${a.stock}</b>`);
  } catch (e) { toast('⚠️ ' + esc(e.message)); }
}

let _ordenTimer;
function mover(id, dir) {
  const visibles = itemsVisibles();
  const k = visibles.findIndex(i => i.id === id), j = k + dir;
  if (j < 0 || j >= visibles.length) return;
  const a = visibles[k], b = visibles[j];
  [a.orden, b.orden] = [b.orden, a.orden];
  if (a.orden === b.orden) a.orden += dir;
  pintarFilas();
  clearTimeout(_ordenTimer);
  _ordenTimer = setTimeout(async () => {
    const ids = S.items.slice().sort((x, y) => x.orden - y.orden || x.id - y.id).map(i => i.id);
    ids.forEach((aid, n) => porId(aid).orden = n);
    try { await api('PUT', '/api/articulos/orden', { ids }); } catch { toast('⚠️ No se pudo guardar el orden'); }
  }, 600);
}

/* ---------- DESPACHO (Fase 2) ---------- */
const cajasActivas = () => S.items.filter(i => i.activo && i.tipo === 'insumo' && /^caja/i.test(i.nombre));
const rollosActivos = () => S.items.filter(i => i.activo && i.tipo === 'insumo' && i.unidad === 'rollos');
const prodsActivos = () => S.items.filter(i => i.activo && i.tipo === 'producto');

function calcularCajasSugeridas() {
  const sugeridas = {};
  cajasActivas().forEach(c => { sugeridas[c.id] = 0; });
  const totalUnidades = S.lineasDesp.reduce((acc, l) => acc + l.cantidad, 0);
  if (!totalUnidades) return sugeridas;

  const cajaChica = cajasActivas().find(c => /chica/i.test(c.nombre));
  const cajaMediana = cajasActivas().find(c => /mediana/i.test(c.nombre));
  const cajaGrande = cajasActivas().find(c => /grande/i.test(c.nombre));
  const rc = S.reglaCajas;
  const medDesde = rc.mediana_desde || 3;
  const graDesde = rc.grande_desde || rc.caja_grande_desde_unidades || 10;

  if (cajaGrande && totalUnidades >= graDesde) {
    sugeridas[cajaGrande.id] = Math.ceil(totalUnidades / Math.max(1, rc.grande_capacidad || rc.unidades_por_caja_grande || 15));
  } else if (cajaMediana && totalUnidades >= medDesde) {
    sugeridas[cajaMediana.id] = Math.ceil(totalUnidades / Math.max(1, rc.mediana_capacidad || 9));
  } else if (rc.respetar_caja_minima) {
    S.lineasDesp.forEach(l => {
      const p = porId(l.articulo_id);
      const cid = p?.caja_id || cajaChica?.id;
      if (cid && sugeridas[cid] !== undefined) sugeridas[cid] += l.cantidad;
    });
  } else if (cajaChica) {
    sugeridas[cajaChica.id] = Math.ceil(totalUnidades / Math.max(1, rc.chica_capacidad || 2));
  }
  return sugeridas;
}

function resumenReglaCajasTexto() {
  const rc = S.reglaCajas;
  const medDesde = rc.mediana_desde || 3;
  const graDesde = rc.grande_desde || 10;
  const rangoChica = medDesde <= 2 ? '1 u' : `1 a ${medDesde - 1} u`;
  const rangoMed = `${medDesde} a ${graDesde - 1} u`;
  return `${rangoChica} → <b>Chica</b> (entran ${rc.chica_capacidad || 2}) · ${rangoMed} → <b>Mediana</b> (entran ${rc.mediana_capacidad || 9}) · ${graDesde}+ u → <b>Grande</b> (entran ${rc.grande_capacidad || 15})`;
}

function aplicarCajasSugeridas() {
  const sug = calcularCajasSugeridas();
  document.querySelectorAll('[data-caja]').forEach(inp => {
    inp.value = sug[Number(inp.dataset.caja)] || 0;
  });
}

function vDespacho() {
  const prods = prodsActivos();
  const cajas = cajasActivas();
  const rollos = rollosActivos();
  const proxNum = (S.despachos[0]?.id || 0) + 1;
  const placeholderCli = S.dCanal === 'Revendedor' ? 'Ej: Carlos (San Rafael)' : S.dCanal === 'Mercado Libre' ? 'Ej: #ML-2231' : 'Ej: Juan Pérez';

  return `
  <div class="split-grid">
    <div class="card p-card stack">
      <div>
        <h2 class="semi" style="margin:0;font-size:18px">Nuevo despacho #${proxNum}</h2>
        <p class="small muted" style="margin:4px 0 0">Reemplaza la planilla de papel. Descuenta productos e insumos automáticamente.</p>
      </div>
      <div>
        <div class="small semi" style="margin-bottom:8px">Canal de venta</div>
        <div class="chips-wrap">
          ${S.canales.map(c => `<button class="chip ${S.dCanal === c ? 'on' : ''}" onclick="S.dCanal='${c}';render()">${CANAL_IC[c] || ''} ${esc(c)}</button>`).join('')}
        </div>
      </div>
      ${S.dCanal === 'Revendedor' ? `<div class="subbox">
        <div class="small semi" style="margin-bottom:8px">¿Cómo sale el pedido del revendedor?</div>
        <div class="chips-wrap">
          ${S.envios.map(e => `<label class="chip ${S.dEnvio === e ? 'on' : ''}" style="cursor:pointer" onclick="S.dEnvio='${e}';render()">
            <input type="radio" name="envio" value="${esc(e)}" ${S.dEnvio === e ? 'checked' : ''} class="hidden">${ENVIO_IC[e] || '🚚'} ${esc(e)}</label>`).join('')}
        </div>
      </div>` : ''}
      <label class="small">Cliente / referencia <span class="muted">(opcional)</span>
        <input id="dCli" class="inp" style="margin-top:4px" value="${esc(S.dCli)}" oninput="S.dCli=this.value" placeholder="${placeholderCli}">
      </label>
      <div>
        <div class="small semi" style="margin-bottom:8px">🏷️ Productos</div>
        <div class="row" style="flex-wrap:wrap">
          <select id="dProd" class="inp">${prods.map(p => `<option value="${p.id}">${esc(p.nombre)} (${p.stock} disp.)</option>`).join('')}</select>
          <input id="dQty" type="number" min="1" value="1" class="inp" style="width:84px">
          <button class="btn" onclick="agregarLineaDesp()">Agregar</button>
        </div>
        <div id="lineasDesp" class="stack" style="margin-top:10px;gap:8px">${lineasDespHtml()}</div>
      </div>
      <div>
        <div class="row between" style="margin-bottom:6px;flex-wrap:wrap">
          <span class="small semi">📦 Cajas usadas</span>
          <button class="xs link dotted" onclick="dlgReglaCajas()">⚙️ Configurar cantidades por caja</button>
        </div>
        <div class="xs muted subbox" style="padding:8px 10px;margin-bottom:8px">
          📏 Regla establecida: ${resumenReglaCajasTexto()}
        </div>
        <div class="grid3">
          ${cajas.map(c => `<label class="small">${esc(c.nombre.replace('Caja ', ''))} <span class="xs muted">(${c.stock})</span>
            <input type="number" min="0" value="0" data-caja="${c.id}" class="inp" style="margin-top:4px" oninput="S.cajasManuales=true"></label>`).join('')}
        </div>
        <div class="xs muted" style="margin-top:4px">✨ Se completan solas según la cantidad de unidades del pedido; podés ajustarlas a mano si hace falta.</div>
      </div>
      <div>
        <div class="small semi" style="margin-bottom:8px">🧻 ¿Se terminó algún rollo?</div>
        <div class="chips-wrap">
          ${rollos.map(r => `<label class="chip row" style="cursor:pointer"><input type="checkbox" data-rollo="${r.id}">${esc(r.nombre)} <span class="xs muted">(${r.stock})</span></label>`).join('')}
        </div>
      </div>
      <button class="btn" style="padding:12px" onclick="guardarDespacho()">✅ Registrar despacho</button>
    </div>
    <div class="card p-card">
      <h2 class="semi" style="margin:0 0 12px;font-size:16px">Despachos recientes</h2>
      ${S.despachos.length ? S.despachos.slice(0, 10).map(d => `
        <div class="list-row" style="align-items:flex-start">
          <div class="grow small">
            <div><b>#${d.id}</b> · ${CANAL_IC[d.canal] || ''} ${esc(d.canal)}${d.envio ? `<span class="muted"> · ${esc(d.envio)}</span>` : ''}${d.cliente ? ` · <b>${esc(d.cliente)}</b>` : ''}</div>
            <div class="xs muted" style="margin-top:2px">${(d.items || []).map(it => `${it.cantidad}× ${esc(it.nombre)}`).join(', ')}</div>
          </div>
          <span class="xs muted nowrap">${fmtRel(d.fecha)}</span>
        </div>`).join('') : '<p class="small muted" style="margin:0">Todavía no hay despachos registrados.</p>'}
    </div>
  </div>`;
}

function lineasDespHtml() {
  if (!S.lineasDesp.length) return '<p class="small muted" style="margin:0">Todavía no agregaste productos.</p>';
  return S.lineasDesp.map((l, k) => {
    const p = porId(l.articulo_id);
    const falta = p && l.cantidad > p.stock;
    return `<div class="line-pill">
      <span>${esc(p ? p.nombre : '')} × <b>${l.cantidad}</b> ${falta ? `<span class="badge b-crit">Stock actual: ${p.stock}</span>` : ''}</span>
      <button class="muted" onclick="quitarLineaDesp(${k})" title="Quitar">✕</button>
    </div>`;
  }).join('');
}

function agregarLineaDesp() {
  const aid = Number($('dProd').value);
  const q = Math.max(1, Number($('dQty').value) || 1);
  const ex = S.lineasDesp.find(l => l.articulo_id === aid);
  if (ex) ex.cantidad += q;
  else S.lineasDesp.push({ articulo_id: aid, cantidad: q });
  S.cajasManuales = false;
  $('lineasDesp').innerHTML = lineasDespHtml();
  aplicarCajasSugeridas();
}

function quitarLineaDesp(idx) {
  S.lineasDesp.splice(idx, 1);
  S.cajasManuales = false;
  $('lineasDesp').innerHTML = lineasDespHtml();
  aplicarCajasSugeridas();
}

async function guardarDespacho() {
  const items = S.lineasDesp.map(l => ({ ...l }));
  document.querySelectorAll('[data-caja]').forEach(e => {
    const q = Number(e.value) || 0;
    if (q > 0) items.push({ articulo_id: Number(e.dataset.caja), cantidad: q });
  });
  document.querySelectorAll('[data-rollo]:checked').forEach(e => {
    items.push({ articulo_id: Number(e.dataset.rollo), cantidad: 1 });
  });
  if (!items.length) return toast('⚠️ Agregá al menos un producto o insumo');

  try {
    const d = await api('POST', '/api/despachos', {
      usuario: S.usuario,
      canal: S.dCanal,
      envio: S.dCanal === 'Revendedor' ? S.dEnvio : '',
      cliente: S.dCli,
      origen: 'manual',
      items,
    });
    S.lineasDesp = []; S.dCli = ''; S.cajasManuales = false;
    await cargarDatosVista('despacho');
    render(); actualizarCampanita();
    toast(`✅ Despacho #${d.id} registrado y stock actualizado`);
  } catch (e) {
    toast('⚠️ ' + esc(e.message));
  }
}

function dlgReglaCajas() {
  const rc = S.reglaCajas;
  abrirDlg(`<h3>📦 Cantidades establecidas por caja</h3>
    <p class="xs muted" style="margin:0">Definí a partir de cuántas unidades del pedido se usa cada tamaño de caja y cuántas unidades entran por caja. Queda guardado para todos los despachos y simulaciones.</p>
    <div class="subbox stack" style="gap:10px">
      <div class="grid2">
        <div><div class="small semi">📦 Caja chica</div><div class="xs muted">Desde 1 unidad (pedidos individuales)</div></div>
        <label class="xs">Unidades máx. que entran por Caja chica
          <input class="inp small" name="chica_cap" type="number" min="1" max="50" value="${rc.chica_capacidad || 2}" required></label>
      </div>
      <div class="grid2" style="border-top:1px solid var(--border);padding-top:8px">
        <label class="xs">📦 Pasar a <b>Caja mediana</b> desde (unidades)
          <input class="inp small" name="med_desde" type="number" min="2" max="100" value="${rc.mediana_desde || 3}" required></label>
        <label class="xs">Unidades máx. que entran por Caja mediana
          <input class="inp small" name="med_cap" type="number" min="1" max="100" value="${rc.mediana_capacidad || 9}" required></label>
      </div>
      <div class="grid2" style="border-top:1px solid var(--border);padding-top:8px">
        <label class="xs">📦 Pasar a <b>Caja grande</b> desde (unidades)
          <input class="inp small" name="gra_desde" type="number" min="3" max="500" value="${rc.grande_desde || 10}" required></label>
        <label class="xs">Unidades máx. que entran por Caja grande
          <input class="inp small" name="gra_cap" type="number" min="1" max="500" value="${rc.grande_capacidad || 15}" required></label>
      </div>
    </div>
    <label class="row xs muted"><input type="checkbox" name="resp_min" ${rc.respetar_caja_minima ? 'checked' : ''}> Si es pedido individual pero el estuche tiene asignada Caja mediana en Stock, usar Mediana</label>`, async fd => {
    S.reglaCajas = await api('PUT', '/api/config/cajas', {
      chica_capacidad: numero(fd, 'chica_cap'),
      mediana_desde: numero(fd, 'med_desde'),
      mediana_capacidad: numero(fd, 'med_cap'),
      grande_desde: numero(fd, 'gra_desde'),
      grande_capacidad: numero(fd, 'gra_cap'),
      respetar_caja_minima: fd.get('resp_min') === 'on',
    });
    S.cajasManuales = false;
    render();
    toast('✅ Regla de cajas guardada');
  });
}

/* ---------- ARMADO DE ESTUCHES (Fase 2) ---------- */
function vArmado() {
  const prods = prodsActivos();
  if (S.preArmado) { S.armProdId = S.preArmado; S.preArmado = null; }
  if (!S.armProdId || !porId(S.armProdId)) S.armProdId = prods[0]?.id || null;
  const prod = porId(S.armProdId);
  const cant = Math.max(1, Number(S.armCant) || 1);

  return `
  <div class="split-grid">
    <div class="card p-card stack">
      <div>
        <h2 class="semi" style="margin:0;font-size:18px">Armado de estuches</h2>
        <p class="small muted" style="margin:4px 0 0">Cuando armás estuches en el depósito: suma el producto terminado y descuenta sus componentes según la receta.</p>
      </div>
      <div class="grid2">
        <label class="small">Producto a armar
          <select class="inp" style="margin-top:4px" onchange="S.armProdId=Number(this.value);render()">
            ${prods.map(p => `<option value="${p.id}" ${p.id === S.armProdId ? 'selected' : ''}>🏷️ ${esc(p.nombre)} (hay ${p.stock} u${p.armables !== null ? ` · armables: ${p.armables}` : ''})</option>`).join('')}
          </select>
        </label>
        <label class="small">Cantidad a armar
          <input class="inp" style="margin-top:4px" type="number" min="1" value="${cant}" oninput="S.armCant=Math.max(1,Number(this.value)||1);$('armRecetaBox').innerHTML=armadoRecetaBoxHtml()">
        </label>
      </div>
      <div id="armRecetaBox" class="subbox">${armadoRecetaBoxHtml()}</div>
      <label class="small">Nota <span class="muted">(opcional)</span>
        <input class="inp" style="margin-top:4px" value="${esc(S.armNota)}" oninput="S.armNota=this.value" placeholder="Ej: Lote para fin de semana">
      </label>
      <button class="btn" style="padding:12px" onclick="guardarArmado(false)">🛠️ Registrar armado (+${cant} ${esc(prod?.nombre || '')})</button>
    </div>
    <div class="card p-card">
      <h2 class="semi" style="margin:0 0 12px;font-size:16px">Armados recientes</h2>
      ${S.armados.length ? S.armados.map(ar => `
        <div class="list-row">
          <div class="grow small">
            <div><b>+${ar.cantidad}</b> ${esc(ar.producto_nombre)}</div>
            <div class="xs muted">${esc(ar.usuario)}${ar.nota ? ' · ' + esc(ar.nota) : ''}</div>
          </div>
          <span class="xs muted nowrap">${fmtRel(ar.fecha)}</span>
        </div>`).join('') : '<p class="small muted" style="margin:0">Todavía no registraste armados.</p>'}
    </div>
  </div>`;
}

function armadoRecetaBoxHtml() {
  const prod = porId(S.armProdId);
  if (!prod) return '';
  const rec = prod.receta || [];
  const cant = Math.max(1, Number(S.armCant) || 1);
  return `
    <div class="row between" style="margin-bottom:8px;flex-wrap:wrap">
      <span class="small semi">🧩 Piezas que incluye ${esc(prod.nombre)}</span>
      <div class="row">
        <button class="btn2 sm" onclick="dlgNuevo('componente')">+ Nueva pieza</button>
        <button class="btn2 sm" onclick="dlgReceta(${prod.id})">✏️ Editar piezas del estuche</button>
      </div>
    </div>
    ${rec.length ? `
      <div class="xs muted" style="margin-bottom:6px">Con el stock actual de piezas podés armar hasta <b>${prod.armables} u</b>. Para armar <b>${cant} u</b> se descontarán:</div>
      ${rec.map(c => {
        const req = c.cantidad * cant;
        const rest = c.stock - req;
        const ok = rest >= 0;
        return `<div class="list-row small">
          <span>${esc(c.nombre)} <span class="xs muted">(${c.cantidad} por estuche)</span></span>
          <span class="row nowrap">
            <span>necesitás <b>${req}</b> · hay ${c.stock} ${esc(c.unidad)}</span>
            ${ok ? `<span class="badge b-ok">quedan ${rest}</span>` : `<span class="badge b-crit">faltan ${-rest}</span>`}
          </span>
        </div>`;
      }).join('')}
    ` : `<p class="small muted" style="margin:0">Este producto se vende directo (sin armado) o todavía no le asignaste piezas. Podés tocar <b>"✏️ Editar piezas del estuche"</b> para indicar qué lleva adentro.</p>`}`;
}

async function guardarArmado(forzar) {
  const prod = porId(S.armProdId);
  if (!prod) return;
  const cant = Math.max(1, Number(S.armCant) || 1);
  const faltan = (prod.receta || []).filter(c => c.stock < c.cantidad * cant);
  if (faltan.length && !forzar) {
    const detalle = faltan.map(c => `${c.nombre} (necesitás ${c.cantidad * cant}, hay ${c.stock})`).join(', ');
    if (!confirm(`⚠️ No alcanzan algunos componentes:\n${detalle}\n\n¿Querés registrar el armado igual (esos componentes quedarán en 0)?`)) return;
    forzar = true;
  }
  try {
    await api('POST', '/api/armados', {
      usuario: S.usuario,
      producto_id: prod.id,
      cantidad: cant,
      nota: S.armNota,
      forzar,
    });
    S.armNota = ''; S.armCant = 1;
    await cargarDatosVista('armado');
    render(); actualizarCampanita();
    toast(`🛠️ Armado registrado: +${cant} ${esc(prod.nombre)}`);
  } catch (e) {
    toast('⚠️ ' + esc(e.message));
  }
}

/* ---------- INGRESO (Fase 2) ---------- */
function vIngreso() {
  const activos = S.items.filter(i => i.activo);
  const pre = S.preIng || activos[0]?.id;
  S.preIng = null;
  const selItem = porId(pre) || activos[0];

  return `
  <div class="split-grid">
    <div class="card p-card stack">
      <div>
        <h2 class="semi" style="margin:0;font-size:18px">Registrar ingreso</h2>
        <p class="small muted" style="margin:4px 0 0">Cuando llega mercadería, componentes o insumos al depósito.</p>
      </div>
      <label class="small">Artículo
        <select id="cItem" class="inp" style="margin-top:4px" onchange="const it=porId(this.value);if(it&&it.proveedor&&!$('cProv').value)$('cProv').value=it.proveedor;">
          ${activos.map(i => `<option value="${i.id}" ${i.id === selItem?.id ? 'selected' : ''}>${TIPO_LABEL[i.tipo].split(' ')[0]} ${esc(i.nombre)} (hay ${i.stock} ${esc(i.unidad)})</option>`).join('')}
        </select>
      </label>
      <label class="small">Cantidad que ingresa
        <input id="cQty" type="number" min="1" value="1" class="inp" style="margin-top:4px">
      </label>
      <label class="small">Proveedor <span class="muted">(opcional — persona o empresa)</span>
        <input id="cProv" list="provs" class="inp" style="margin-top:4px" value="${esc(selItem?.proveedor || '')}" placeholder="Ej: Embalajes Norte">
        ${datalistProveedores()}
      </label>
      <div class="grid2">
        <label class="small">Precio unitario <span class="muted">(opcional)</span>
          <input id="cPrice" type="number" min="0" step="any" class="inp" style="margin-top:4px" placeholder="$"></label>
        <label class="small">Nota <span class="muted">(opcional)</span>
          <input id="cNote" class="inp" style="margin-top:4px" placeholder="Factura, remito..."></label>
      </div>
      <button class="btn" style="padding:12px" onclick="guardarIngreso()">📥 Sumar al stock</button>
    </div>
    <div class="card p-card">
      <h2 class="semi" style="margin:0 0 12px;font-size:16px">Ingresos recientes</h2>
      ${S.ingresos.length ? S.ingresos.slice(0, 10).map(ing => `
        <div class="list-row">
          <div class="grow small">
            <div><b>+${ing.cantidad} ${esc(ing.unidad)}</b> · ${esc(ing.articulo_nombre)}</div>
            <div class="xs muted">${esc(ing.usuario)}${ing.proveedor ? ' · ' + esc(ing.proveedor) : ''}${ing.precio ? ` · $${ing.precio}` : ''}${ing.nota ? ` (${esc(ing.nota)})` : ''}</div>
          </div>
          <span class="xs muted nowrap">${fmtRel(ing.fecha)}</span>
        </div>`).join('') : '<p class="small muted" style="margin:0">Todavía no hay ingresos registrados.</p>'}
    </div>
  </div>`;
}

async function guardarIngreso() {
  const aid = Number($('cItem').value);
  const q = Number($('cQty').value) || 0;
  const prov = $('cProv').value.trim();
  const precioVal = $('cPrice').value.trim();
  const nota = $('cNote').value.trim();
  if (q <= 0) return toast('⚠️ Ingresá una cantidad mayor a 0');

  try {
    const r = await api('POST', '/api/ingresos', {
      usuario: S.usuario,
      articulo_id: aid,
      cantidad: q,
      proveedor: prov,
      precio: precioVal ? Number(precioVal) : null,
      nota,
    });
    await cargarDatosVista('ingreso');
    S.preIng = aid;
    render();
    toast(`📥 +${q} ${esc(r.articulo.unidad)} de ${esc(r.articulo.nombre)}`);
  } catch (e) {
    toast('⚠️ ' + esc(e.message));
  }
}

/* ---------- AVISOS (Fase 4) ---------- */
function vAvisos() {
  const a = S.cfgAvisos.app, m = S.cfgAvisos.mail;
  const tg = (grp, k, l, desc, dis = false) => `
    <div class="list-row ${dis ? 'disabled-block' : ''}" style="align-items:flex-start">
      <div class="grow"><div class="small semi">${l}</div>${desc ? `<div class="xs muted">${desc}</div>` : ''}</div>
      <button class="tgl ${S.cfgAvisos[grp][k] ? 'on' : ''}" onclick="toggleAvisoCfg('${grp}','${k}')"></button>
    </div>`;

  return `
  <div class="grid3-xl">
    <div class="card p-card">
      <div class="row between" style="margin-bottom:12px">
        <h2 class="semi" style="margin:0;font-size:16px">Centro de avisos</h2>
        <button class="small link" onclick="marcarAvisosLeidos()">Marcar leído</button>
      </div>
      ${S.notifs.length ? S.notifs.map(n => `
        <div class="list-row" style="align-items:flex-start;${n.leida ? 'opacity:.6' : ''}">
          <div style="font-size:18px">${NOTIF_IC[n.tipo] || '🔔'}</div>
          <div class="grow">
            <div class="small ${n.leida ? '' : 'semi'}">${esc(n.mensaje)}</div>
            <div class="xs muted" style="margin-top:2px">${fmtRel(n.fecha)}${n.enviada_mail ? ' · ✉️ Gmail enviado' : ''}</div>
          </div>
          ${n.leida ? '' : '<span class="dot-unread"></span>'}
        </div>`).join('') : '<p class="small muted" style="margin:0">No hay avisos todavía.</p>'}
    </div>

    <div class="card p-card">
      <div class="row" style="margin-bottom:4px"><span style="font-size:18px">📱</span><h2 class="semi" style="margin:0;font-size:16px">Avisos en la app</h2></div>
      <p class="xs muted" style="margin:0 0 8px">Campanita y centro de avisos. Se ven en la notebook y en el celular.</p>
      ${tg('app', 'on', 'Activar avisos en la app', 'Interruptor general')}
      ${tg('app', 'desp', 'Al cargar un despacho', 'Detalle de lo que se descontó', !a.on)}
      ${tg('app', 'photo', 'Al cargar una planilla por foto', 'Resumen de lo leído', !a.on)}
      ${tg('app', 'low', 'Stock BAJO', 'Cuando llega al mínimo', !a.on)}
      ${tg('app', 'crit', 'Stock CRÍTICO', 'Prioridad alta', !a.on)}
    </div>

    <div class="card p-card">
      <div class="row" style="margin-bottom:4px"><span style="font-size:18px">✉️</span><h2 class="semi" style="margin:0;font-size:16px">Avisos por Gmail</h2></div>
      <p class="xs muted" style="margin:0 0 8px">Se envían desde la cuenta Gmail del negocio (${m.tiene_clave ? 'contraseña cargada ✅' : `<button class="link dotted xs" onclick="ir('config')">cargar contraseña en Configuración →</button>`}).</p>
      ${tg('mail', 'on', 'Activar envío por Gmail', 'Interruptor general')}
      <div class="${m.on ? '' : 'disabled-block'}">
        <label class="xs muted" style="display:block;padding:8px 0">Cuenta que envía
          <input class="inp small" style="margin-top:4px" value="${esc(m.from)}" onchange="S.cfgAvisos.mail.from=this.value;guardarCfgAvisos()">
        </label>
        ${tg('mail', 'desp', 'Cada despacho', 'Puede ser mucho mail: apagado por defecto')}
        ${tg('mail', 'low', 'Stock BAJO', '')}
        ${tg('mail', 'crit', 'Stock CRÍTICO', '')}
        ${tg('mail', 'week', 'Resumen semanal', 'Stock, faltantes, pedidos por canal y consumo')}
        ${m.week ? `<div class="grid2" style="padding:8px 0">
          <label class="xs muted">Día<select class="inp small" style="margin-top:4px" onchange="S.cfgAvisos.mail.day=this.value;guardarCfgAvisos()">
            ${['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'].map(d => `<option ${d === m.day ? 'selected' : ''}>${d}</option>`).join('')}</select></label>
          <label class="xs muted">Hora<input type="time" class="inp small" style="margin-top:4px" value="${esc(m.hour)}" onchange="S.cfgAvisos.mail.hour=this.value;guardarCfgAvisos()"></label>
        </div>` : ''}
        <div style="padding:10px 0">
          <div class="small semi" style="margin-bottom:6px">Destinatarios</div>
          <div class="chips-wrap" style="margin-bottom:8px">
            ${(m.emails || []).map((e, k) => `<span class="btn2 sm">${esc(e)} <button onclick="S.cfgAvisos.mail.emails.splice(${k},1);guardarCfgAvisos()">✕</button></span>`).join('')}
          </div>
          <div class="row">
            <input id="newMail" class="inp small" placeholder="agregar@gmail.com">
            <button class="btn2" onclick="const v=$('newMail').value.trim();if(v){S.cfgAvisos.mail.emails.push(v);guardarCfgAvisos()}">Agregar</button>
          </div>
        </div>
        <button class="btn" style="width:100%" onclick="enviarResumenPrueba()">📊 Enviar resumen de prueba</button>
      </div>
    </div>
  </div>`;
}

async function toggleAvisoCfg(grp, k) {
  S.cfgAvisos[grp][k] = !S.cfgAvisos[grp][k];
  await guardarCfgAvisos();
}

async function guardarCfgAvisos() {
  try {
    S.cfgAvisos = await api('PUT', '/api/avisos/config', S.cfgAvisos);
    render();
  } catch (e) { toast('⚠️ ' + esc(e.message)); }
}

async function marcarAvisosLeidos() {
  await api('POST', '/api/avisos/leer-todas');
  S.notifs.forEach(n => { n.leida = 1; });
  render(); actualizarCampanita();
}

async function enviarResumenPrueba() {
  try {
    const r = await api('POST', '/api/avisos/resumen-prueba');
    await cargarDatosVista('avisos');
    render(); actualizarCampanita();
    toast(r.mail_enviado ? `📊 Resumen enviado por Gmail` : `📊 Resumen generado en el centro de avisos`);
  } catch (e) { toast('⚠️ ' + esc(e.message)); }
}

/* ---------- PLANILLA POR FOTO + ANTI-DUPLICADOS (Fase 7) ---------- */
const DUP_BADGE = {
  nueva: ['🆕 Nueva', 'b-ok'],
  ya_cargada: ['✔️ Ya cargada', 'b-neutral'],
  modificada: ['✏️ Modificada', 'b-low'],
  posible_duplicado: ['❓ Posible duplicado', 'b-crit'],
};
const CONF_BADGE = {
  alta: ['✅ Lectura segura', 'b-ok'],
  media: ['⚠️ Revisar letra', 'b-low'],
  baja: ['❗ Dudosa', 'b-crit'],
};

function vPlanilla() {
  const tipos = S.planillasInfo.tipos?.length ? S.planillasInfo.tipos : [
    { id: 'diaria', titulo: '📋 DIARIA 4 ok (Local / Revendedores / Extras)', columnas_ref: 'N° · Total unid. · A · B · B Prem · Fernetero · Familiar · Correa · C · M · Fecha · Comprador · Local o Transporte' },
    { id: 'tiendanube', titulo: '🛍️ Tienda Nube 1', columnas_ref: '# · Total unidades · A · B · B Prem · Fernetero · Familiar · Correa · C · M · Fecha · Comprador · Retiro por local' },
    { id: 'mercadolibre', titulo: '🟡 Mercado Libre', columnas_ref: 'N° de pedido · Fecha · # de pedido · Nombre · Producto · Correa · Cantidad · Factura' },
  ];
  const tipoSel = tipos.find(t => t.id === S.planillaTipo) || tipos[0];
  const prods = S.items.filter(i => i.activo && i.tipo === 'producto');
  const filas = S.planillaFilas || [];
  const seleccionadas = filas.filter(f => f.seleccionada);
  const cNuevas = filas.filter(f => f.estado_dup === 'nueva').length;
  const cYaCarg = filas.filter(f => f.estado_dup === 'ya_cargada').length;
  const cModif = filas.filter(f => f.estado_dup === 'modificada' || f.estado_dup === 'posible_duplicado').length;

  return `
  <div class="stack" style="gap:16px">
    <div class="card p-card stack">
      <div class="row between" style="flex-wrap:wrap;gap:10px">
        <div>
          <h2 class="semi" style="margin:0;font-size:18px">📸 Cargar planilla de papel por foto</h2>
          <p class="small muted" style="margin:4px 0 0">Elegí qué planilla vas a fotografiar, subí la foto (o probá con un ejemplo) y revisá las filas antes de descontar el stock.</p>
        </div>
        <div class="row" style="flex-wrap:wrap;gap:8px">
          <a class="btn2 sm nowrap" href="/api/planillas/imprimible-ml" target="_blank" style="text-decoration:none">🖨️ Imprimir hoja Mercado Libre</a>
          ${S.planillasInfo.tiene_excel ? `<a class="btn2 sm nowrap" href="/api/planillas/excel" download style="text-decoration:none">📥 Descargar Excel original</a>` : ''}
        </div>
      </div>

      <div>
        <div class="small semi" style="margin-bottom:6px">1. ¿Qué planilla es?</div>
        <div class="chips-wrap">
          ${tipos.map(t => `<button class="chip ${S.planillaTipo === t.id ? 'on' : ''}" onclick="S.planillaTipo='${t.id}';S.planillaFilas=[];render()">${esc(t.titulo)}</button>`).join('')}
        </div>
        <div class="xs muted" style="margin-top:6px">Columnas reconocidas: ${esc(tipoSel.columnas_ref)}</div>
      </div>

      <div class="grid2" style="align-items:end">
        <label class="small">2. Foto de la planilla (cámara del celular o archivo)
          <input id="inpFotoPlanilla" type="file" accept="image/*" capture="environment" class="inp" style="margin-top:4px" onchange="alElegirFotoPlanilla(this)">
        </label>
        <div class="row" style="gap:8px;flex-wrap:wrap">
          <button class="btn" onclick="analizarPlanilla(false)" ${S.planillaAnalizando ? 'disabled' : ''}>
            ${S.planillaAnalizando ? '⏳ Leyendo planilla...' : '🔍 Analizar foto con IA'}
          </button>
          <button class="btn2" onclick="analizarPlanilla(true)" ${S.planillaAnalizando ? 'disabled' : ''}>
            🧪 Probar con ejemplo (${S.planillaTipo === 'diaria' ? 'DIARIA 4 ok' : S.planillaTipo === 'tiendanube' ? 'Tienda Nube 1' : 'Mercado Libre'})
          </button>
        </div>
      </div>
      ${S.planillaImgBase64 ? `<div class="row small"><span class="badge b-ok">📷 Foto lista para analizar</span><button class="link xs" onclick="S.planillaImgBase64=null;render()">Quitar foto</button></div>` : ''}
    </div>

    ${filas.length ? `
    <div class="card p-card stack">
      <div class="row between" style="flex-wrap:wrap;gap:10px">
        <div>
          <h3 class="semi" style="margin:0;font-size:16px">3. Revisión y control anti-duplicados (${filas.length} filas leídas)</h3>
          <p class="xs muted" style="margin:2px 0 0">Las filas <b>✔️ Ya cargadas</b> vienen destildadas automáticamente para no descontar dos veces aunque saques foto a la misma hoja.</p>
        </div>
        <div class="row" style="gap:6px;flex-wrap:wrap">
          <span class="badge b-ok">🆕 ${cNuevas} nueva(s)</span>
          <span class="badge b-neutral">✔️ ${cYaCarg} ya cargada(s)</span>
          ${cModif ? `<span class="badge b-low">✏️ ${cModif} a revisar</span>` : ''}
        </div>
      </div>

      <div class="stack" style="gap:10px">
        ${filas.map((f, idx) => {
          const [dupTxt, dupCls] = DUP_BADGE[f.estado_dup] || DUP_BADGE.nueva;
          const [confTxt, confCls] = CONF_BADGE[f.confianza] || CONF_BADGE.alta;
          return `
          <div class="subbox" style="${f.seleccionada ? 'border-left:4px solid var(--primary)' : 'opacity:0.68'}">
            <div class="row between" style="flex-wrap:wrap;gap:8px;margin-bottom:8px">
              <label class="row semi" style="cursor:pointer">
                <input type="checkbox" ${f.seleccionada ? 'checked' : ''} onchange="S.planillaFilas[${idx}].seleccionada=this.checked;render()">
                <span>Fila / N°:</span>
                <input class="inp small" style="width:82px;padding:3px 6px" value="${esc(f.nro_fila)}" onchange="S.planillaFilas[${idx}].nro_fila=this.value">
              </label>
              <div class="row" style="gap:6px;flex-wrap:wrap">
                <span class="badge ${dupCls}" title="${esc(f.detalle_dup)}">${dupTxt}</span>
                <span class="badge ${confCls}">${confTxt}</span>
              </div>
            </div>

            <div class="grid3-xl" style="gap:8px;margin-bottom:8px">
              <label class="xs muted">Canal
                <select class="inp small" style="margin-top:2px" onchange="S.planillaFilas[${idx}].canal=this.value;render()">
                  ${S.canales.map(c => `<option ${c === f.canal ? 'selected' : ''}>${esc(c)}</option>`).join('')}
                </select>
              </label>
              ${f.canal === 'Revendedor' ? `<label class="xs muted">Envío (Revendedor)
                <select class="inp small" style="margin-top:2px" onchange="S.planillaFilas[${idx}].envio=this.value">
                  ${S.envios.map(e => `<option ${e === f.envio ? 'selected' : ''}>${esc(e)}</option>`).join('')}
                </select>
              </label>` : `<label class="xs muted"># Pedido / Correa / Factura
                <input class="inp small" style="margin-top:2px" value="${esc([f.pedido_nro, f.correa ? 'Correa ' + f.correa : '', f.factura ? 'Fact. ' + f.factura : ''].filter(Boolean).join(' · '))}"
                  placeholder="Opcional" onchange="S.planillaFilas[${idx}].correa=this.value">
              </label>`}
              <label class="xs muted">Comprador / Cliente
                <input class="inp small" style="margin-top:2px" value="${esc(f.cliente)}" placeholder="Nombre del comprador" onchange="S.planillaFilas[${idx}].cliente=this.value">
              </label>
            </div>

            <div class="stack" style="gap:6px">
              ${(f.items || []).map((it, k) => `
                <div class="line-pill">
                  <span class="small">🏷️ <b>${esc(it.nombre)}</b></span>
                  <div class="row">
                    <input type="number" min="1" value="${it.cantidad}" class="inp small" style="width:68px;padding:3px 6px"
                      onchange="S.planillaFilas[${idx}].items[${k}].cantidad=Math.max(1,Number(this.value)||1);render()">
                    <button class="muted" onclick="S.planillaFilas[${idx}].items.splice(${k},1);render()">✕</button>
                  </div>
                </div>
              `).join('')}
              <div class="row" style="gap:6px">
                <select id="plAddProd_${idx}" class="inp small">
                  ${prods.map(p => `<option value="${p.id}">${esc(p.nombre)}</option>`).join('')}
                </select>
                <button class="btn2 sm nowrap" onclick="agregarProdFilaPlanilla(${idx})">+ Producto</button>
              </div>
            </div>

            <div class="row between" style="margin-top:8px;flex-wrap:wrap;gap:6px">
              <div class="xs muted">
                ${f.nota_ia ? `💡 <b>Lectura:</b> ${esc(f.nota_ia)} · ` : ''}
                <span>${esc(f.detalle_dup || '')}</span>
              </div>
              ${(f.cajas_sugeridas || []).length ? `
                <label class="row xs" style="cursor:pointer">
                  <input type="checkbox" ${f.incluir_cajas ? 'checked' : ''} onchange="S.planillaFilas[${idx}].incluir_cajas=this.checked">
                  <span>📦 Descontar caja sugerida: <b>${f.cajas_sugeridas.map(c => `${c.cantidad}× ${esc(c.nombre)}`).join(', ')}</b></span>
                </label>
              ` : ''}
            </div>
          </div>`;
        }).join('')}
      </div>

      <div class="row between" style="padding-top:6px;flex-wrap:wrap;gap:10px">
        <span class="small muted">Se descontarán <b>${seleccionadas.length}</b> de ${filas.length} fila(s) leídas.</span>
        <button class="btn" style="padding:12px 18px" onclick="confirmarPlanilla()" ${!seleccionadas.length ? 'disabled' : ''}>
          ✅ Confirmar ${seleccionadas.length} fila(s) tildadas y descontar stock
        </button>
      </div>
    </div>` : ''}

    <div class="card p-card">
      <h3 class="semi" style="margin:0 0 10px;font-size:16px">Planillas confirmadas recientemente</h3>
      ${(S.planillasInfo.historial || []).length ? S.planillasInfo.historial.map(h => `
        <div class="list-row small">
          <div>
            <b>${esc(h.tipo_planilla === 'diaria' ? '📋 DIARIA 4 ok' : h.tipo_planilla === 'tiendanube' ? '🛍️ Tienda Nube 1' : '🟡 Mercado Libre')}</b>
            <span class="muted"> · ${h.filas_cargadas} fila(s) confirmada(s) por ${esc(h.usuario)}</span>
          </div>
          <span class="xs muted">${fmtRel(h.fecha)}</span>
        </div>
      `).join('') : '<p class="small muted" style="margin:0">Todavía no se confirmaron planillas por foto.</p>'}
    </div>
  </div>`;
}

function alElegirFotoPlanilla(inp) {
  const file = inp.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    S.planillaImgBase64 = reader.result;
    render();
    toast('📷 Foto cargada. Tocá «Analizar foto con IA».');
  };
  reader.readAsDataURL(file);
}

function agregarProdFilaPlanilla(idx) {
  const sel = $(`plAddProd_${idx}`);
  if (!sel) return;
  const prod = porId(sel.value);
  if (!prod) return;
  const fila = S.planillaFilas[idx];
  const ex = fila.items.find(i => i.articulo_id === prod.id);
  if (ex) ex.cantidad += 1;
  else fila.items.push({ articulo_id: prod.id, nombre: prod.nombre, tipo: prod.tipo, unidad: prod.unidad, cantidad: 1 });
  render();
}

async function analizarPlanilla(usarEjemplo) {
  if (!usarEjemplo && !S.planillaImgBase64) {
    return toast('⚠️ Primero elegí o sacá una foto de la planilla (o tocá «Probar con ejemplo»).');
  }
  S.planillaAnalizando = true;
  render();
  try {
    const r = await api('POST', '/api/planillas/analizar', {
      tipo_planilla: S.planillaTipo,
      imagen_base64: usarEjemplo ? null : S.planillaImgBase64,
      usar_ejemplo: !!usarEjemplo,
    });
    S.planillaFilas = r.filas || [];
    toast(`📸 Se leyeron ${S.planillaFilas.length} fila(s) de la planilla`);
  } catch (e) {
    toast('⚠️ ' + esc(e.message));
  } finally {
    S.planillaAnalizando = false;
    render();
  }
}

async function confirmarPlanilla() {
  const seleccionadas = (S.planillaFilas || []).filter(f => f.seleccionada && f.items?.length);
  if (!seleccionadas.length) return toast('⚠️ Tildá al menos una fila para confirmar');
  try {
    const r = await api('POST', '/api/planillas/confirmar', {
      usuario: S.usuario,
      tipo_planilla: S.planillaTipo,
      id_hoja: S.planillaHojaId || '',
      filas: seleccionadas,
    });
    S.planillaFilas = [];
    S.planillaImgBase64 = null;
    await cargarDatosVista('planilla');
    render();
    actualizarCampanita();
    toast(`✅ Planilla confirmada: ${r.filas_procesadas} despacho(s) descontados del stock`);
  } catch (e) {
    toast('⚠️ ' + esc(e.message));
  }
}

/* ---------- ASISTENTE Y PREVISIÓN (Fase 6) ---------- */
function vChat() {
  const sugs = [
    'Armé 10 estuches ferneteros',
    '¿Qué falta comprar o armar?',
    'Si me piden 15 Estuche Asador y 10 Fernetero, ¿me alcanza?',
    '¿Cuántos estuches hay?',
    '¿Qué pedidos futuros hay?',
    'Mostrame los insumos',
  ];

  return `
  <div class="panel-grid">
    <div class="card chat-box">
      <div class="row" style="padding:14px 16px;border-bottom:1px solid var(--border)">
        <div class="brand-logo" style="border-radius:50%">🤖</div>
        <div>
          <div class="semi">Asistente de stock y previsión</div>
          <div class="xs muted">Consultá stock, simulá pedidos grandes o escribí "armé X estuches..." para cargarlos</div>
        </div>
      </div>
      <div id="msgs" class="chat-msgs">
        ${S.chat.map((m, idx) => `
          <div class="msg-row ${m.from === 'me' ? 'me' : 'bot'}">
            <div class="msg-bubble">
              <div>${esc(m.text)}</div>
              ${m.accion && m.estadoAccion === 'pendiente' ? `
                <div class="row" style="margin-top:10px;gap:8px;flex-wrap:wrap">
                  <button class="btn sm" onclick="confirmarAccionChat(${idx})">✅ Confirmar y cargar</button>
                  <button class="btn2 sm" onclick="cancelarAccionChat(${idx})">✕ Cancelar</button>
                </div>
              ` : m.estadoAccion === 'confirmada' ? `
                <div class="xs semi" style="margin-top:8px;color:var(--ok)">✅ Confirmado y cargado en el stock</div>
              ` : m.estadoAccion === 'cancelada' ? `
                <div class="xs muted" style="margin-top:8px">✕ Operación cancelada</div>
              ` : ''}
            </div>
          </div>`).join('')}
      </div>
      <div class="sug-strip">
        ${sugs.map(s => `<button class="btn2 sm nowrap" onclick="preguntarChat(${JSON.stringify(s).replace(/"/g, '&quot;')})">${esc(s)}</button>`).join('')}
      </div>
      <form class="row" style="padding:12px 16px" onsubmit="event.preventDefault();const i=$('qChat');if(i.value.trim())preguntarChat(i.value);">
        <input id="qChat" class="inp" placeholder="Ej: 'Armé 10 estuches ferneteros' o '¿Me alcanza para 20 Asador?'..." autocomplete="off">
        <button class="btn">Enviar</button>
      </form>
    </div>

    <div class="card p-card stack">
      <div class="chips-wrap">
        <button class="chip ${S.tabPrev === 'sim' ? 'on' : ''}" onclick="S.tabPrev='sim';render()">🔮 Simulador "¿Me alcanza?"</button>
        <button class="chip ${S.tabPrev === 'futuros' ? 'on' : ''}" onclick="S.tabPrev='futuros';render()">📌 Pedidos futuros (${S.pedidosFuturos.length})</button>
        <button class="chip ${S.tabPrev === 'proy' ? 'on' : ''}" onclick="S.tabPrev='proy';render()">📈 Proyección</button>
      </div>
      ${S.tabPrev === 'sim' ? vTabSimulador() : S.tabPrev === 'futuros' ? vTabPedidosFuturos() : vTabProyeccion()}
    </div>
  </div>`;
}

async function preguntarChat(q) {
  const limpio = q.trim();
  if (!limpio) return;
  S.chat.push({ from: 'me', text: limpio });
  render();

  // Si hay una confirmación de armado pendiente y el usuario responde "sí" o "no" por teclado
  if (S.accionChatPendiente) {
    const norm = limpio.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    if (/^(si|dale|ok|confirmar|confirmo|cargalo|cargar|listo)$/.test(norm)) {
      await confirmarAccionChat();
      return;
    }
    if (/^(no|cancelar|anular|salir)$/.test(norm)) {
      cancelarAccionChat();
      return;
    }
  }

  try {
    const r = await api('POST', '/api/chat', { pregunta: limpio });
    if (r.accion_pendiente) {
      // Si había otra acción previa pendiente, marcarla como cancelada
      S.chat.forEach(m => { if (m.estadoAccion === 'pendiente') m.estadoAccion = 'cancelada'; });
      S.accionChatPendiente = r.accion_pendiente;
      S.chat.push({ from: 'bot', text: r.respuesta, accion: r.accion_pendiente, estadoAccion: 'pendiente' });
    } else {
      S.chat.push({ from: 'bot', text: r.respuesta });
    }
  } catch (e) {
    S.chat.push({ from: 'bot', text: '⚠️ Error: ' + e.message });
  }
  render();
  const inp = $('qChat'); if (inp) inp.focus();
}

async function confirmarAccionChat(msgIdx) {
  const msg = msgIdx !== undefined
    ? S.chat[msgIdx]
    : [...S.chat].reverse().find(m => m.accion && m.estadoAccion === 'pendiente');
  const acc = msg?.accion || S.accionChatPendiente;
  if (!acc || acc.tipo !== 'armado') return;

  try {
    const resumenCargados = [];
    for (const it of acc.items) {
      const res = await api('POST', '/api/armados', {
        usuario: S.usuario,
        producto_id: it.producto_id,
        cantidad: it.cantidad,
        nota: 'Cargado desde el chat inteligente',
        forzar: true,
      });
      resumenCargados.push(`• +${it.cantidad} ${it.unidad || 'u'} de ${res.producto.nombre} (stock actual: ${res.producto.stock} ${res.producto.unidad}) — ${res.componentes_descontados} pieza(s) descontadas.`);
    }
    if (msg) msg.estadoAccion = 'confirmada';
    S.accionChatPendiente = null;
    S.chat.push({
      from: 'bot',
      text: `✅ ¡Listo! Ya registré el armado en el stock a nombre de ${S.usuario}:\n` + resumenCargados.join('\n'),
    });
    await cargarDatosVista('chat');
    render();
    actualizarCampanita();
    toast('🛠️ Armado confirmado y cargado desde el chat');
  } catch (e) {
    toast('⚠️ ' + esc(e.message));
  }
}

function cancelarAccionChat(msgIdx) {
  const msg = msgIdx !== undefined
    ? S.chat[msgIdx]
    : [...S.chat].reverse().find(m => m.accion && m.estadoAccion === 'pendiente');
  if (msg) msg.estadoAccion = 'cancelada';
  S.accionChatPendiente = null;
  S.chat.push({ from: 'bot', text: '✕ Operación cancelada. No se modificó el stock.' });
  render();
}

function vTabSimulador() {
  const prods = S.items.filter(i => i.activo && i.tipo !== 'componente');
  const r = S.resultadoSim;
  return `
    <div>
      <h3 class="semi" style="margin:0;font-size:16px">Simular un pedido grande a futuro</h3>
      <p class="xs muted" style="margin:4px 0 0">Cargá qué productos te van a pedir para saber si te alcanza, cuánto stock te quedaría, qué piezas necesitás para armar los faltantes y cuántas cajas lleva.</p>
    </div>
    <div class="row" style="flex-wrap:wrap">
      <select id="simProd" class="inp">${prods.map(p => `<option value="${p.id}">${esc(p.nombre)} (disp: ${p.disponible})</option>`).join('')}</select>
      <input id="simQty" type="number" min="1" value="10" class="inp" style="width:84px">
      <button class="btn2 nowrap" onclick="agregarLineaSim()">+ Agregar</button>
    </div>
    <div class="stack" style="gap:6px">
      ${S.lineasSim.length ? S.lineasSim.map((l, k) => {
        const p = porId(l.articulo_id);
        return `<div class="line-pill">
          <span>${esc(p ? p.nombre : '')} × <b>${l.cantidad}</b></span>
          <button class="muted" onclick="S.lineasSim.splice(${k},1);ejecutarSimulacion()">✕</button>
        </div>`;
      }).join('') : '<p class="xs muted" style="margin:0">Agregá uno o más productos arriba para ver el cálculo.</p>'}
    </div>
    ${S.lineasSim.length ? `<div class="row" style="flex-wrap:wrap">
      <button class="btn grow" onclick="ejecutarSimulacion()">🔮 Calcular previsión</button>
      <button class="btn2" onclick="dlgGuardarPedidoFuturo()">📌 Agendar como pedido futuro</button>
    </div>` : ''}
    ${r ? `<div class="subbox stack" style="gap:10px">
      <div class="small semi">${r.alcanza_stock_directo && r.alcanzan_cajas
        ? '✅ ¡Te alcanza con el stock armado actual!'
        : (!r.alcanza_stock_directo && r.componentes_necesarios.length && r.alcanzan_componentes)
          ? '🛠️ No alcanza con los estuches armados, pero SÍ te alcanzan los componentes para armarlos.'
          : '⚠️ No alcanza con el stock actual: revisá los faltantes abajo.'}</div>
      <div style="overflow-x:auto">
        <table class="tabla small">
          <thead><tr><th>Artículo</th><th>Disp.</th><th>Pedís</th><th>Quedan</th><th>Faltan</th></tr></thead>
          <tbody>
            ${r.productos.map(p => `<tr>
              <td><b>${esc(p.nombre)}</b>${p.comprometido ? `<div class="xs muted">(${p.comprometido} reserv.)</div>` : ''}</td>
              <td>${p.disponible}</td>
              <td><b>${p.pedido}</b></td>
              <td>${badge(p.estado_final)} <b>${p.quedaria}</b></td>
              <td>${p.faltante > 0 ? `<span class="badge b-crit">Faltan ${p.faltante}</span>${p.armables_con_stock !== null ? `<div class="xs muted">armables: ${p.armables_con_stock}</div>` : ''}` : '<span class="badge b-ok">OK</span>'}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
      ${r.componentes_necesarios.length ? `
        <div class="xs semi">🧩 Componentes para armar los estuches faltantes:</div>
        ${r.componentes_necesarios.map(c => `<div class="list-row xs">
          <span>${esc(c.nombre)}</span>
          <span>necesitás <b>${c.necesario}</b> · hay ${c.stock_actual} → ${c.faltante > 0 ? `<span class="badge b-crit">faltan comprar ${c.faltante}</span>` : `<span class="badge b-ok">quedan ${c.quedaria}</span>`}</span>
        </div>`).join('')}
      ` : ''}
      ${r.cajas_estimadas.length ? `
        <div class="xs semi">📦 Cajas de envío estimadas:</div>
        ${r.cajas_estimadas.map(cj => `<div class="list-row xs">
          <span>${esc(cj.nombre)}</span>
          <span>lleva <b>${cj.necesarias}</b> · hay ${cj.stock_actual} → ${cj.faltante > 0 ? `<span class="badge b-crit">faltan ${cj.faltante}</span>` : `<span class="badge b-ok">quedan ${cj.quedaria}</span>`}</span>
        </div>`).join('')}
      ` : ''}
    </div>` : ''}`;
}

async function agregarLineaSim() {
  const aid = Number($('simProd').value);
  const q = Math.max(1, Number($('simQty').value) || 1);
  const ex = S.lineasSim.find(l => l.articulo_id === aid);
  if (ex) ex.cantidad += q;
  else S.lineasSim.push({ articulo_id: aid, cantidad: q });
  await ejecutarSimulacion();
}

async function ejecutarSimulacion() {
  if (!S.lineasSim.length) { S.resultadoSim = null; render(); return; }
  try {
    S.resultadoSim = await api('POST', '/api/prevision/simular', { items: S.lineasSim, descontar_comprometido: true });
    render();
  } catch (e) { toast('⚠️ ' + esc(e.message)); }
}

function dlgGuardarPedidoFuturo() {
  abrirDlg(`<h3>📌 Agendar pedido futuro (reserva)</h3>
    <p class="xs muted" style="margin:0">No descuenta el stock hoy, pero lo deja marcado como <b>comprometido</b> para que sepas cuánto tenés disponible de verdad.</p>
    <label>Cliente / referencia<input class="inp" name="cliente" required placeholder="Ej: Mayorista Córdoba"></label>
    <label>Fecha estimada de entrega<input class="inp" name="fecha" type="date"></label>
    <label>Nota <span class="muted xs">(opcional)</span><input class="inp" name="nota" placeholder="Ej: Seña 50% pagada"></label>`, async fd => {
    await api('POST', '/api/pedidos-futuros', {
      usuario: S.usuario,
      cliente: fd.get('cliente'),
      fecha_estimada: fd.get('fecha') || '',
      nota: fd.get('nota') || '',
      items: S.lineasSim,
    });
    S.lineasSim = []; S.resultadoSim = null; S.tabPrev = 'futuros';
    await cargarDatosVista('chat');
    render();
    toast('📌 Pedido futuro agendado y stock comprometido actualizado');
  });
}

function vTabPedidosFuturos() {
  return `
    <div>
      <h3 class="semi" style="margin:0;font-size:16px">Pedidos futuros pendientes</h3>
      <p class="xs muted" style="margin:4px 0 0">Reservan stock (comprometido) sin descontarlo hasta que se entreguen.</p>
    </div>
    ${S.pedidosFuturos.length ? S.pedidosFuturos.map(pf => `
      <div class="subbox stack" style="gap:6px">
        <div class="row between">
          <div><b>${esc(pf.cliente || 'Pedido #' + pf.id)}</b> ${pf.fecha_estimada ? `<span class="badge b-low">📅 ${esc(pf.fecha_estimada)}</span>` : ''}</div>
          <span class="xs muted">por ${esc(pf.usuario)}</span>
        </div>
        <div class="small">${(pf.items || []).map(it => `<div>• <b>${it.cantidad}×</b> ${esc(it.nombre)} <span class="xs muted">(stock hoy: ${it.stock})</span></div>`).join('')}</div>
        ${pf.nota ? `<div class="xs muted">📝 ${esc(pf.nota)}</div>` : ''}
        <div class="row" style="margin-top:4px">
          <button class="btn sm" style="padding:6px 10px;font-size:12px" onclick="concretarPedidoFuturo(${pf.id})">🚚 Convertir en despacho</button>
          <button class="btn2 sm" onclick="cancelarPedidoFuturo(${pf.id})">✕ Cancelar reserva</button>
        </div>
      </div>`).join('') : `<p class="small muted" style="margin:0">No hay pedidos futuros pendientes. Podés cargar uno desde el <b>🔮 Simulador</b>.</p>`}`;
}

async function concretarPedidoFuturo(id) {
  abrirDlg(`<h3>🚚 Convertir pedido futuro en despacho</h3>
    <label>Canal de venta<select class="inp" name="canal" onchange="$('fEnvFut').classList.toggle('hidden', this.value!=='Revendedor')">
      ${S.canales.map(c => `<option value="${c}" ${c === 'Revendedor' ? 'selected' : ''}>${esc(c)}</option>`).join('')}</select></label>
    <label id="fEnvFut">Forma de envío (Revendedor)<select class="inp" name="envio">
      ${S.envios.map(e => `<option value="${e}">${esc(e)}</option>`).join('')}</select></label>`, async fd => {
    const r = await api('POST', `/api/pedidos-futuros/${id}/concretar`, {
      usuario: S.usuario,
      canal: fd.get('canal'),
      envio: fd.get('envio') || 'Retira en local',
    });
    await cargarDatosVista('chat');
    render(); actualizarCampanita();
    toast(`✅ Convertido en Despacho #${r.despacho.id}`);
  });
}

async function cancelarPedidoFuturo(id) {
  if (!confirm('¿Cancelar este pedido futuro y liberar su stock comprometido?')) return;
  await api('POST', `/api/pedidos-futuros/${id}/cancelar`);
  await cargarDatosVista('chat');
  render();
  toast('Reserva cancelada');
}

function vTabProyeccion() {
  return `
    <div>
      <h3 class="semi" style="margin:0;font-size:16px">Proyección por ritmo de consumo</h3>
      <p class="xs muted" style="margin:4px 0 0">Calcula cuánto sale por día según los despachos registrados, cuántos días te dura el stock disponible y cuánto conviene reponer para cubrir 14 días + el mínimo.</p>
    </div>
    <div style="overflow-x:auto">
      <table class="tabla small">
        <thead><tr><th>Artículo</th><th>Disp.</th><th>Ritmo</th><th>Cobertura</th><th>Sugerido</th></tr></thead>
        <tbody>
          ${S.proyeccion.map(p => `<tr>
            <td><b>${esc(p.nombre)}</b></td>
            <td>${p.disponible} ${esc(p.unidad)}</td>
            <td class="muted">${p.consumo_diario > 0 ? `${p.consumo_diario}/día` : '—'}</td>
            <td>${p.dias_cobertura !== null ? `<b>~${p.dias_cobertura} d</b><div class="xs muted">${esc(p.fecha_quiebre)}</div>` : '<span class="xs muted">sin salidas</span>'}</td>
            <td>${p.sugerencia_reponer > 0 ? `<span class="badge b-low">+${p.sugerencia_reponer} ${esc(p.unidad)}</span>` : '<span class="badge b-ok">OK</span>'}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
}

/* ---------- CONFIGURACIÓN (Fase 5) ---------- */
function vConfig() {
  const sys = S.sistema;
  return `
  <div class="grid3-xl">
    <div class="card p-card stack">
      <div>
        <h2 class="semi" style="margin:0;font-size:16px">📱 Usar desde el celular (WiFi)</h2>
        <p class="xs muted" style="margin:4px 0 0">Con el celular conectado al mismo WiFi del local, escaneá el código QR o escribí esta dirección en el navegador:</p>
      </div>
      <div class="subbox row between" style="flex-wrap:wrap">
        <code class="semi" style="word-break:break-all">${esc(sys.url_lan)}</code>
        <button class="btn2 sm" onclick="navigator.clipboard?.writeText('${esc(sys.url_lan)}');toast('Dirección copiada')">Copiar</button>
      </div>
      ${sys.qr_svg ? `<div class="qr-wrap" style="margin:0 auto">${sys.qr_svg}</div>` : ''}
      <p class="xs muted" style="margin:0">💡 Si desde el celular no abre, verificá que la red WiFi de Windows esté marcada como <b>"Red privada"</b> y permití Python cuando Windows Firewall lo pregunte.</p>
    </div>

    <div class="card p-card stack">
      <div>
        <h2 class="semi" style="margin:0;font-size:16px">🔑 Claves (Gemini y Gmail)</h2>
        <p class="xs muted" style="margin:4px 0 0">Se guardan solo en esta notebook (nunca en el código).</p>
      </div>
      <div class="subbox stack" style="gap:8px">
        <div class="row between" style="flex-wrap:wrap">
          <span class="small semi">🤖 Gemini API (nivel gratuito)</span>
          ${sys.tiene_gemini_key ? '<span class="badge b-ok">Cargada ✅</span>' : '<span class="badge b-low">Sin clave (usa modo local)</span>'}
        </div>
        <div class="xs muted">1. Entrá a <b>aistudio.google.com/apikey</b> con tu cuenta Google.<br>2. Tocá "Create API key" y pegala acá:</div>
        <input id="cfgGemKey" type="password" class="inp small" placeholder="${sys.tiene_gemini_key ? '•••••••• (dejar vacío para no cambiar)' : 'Pegar clave AIza...'}">
        <div class="row" style="flex-wrap:wrap">
          <button class="btn2 sm grow" onclick="guardarClavesCfg()">Guardar clave Gemini</button>
          <button class="btn2 sm" onclick="probarGeminiCfg()">🧪 Probar</button>
        </div>
      </div>

      <div class="subbox stack" style="gap:8px">
        <div class="row between" style="flex-wrap:wrap">
          <span class="small semi">✉️ Gmail (contraseña de aplicación)</span>
          ${sys.tiene_gmail_pass ? '<span class="badge b-ok">Cargada ✅</span>' : '<span class="badge b-low">Sin configurar</span>'}
        </div>
        <div class="xs muted">1. Entrá a <b>myaccount.google.com/apppasswords</b>.<br>2. Creá una contraseña de 16 letras para "StockDepo":</div>
        <input id="cfgMailFrom" class="inp small" value="${esc(sys.mail_from)}" placeholder="tu-correo@gmail.com">
        <input id="cfgMailPass" type="password" class="inp small" placeholder="${sys.tiene_gmail_pass ? '•••••••• (dejar vacío para no cambiar)' : 'Contraseña de 16 letras'}">
        <div class="row" style="flex-wrap:wrap">
          <button class="btn2 sm grow" onclick="guardarClavesCfg()">Guardar Gmail</button>
          <button class="btn2 sm" onclick="probarGmailCfg()">✉️ Enviar prueba</button>
        </div>
      </div>
    </div>

    <div class="card p-card stack">
      <div>
        <h2 class="semi" style="margin:0;font-size:16px">💾 Respaldos de la base de datos</h2>
        <p class="xs muted" style="margin:4px 0 0">El sistema guarda una copia diaria automática en la carpeta <code>backups/</code> (conservando las últimas 30).</p>
      </div>
      <button class="btn" onclick="crearRespaldoAhora()">💾 Crear respaldo ahora</button>
      <div class="stack" style="gap:4px;max-height:320px;overflow-y:auto">
        ${(sys.respaldos || []).length ? sys.respaldos.map(b => `
          <div class="list-row small">
            <div class="grow">
              <div class="xs semi" style="word-break:break-all">${esc(b.nombre)}</div>
              <div class="xs muted">${fmtFechaHora(b.fecha)} · ${b.tamano_kb} KB</div>
            </div>
            <button class="btn2 sm" onclick="restaurarRespaldoCfg('${esc(b.nombre)}')">Restaurar</button>
          </div>`).join('') : '<p class="xs muted" style="margin:0">Todavía no hay respaldos.</p>'}
      </div>
    </div>
  </div>`;
}

async function guardarClavesCfg() {
  const body = {};
  const gk = $('cfgGemKey')?.value.trim();
  const mf = $('cfgMailFrom')?.value.trim();
  const mp = $('cfgMailPass')?.value.trim();
  if (gk) body.gemini_api_key = gk;
  if (mf !== undefined) body.mail_from = mf;
  if (mp) body.gmail_app_password = mp;
  try {
    S.sistema = await api('PUT', '/api/sistema/claves', body);
    render();
    toast('✅ Configuración guardada');
  } catch (e) { toast('⚠️ ' + esc(e.message)); }
}

async function probarGeminiCfg() {
  try {
    const r = await api('POST', '/api/sistema/probar-gemini');
    toast(`✅ Gemini respondió: ${esc(r.respuesta)}`);
  } catch (e) { toast('⚠️ ' + esc(e.message)); }
}

async function probarGmailCfg() {
  try {
    const r = await api('POST', '/api/sistema/probar-gmail');
    toast(`✅ ${esc(r.detalle)}`);
  } catch (e) { toast('⚠️ ' + esc(e.message)); }
}

async function crearRespaldoAhora() {
  try {
    await api('POST', '/api/sistema/respaldos');
    S.sistema = await api('GET', '/api/sistema/info');
    render();
    toast('💾 Respaldo creado correctamente');
  } catch (e) { toast('⚠️ ' + esc(e.message)); }
}

async function restaurarRespaldoCfg(nombre) {
  if (!confirm(`¿Restaurar la base de datos al respaldo "${nombre}"?\n(Se creará antes un respaldo automático del estado actual).`)) return;
  try {
    await api('POST', '/api/sistema/respaldos/restaurar', { nombre });
    await cargarArticulos();
    S.sistema = await api('GET', '/api/sistema/info');
    render();
    toast('✅ Base de datos restaurada');
  } catch (e) { toast('⚠️ ' + esc(e.message)); }
}

/* ---------- DIÁLOGOS (Stock + Recetas) ---------- */
function abrirDlg(html, alGuardar) {
  const d = $('dlg');
  d.innerHTML = `<form method="dialog" class="form" id="dlgForm">${html}
    <div class="err" id="dlgErr"></div>
    <div class="dlg-actions"><button type="button" class="btn2" onclick="$('dlg').close()">Cancelar</button><button class="btn" id="dlgOk">Guardar</button></div></form>`;
  $('dlgForm').onsubmit = async ev => {
    ev.preventDefault();
    $('dlgOk').disabled = true;
    try { await alGuardar(new FormData($('dlgForm'))); d.close(); }
    catch (e) { $('dlgErr').textContent = e.message; }
    finally { $('dlgOk').disabled = false; }
  };
  d.showModal();
  const primero = d.querySelector('input:not([type=checkbox]),select'); if (primero) primero.focus();
}

const optsCaja = sel => `<option value="">Sin caja por defecto</option>` + cajasActivas().map(c => `<option value="${c.id}" ${c.id === sel ? 'selected' : ''}>${esc(c.nombre)}</option>`).join('');
const numero = (fd, k) => Number(fd.get(k) || 0);

function dlgLimites(id) {
  const i = porId(id);
  abrirDlg(`<h3>Límites de ${esc(i.nombre)}</h3>
    <div class="grid2">
      <label>Stock mínimo <span class="muted xs">(aviso "bajo")</span><input class="inp" name="minimo" type="number" min="0" value="${i.minimo}" required></label>
      <label>Stock crítico<input class="inp" name="critico" type="number" min="0" value="${i.critico}" required></label>
    </div>`, async fd => {
    const a = await api('PATCH', `/api/articulos/${id}`, { minimo: numero(fd, 'minimo'), critico: numero(fd, 'critico') });
    Object.assign(i, a); pintarFilas(); toast('Límites actualizados');
  });
}

function dlgEditar(id) {
  const i = porId(id);
  abrirDlg(`<h3>Editar artículo</h3>
    <label>Nombre<input class="inp" name="nombre" value="${esc(i.nombre)}" required maxlength="120"></label>
    <div class="grid2">
      <label>Tipo<input class="inp" value="${TIPO_LABEL[i.tipo]}" disabled></label>
      <label>Unidad<input class="inp" name="unidad" value="${esc(i.unidad)}" placeholder="u, rollos..."></label>
    </div>
    <div class="grid2">
      <label>Stock contado <span class="muted xs">(hoy: ${i.stock})</span><input class="inp" name="stock" type="number" min="0" value="${i.stock}"></label>
      <label>Proveedor <span class="muted xs">(opcional)</span><input class="inp" name="proveedor" value="${esc(i.proveedor)}" list="provs"></label>
    </div>
    ${i.tipo === 'producto' ? `<label>Caja de envío por defecto<select class="inp" name="caja_id">${optsCaja(i.caja_id)}</select></label>` : ''}
    <label class="row small"><input type="checkbox" name="activo" ${i.activo ? 'checked' : ''}> Artículo activo <span class="muted xs">(destildá para ocultarlo sin borrar su historial)</span></label>
    ${datalistProveedores()}`, async fd => {
    const cambios = { nombre: fd.get('nombre'), unidad: fd.get('unidad') || 'u', proveedor: fd.get('proveedor') || '', activo: fd.get('activo') === 'on' };
    if (i.tipo === 'producto') cambios.caja_id = fd.get('caja_id') ? Number(fd.get('caja_id')) : null;
    let a = await api('PATCH', `/api/articulos/${id}`, cambios);
    const delta = numero(fd, 'stock') - a.stock;
    if (delta) a = await api('POST', `/api/articulos/${id}/ajuste`, { delta, usuario: S.usuario, motivo: 'Conteo / corrección de stock' });
    await cargarArticulos(); pintarFilas(); toast('Artículo actualizado');
  });
}

function datalistProveedores() {
  const provs = [...new Set([
    ...S.items.map(i => i.proveedor),
    ...(S.ingresos || []).map(ing => ing.proveedor),
  ].filter(Boolean))];
  return `<datalist id="provs">${provs.map(p => `<option value="${esc(p)}">`).join('')}</datalist>`;
}

function dlgNuevo(forzarTipo) {
  const tipoInicial = forzarTipo || (S.filtro !== 'todos' ? S.filtro : 'componente');
  abrirDlg(`<h3>Nuevo artículo</h3>
    <label>Nombre<input class="inp" name="nombre" required maxlength="120" placeholder="Ej: Copa de vidrio, Cuchillo asador..."></label>
    <div class="grid2">
      <label>Tipo<select class="inp" name="tipo" onchange="$('filaCaja').classList.toggle('hidden', this.value!=='producto')">
        ${Object.entries(TIPO_LABEL).map(([k, l]) => `<option value="${k}" ${k === tipoInicial ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
      <label>Unidad<input class="inp" name="unidad" value="u" placeholder="u, rollos..."></label>
    </div>
    <div class="grid2">
      <label>Stock actual<input class="inp" name="stock" type="number" min="0" value="0"></label>
      <label>Proveedor <span class="muted xs">(opcional)</span><input class="inp" name="proveedor" list="provs"></label>
    </div>
    <div class="grid2">
      <label>Stock mínimo<input class="inp" name="minimo" type="number" min="0" value="0"></label>
      <label>Stock crítico<input class="inp" name="critico" type="number" min="0" value="0"></label>
    </div>
    <label id="filaCaja" class="${tipoInicial === 'producto' ? '' : 'hidden'}">Caja de envío por defecto<select class="inp" name="caja_id">${optsCaja(null)}</select></label>
    ${datalistProveedores()}`, async fd => {
    const tipo = fd.get('tipo');
    const a = await api('POST', '/api/articulos', {
      nombre: fd.get('nombre'), tipo, unidad: fd.get('unidad') || 'u', stock: numero(fd, 'stock'),
      minimo: numero(fd, 'minimo'), critico: numero(fd, 'critico'), proveedor: fd.get('proveedor') || '',
      caja_id: tipo === 'producto' && fd.get('caja_id') ? Number(fd.get('caja_id')) : null, usuario: S.usuario,
    });
    await cargarArticulos(); render(); toast(`✅ ${esc(a.nombre)} creado`);
  });
}

/* Editor de piezas que lleva un estuche/producto */
let _recetaTmp = [];
function dlgReceta(productoId, conservarTmp = false) {
  const prod = porId(productoId);
  if (!prod) return;
  if (!conservarTmp) {
    _recetaTmp = (prod.receta || []).map(r => ({ componente_id: r.componente_id, cantidad: r.cantidad }));
  }
  const compsDisponibles = () => S.items.filter(i => i.activo && i.tipo === 'componente');

  const pintarItemsReceta = () => {
    const box = $('recItems');
    if (!box) return;
    if (!_recetaTmp.length) {
      box.innerHTML = '<div class="xs muted">Este producto no tiene piezas asignadas. Elegí una abajo y tocá "+ Agregar".</div>';
      return;
    }
    box.innerHTML = _recetaTmp.map((it, idx) => {
      const c = porId(it.componente_id);
      return `<div class="line-pill">
        <span>🧩 ${esc(c ? c.nombre : '')} <span class="xs muted">(stock: ${c ? c.stock : 0})</span></span>
        <div class="row">
          <input type="number" min="1" value="${it.cantidad}" class="inp" style="width:70px;padding:4px 8px"
            onchange="_recetaTmp[${idx}].cantidad=Math.max(1,Number(this.value)||1)">
          <button type="button" class="muted" title="Quitar pieza" onclick="_quitarCompReceta(${idx})">✕</button>
        </div>
      </div>`;
    }).join('');
  };

  window._quitarCompReceta = idx => {
    _recetaTmp.splice(idx, 1);
    pintarItemsReceta();
  };

  window._agregarCompReceta = () => {
    const cid = Number($('recCompSel').value);
    const q = Math.max(1, Number($('recCompQty').value) || 1);
    if (!cid) return;
    const ex = _recetaTmp.find(x => x.componente_id === cid);
    if (ex) ex.cantidad += q;
    else _recetaTmp.push({ componente_id: cid, cantidad: q });
    pintarItemsReceta();
  };

  window._crearCompRapido = async () => {
    const nom = $('nuevoCompNom').value.trim();
    const stk = Math.max(0, Number($('nuevoCompStk').value) || 0);
    if (!nom) return;
    try {
      const c = await api('POST', '/api/articulos', {
        nombre: nom, tipo: 'componente', unidad: 'u', stock: stk, minimo: 5, critico: 2, proveedor: '', usuario: S.usuario,
      });
      S.items.push(c);
      _recetaTmp.push({ componente_id: c.id, cantidad: 1 });
      $('dlg').close();
      dlgReceta(productoId, true);
      toast(`🧩 Pieza "${esc(c.nombre)}" creada y sumada al estuche`);
    } catch (e) {
      $('dlgErr').textContent = e.message;
    }
  };

  const comps = compsDisponibles();
  abrirDlg(`<h3>🧩 Piezas que incluye: ${esc(prod.nombre)}</h3>
    <p class="xs muted" style="margin:0">Estas son las cosas que lleva adentro <b>1 unidad</b> de este estuche. Cuando registrás que armaste este estuche (en <b>🛠️ Armado</b> o por el <b>Chat</b>), el sistema suma el estuche armado y descuenta estas piezas automáticamente.</p>
    <div id="recItems" class="stack" style="gap:6px"></div>
    ${comps.length ? `<div class="row" style="flex-wrap:wrap">
      <select id="recCompSel" class="inp">${comps.map(c => `<option value="${c.id}">${esc(c.nombre)} (${c.stock} ${esc(c.unidad)})</option>`).join('')}</select>
      <input id="recCompQty" type="number" min="1" value="1" class="inp" style="width:74px">
      <button type="button" class="btn2 nowrap" onclick="_agregarCompReceta()">+ Agregar</button>
    </div>` : ''}
    <div class="subbox">
      <div class="xs semi" style="margin-bottom:6px">¿No está la pieza en la lista? Creala rápido:</div>
      <div class="row" style="flex-wrap:wrap">
        <input id="nuevoCompNom" class="inp small" placeholder="Nombre (ej: Copa vidrio)">
        <input id="nuevoCompStk" type="number" min="0" value="0" class="inp small" style="width:84px" title="Stock actual" placeholder="Stock">
        <button type="button" class="btn2 sm nowrap" onclick="_crearCompRapido()">+ Crear pieza</button>
      </div>
    </div>`, async () => {
    await api('PUT', `/api/articulos/${productoId}/receta`, { items: _recetaTmp });
    await cargarArticulos();
    render();
    toast(`✅ Piezas de ${esc(prod.nombre)} guardadas`);
  });
  pintarItemsReceta();
}

/* ---------- campanita ---------- */
async function actualizarCampanita() {
  try {
    const { cantidad } = await api('GET', '/api/notificaciones/no-leidas');
    const b = $('bellCount'); b.textContent = cantidad; b.classList.toggle('hidden', !cantidad);
  } catch { }
}

/* ---------- pantalla de arranque Neón LED ---------- */
let _splashRaf = null;
let _splashTimer = null;

function cerrarSplashNeon() {
  if (_splashRaf) { cancelAnimationFrame(_splashRaf); _splashRaf = null; }
  if (_splashTimer) { clearTimeout(_splashTimer); _splashTimer = null; }
  const el = $('splashNeon');
  if (el) el.classList.add('out');
}

function reproducirSplashNeon() {
  const el = $('splashNeon');
  const wrap = $('splashLogoWrap');
  const laser = $('splashLaser');
  const txt = $('splashTexto');
  const pct = $('splashPct');
  const bar = $('splashBarFill');
  if (!el || !wrap) return;

  if (_splashRaf) cancelAnimationFrame(_splashRaf);
  if (_splashTimer) clearTimeout(_splashTimer);

  el.classList.remove('out');
  wrap.classList.remove('flicker');
  wrap.style.setProperty('--corte', '96%');
  wrap.style.setProperty('--glow-alpha', '0');
  if (laser) laser.style.opacity = '0';
  if (bar) bar.style.width = '0%';
  if (txt) txt.textContent = 'CARGANDO...';
  if (pct) pct.textContent = '0%';

  const durSubida = 2850; // 2.85 s de encendido de abajo hacia arriba
  const durTotal = 3550;  // ~3.55 s en total incluyendo destello final neón
  const t0 = performance.now();
  let flickered = false;

  const step = now => {
    const dt = now - t0;
    if (dt < durSubida) {
      const t = Math.min(1, dt / durSubida);
      // Curva suave (smoothstep)
      const p = t * t * (3 - 2 * t);
      // El área visible del logo va desde 94% (abajo) hasta 4% (arriba)
      const cortePct = 94 - p * 90;
      wrap.style.setProperty('--corte', `${cortePct.toFixed(2)}%`);
      wrap.style.setProperty('--glow-alpha', (p * 0.65).toFixed(2));
      if (laser) {
        laser.style.opacity = (t > 0.03 && t < 0.98) ? '1' : '0';
      }
      const num = Math.round(p * 100);
      const pts = '.'.repeat((Math.floor(dt / 260) % 3) + 1);
      if (txt) txt.textContent = `CARGANDO${pts}`;
      if (pct) pct.textContent = `${num}%`;
      if (bar) bar.style.width = `${num}%`;
      _splashRaf = requestAnimationFrame(step);
    } else {
      wrap.style.setProperty('--corte', '0%');
      wrap.style.setProperty('--glow-alpha', '0.85');
      if (laser) laser.style.opacity = '0';
      if (txt) txt.textContent = '¡SISTEMA LISTO!';
      if (pct) pct.textContent = '100%';
      if (bar) bar.style.width = '100%';
      if (!flickered) {
        flickered = true;
        wrap.classList.add('flicker');
      }
      if (dt < durTotal) {
        _splashRaf = requestAnimationFrame(step);
      } else {
        cerrarSplashNeon();
      }
    }
  };
  _splashRaf = requestAnimationFrame(step);
}
window.reproducirSplashNeon = reproducirSplashNeon;
window.cerrarSplashNeon = cerrarSplashNeon;

/* ---------- inicio ---------- */
async function iniciar() {
  reproducirSplashNeon();
  let meta = null;
  let errorUltimo = null;

  // Reintenta hasta 8 veces (aprox 4.5 s) para absorber el tiempo de arranque del servidor
  for (let intento = 1; intento <= 8; intento++) {
    try {
      meta = await api('GET', '/api/meta');
      if (meta && meta.usuarios) break;
    } catch (e) {
      errorUltimo = e;
      if (intento < 8) {
        await new Promise(r => setTimeout(r, 600));
      }
    }
  }

  if (!meta || !meta.usuarios) {
    cerrarSplashNeon(true);
    const detalle = errorUltimo ? esc(errorUltimo.message) : 'El servidor no respondió a tiempo.';
    $('contenido').innerHTML = `
      <div class="card empty" style="max-width:520px;margin:30px auto;text-align:center;padding:26px">
        <div style="font-size:38px;margin-bottom:10px">⚠️</div>
        <h3 style="margin:0 0 8px">No se pudo conectar con el servidor</h3>
        <p class="muted small" style="margin:0 0 16px">Verificá que la ventana negra de <b>iniciar.bat</b> esté abierta en la notebook.<br><span class="xs muted">Detalle: ${detalle}</span></p>
        <button class="btn btn-primary" onclick="iniciar()" style="margin:0 auto">🔄 Reintentar conexión</button>
      </div>`;
    return;
  }

  S.usuarios = meta.usuarios;
  S.canales = meta.canales || S.canales;
  S.envios = meta.envios || S.envios;
  S.reglaCajas = meta.regla_cajas || S.reglaCajas;
  renderUsuarios();
  try {
    await cargarDatosVista(S.vista);
  } catch (e) {
    console.warn('Advertencia al cargar vista inicial:', e);
  }
  render();
  actualizarCampanita(); setInterval(actualizarCampanita, 30000);
}

iniciar();
