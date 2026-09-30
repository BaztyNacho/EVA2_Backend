/* ==========================================================================
   VENTAS.JS - REGISTRO DE VENTAS (dashboard, solo ADMINISTRADOR)
   --------------------------------------------------------------------------
   1. Pide GET /api/reportes/ventas/?dias=N (un solo JSON con todo).
   2. Dibuja los indicadores con su variación vs. el período anterior.
   3. Dibuja 5 gráficos con Chart.js, usando los colores de la tienda.
   4. Llena las tablas de clientes, stock crítico y últimas ventas.
   Al cambiar el período se destruyen los gráficos anteriores y se
   vuelven a dibujar con los datos nuevos.
   ========================================================================== */

const usuarioVentas = requerirSesion('ADMINISTRADOR');

/* Colores de la paleta (los mismos de tienda.css) */
const COLORES = {
  naranja: '#F47A18',
  accion: '#B85210',
  carbon: '#171311',
  ambar: '#E29C40',
  verde: '#2F7A58',
  suave: '#6B625C',
  borde: '#D6D0CA',
};
const PALETA_CATEGORIAS = ['#F47A18', '#171311', '#E29C40', '#2F7A58', '#B85210', '#8A817B', '#C9C2BC'];
const COLOR_ESTADO = { PENDIENTE: '#F5C451', PAGADO: '#171311', ENTREGADO: '#2F7A58', CANCELADO: '#6B625C' };

const formatoCompacto = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', notation: 'compact' });
const formatoFechaCorta = new Intl.DateTimeFormat('es-CL', { day: 'numeric', month: 'short' });
const formatoFechaLarga = new Intl.DateTimeFormat('es-CL', { day: 'numeric', month: 'short', year: 'numeric' });

let graficos = [];   // gráficos dibujados (se destruyen al cambiar de período)

/* Configuración común de Chart.js: tipografía y colores de la tienda */
if (window.Chart) {
  Chart.defaults.font.family = "'IBM Plex Sans', system-ui, sans-serif";
  Chart.defaults.color = COLORES.suave;
  Chart.defaults.borderColor = '#EDE9E4';
}


/* ==========================================================================
   INDICADORES
   ========================================================================== */

/* Texto y color de la variación. En la tasa de cancelación, bajar es
   bueno (verde) y subir es malo (rojo); en el resto, al revés. */
function textoVariacion(valor, { invertir = false, unidad = '%' } = {}) {
  if (valor === null || valor === undefined) {
    return '<span class="variacion neutra">Sin período anterior</span>';
  }
  if (valor === 0) return '<span class="variacion neutra">Sin cambios</span>';
  const positivo = invertir ? valor < 0 : valor > 0;
  const flecha = valor > 0 ? 'bi-arrow-up-right' : 'bi-arrow-down-right';
  const signo = valor > 0 ? '+' : '';
  return `<span class="variacion ${positivo ? 'sube' : 'baja'}"><i class="bi ${flecha}"></i> ${signo}${valor}${unidad} vs. período anterior</span>`;
}

function mostrarIndicadores(indicadores) {
  const v = indicadores.variaciones;
  const tarjetas = [
    { icono: 'bi-cash-stack', etiqueta: 'Ingresos', valor: precioCLP(indicadores.ingresos), variacion: textoVariacion(v.ingresos) },
    { icono: 'bi-bag-check', etiqueta: 'Órdenes vendidas', valor: indicadores.ordenes, variacion: textoVariacion(v.ordenes) },
    { icono: 'bi-receipt', etiqueta: 'Ticket promedio', valor: precioCLP(indicadores.ticket), variacion: textoVariacion(v.ticket) },
    { icono: 'bi-box-seam', etiqueta: 'Unidades vendidas', valor: indicadores.unidades, variacion: textoVariacion(v.unidades) },
    { icono: 'bi-x-octagon', etiqueta: 'Tasa de cancelación', valor: `${indicadores.tasa_cancelacion}%`,
      variacion: textoVariacion(v.cancelacion, { invertir: true, unidad: ' pp' }) },
    { icono: 'bi-hourglass-split', etiqueta: 'Por cobrar', valor: precioCLP(indicadores.por_cobrar),
      variacion: `<span class="variacion neutra">${indicadores.ordenes_pendientes} ${indicadores.ordenes_pendientes === 1 ? 'orden pendiente' : 'órdenes pendientes'}</span>` },
  ];
  document.getElementById('indicadores').innerHTML = tarjetas.map(t => `
    <div class="col">
      <div class="indicador">
        <div class="etiqueta"><i class="bi ${t.icono} bi-titulo"></i>${t.etiqueta}</div>
        <div class="valor">${t.valor}</div>
        ${t.variacion}
      </div>
    </div>`).join('');
}


/* ==========================================================================
   GRÁFICOS (Chart.js)
   ========================================================================== */
function crearGrafico(id, configuracion) {
  const grafico = new Chart(document.getElementById(id), configuracion);
  graficos.push(grafico);
}

/* Etiquetas en pesos: "$1,2 M" en los ejes y "$1.234.567" en los tooltips */
const ejePesos = { ticks: { callback: valor => formatoCompacto.format(valor) } };
const tooltipPesos = { callbacks: { label: contexto => ` ${precioCLP(contexto.parsed.y ?? contexto.parsed.x ?? contexto.parsed)}` } };

function dibujarGraficos(datos) {
  graficos.forEach(grafico => grafico.destroy());
  graficos = [];

  // 1. Ingresos por día (líneas con área suave)
  crearGrafico('grafico-dias', {
    type: 'line',
    data: {
      labels: datos.ingresos_por_dia.map(d => formatoFechaCorta.format(new Date(`${d.fecha}T12:00:00`))),
      datasets: [{
        label: 'Ingresos',
        data: datos.ingresos_por_dia.map(d => d.ingresos),
        borderColor: COLORES.naranja,
        backgroundColor: 'rgba(244, 122, 24, .12)',
        fill: true,
        cubicInterpolationMode: 'monotone',   // curva suave que no baja de 0
        pointRadius: datos.ingresos_por_dia.length > 40 ? 0 : 3,
        pointBackgroundColor: COLORES.accion,
      }],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: tooltipPesos },
      scales: { y: { beginAtZero: true, ...ejePesos }, x: { ticks: { maxTicksLimit: 10 } } },
    },
  });

  // 2. Ingresos por categoría (dona con porcentajes en el tooltip)
  const totalCategorias = datos.por_categoria.reduce((suma, c) => suma + c.ingresos, 0);
  crearGrafico('grafico-categorias', {
    type: 'doughnut',
    data: {
      labels: datos.por_categoria.map(c => c.categoria),
      datasets: [{
        data: datos.por_categoria.map(c => c.ingresos),
        backgroundColor: PALETA_CATEGORIAS,
        borderColor: '#fff',
        borderWidth: 2,
      }],
    },
    options: {
      maintainAspectRatio: false,
      cutout: '62%',
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 12, padding: 12 } },
        tooltip: {
          callbacks: {
            label: contexto => {
              const porcentaje = totalCategorias ? (contexto.parsed * 100 / totalCategorias).toFixed(1) : 0;
              return ` ${precioCLP(contexto.parsed)} (${porcentaje}%)`;
            },
          },
        },
      },
    },
  });

  // 3. Top 5 productos (barras horizontales por unidades)
  crearGrafico('grafico-top', {
    type: 'bar',
    data: {
      labels: datos.top_productos.map(p => p.nombre_producto),
      datasets: [{ label: 'Unidades', data: datos.top_productos.map(p => p.unidades), backgroundColor: COLORES.naranja, borderRadius: 4 }],
    },
    options: {
      indexAxis: 'y',
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: contexto => {
              const producto = datos.top_productos[contexto.dataIndex];
              return ` ${producto.unidades} unidades · ${precioCLP(producto.ingresos)}`;
            },
          },
        },
      },
      scales: { x: { beginAtZero: true, ticks: { precision: 0 } }, y: { ticks: { callback(valor) { const t = this.getLabelForValue(valor); return t.length > 22 ? `${t.slice(0, 21)}…` : t; } } } },
    },
  });

  // 4. Ingresos por marca (barras verticales)
  crearGrafico('grafico-marcas', {
    type: 'bar',
    data: {
      labels: datos.por_marca.map(m => m.marca),
      datasets: [{ label: 'Ingresos', data: datos.por_marca.map(m => m.ingresos), backgroundColor: COLORES.carbon, borderRadius: 4 }],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: tooltipPesos },
      scales: { y: { beginAtZero: true, ...ejePesos } },
    },
  });

  // 5. Órdenes por estado (dona con los colores de los badges de estado)
  crearGrafico('grafico-estados', {
    type: 'doughnut',
    data: {
      labels: datos.por_estado.map(e => e.etiqueta),
      datasets: [{
        data: datos.por_estado.map(e => e.cantidad),
        backgroundColor: datos.por_estado.map(e => COLOR_ESTADO[e.estado]),
        borderColor: '#fff',
        borderWidth: 2,
      }],
    },
    options: {
      maintainAspectRatio: false,
      cutout: '55%',
      plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, padding: 10 } } },
    },
  });
}


/* ==========================================================================
   TABLAS
   ========================================================================== */
function filaVacia(columnas, texto) {
  return `<tr><td colspan="${columnas}" class="text-muted text-center py-3">${texto}</td></tr>`;
}

function mostrarTablas(datos) {
  document.getElementById('tabla-clientes').innerHTML = datos.mejores_clientes.length
    ? datos.mejores_clientes.map(c => `
        <tr>
          <td class="fw-semibold">${escaparHTML(c.cliente)}</td>
          <td class="text-end">${c.compras}</td>
          <td class="text-end">${precioCLP(c.total)}</td>
        </tr>`).join('')
    : filaVacia(3, 'Sin ventas en este período.');

  document.getElementById('tabla-stock').innerHTML = datos.stock_critico.length
    ? datos.stock_critico.map(p => `
        <tr>
          <td><a href="/panel/?editar=${p.id}" class="fw-semibold" title="Editar en el panel">${escaparHTML(p.nombre)}</a></td>
          <td class="text-end">${p.vendidas}</td>
          <td class="text-end"><span class="${p.stock === 0 ? 'stock-cero' : 'stock-bajo'}">${p.stock}</span></td>
        </tr>`).join('')
    : filaVacia(3, 'Ningún producto vendido tiene stock crítico.');

  document.getElementById('tabla-ultimas').innerHTML = datos.ultimas_ventas.length
    ? datos.ultimas_ventas.map(o => `
        <tr>
          <td><span class="codigo-orden">#${o.codigo.slice(0, 8).toUpperCase()}</span></td>
          <td class="text-nowrap">${formatoFechaLarga.format(new Date(o.fecha_pago))}</td>
          <td>${escaparHTML(o.cliente)}</td>
          <td><span class="badge badge-estado-${o.estado}">${escaparHTML(o.estado_display)}</span></td>
          <td class="text-end">${precioCLP(o.total)}</td>
        </tr>`).join('')
    : filaVacia(5, 'Sin ventas en este período.');
}


/* ==========================================================================
   CARGA DEL REPORTE
   ========================================================================== */
async function cargarReporte(dias) {
  document.querySelectorAll('.selector-periodo .btn').forEach(boton =>
    boton.classList.toggle('active', Number(boton.dataset.dias) === dias));
  document.getElementById('texto-periodo').textContent = 'Cargando...';

  const { ok, datos } = await apiFetch(`/reportes/ventas/?dias=${dias}`);
  if (!ok) {
    document.getElementById('texto-periodo').textContent = 'No se pudo cargar el reporte.';
    return;
  }

  const periodo = datos.periodo;
  document.getElementById('texto-periodo').textContent = periodo.desde
    ? `Del ${formatoFechaLarga.format(new Date(periodo.desde))} al ${formatoFechaLarga.format(new Date(periodo.hasta))}`
    : 'Todo el historial de la tienda';

  const hayDemo = [...datos.mejores_clientes, ...datos.ultimas_ventas].some(fila => fila.cliente.startsWith('demo_'));
  document.getElementById('aviso-demo').classList.toggle('d-none', !hayDemo);

  mostrarIndicadores(datos.indicadores);
  if (window.Chart) dibujarGraficos(datos);
  mostrarTablas(datos);
}

document.querySelector('.selector-periodo').addEventListener('click', evento => {
  const boton = evento.target.closest('[data-dias]');
  if (boton) cargarReporte(Number(boton.dataset.dias));
});

if (usuarioVentas) {
  document.addEventListener('DOMContentLoaded', () => cargarReporte(30));
}