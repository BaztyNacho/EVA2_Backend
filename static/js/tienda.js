/* ==========================================================================
   TIENDA.JS - COMPONENTES DE INTERFAZ COMPARTIDOS POR TODAS LAS PÁGINAS
   --------------------------------------------------------------------------
   - Formato de precios en pesos chilenos.
   - Escape de HTML (seguridad contra XSS).
   - Imagen de producto (foto o ícono) y tarjetas de producto reutilizables.
   - Menú de cuenta según el rol, menú de categorías y contador del carro.
   - Modo administrador: barra superior e insignia ADMIN.
   - Mini-carro lateral: se abre al presionar el ícono del carro.
   - Botón "Agregar al carro" y notificaciones (toasts).
   Requiere que api.js esté cargado antes.
   Las funciones de la cabecera revisan primero que su elemento exista,
   porque el login y el registro usan una cabecera mínima sin menú,
   sin cuenta y sin carro.
   ========================================================================== */


/* --------------------------------------------------------------------------
   UTILIDADES
   -------------------------------------------------------------------------- */
const formatoCLP = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP' });

function precioCLP(valor) {
  return formatoCLP.format(valor);
}

/* Escapa caracteres especiales antes de insertar texto con innerHTML.
   Así, si un nombre de producto contuviera "<script>", se mostraría como
   texto y no se ejecutaría (protección contra XSS). */
function escaparHTML(texto) {
  const div = document.createElement('div');
  div.textContent = texto ?? '';
  return div.innerHTML;
}

/* Elige un ícono de Bootstrap Icons según el nombre de la categoría.
   Se usa cuando el producto todavía no tiene fotografía. */
function iconoCategoria(nombreCategoria = '') {
  const nombre = nombreCategoria.toLowerCase();
  if (nombre.includes('procesador') || nombre.includes('cpu')) return 'bi-cpu';
  if (nombre.includes('video') || nombre.includes('gpu')) return 'bi-gpu-card';
  if (nombre.includes('ram') || nombre.includes('memoria')) return 'bi-memory';
  if (nombre.includes('almacenamiento') || nombre.includes('ssd') || nombre.includes('disco')) return 'bi-device-ssd';
  if (nombre.includes('placa') || nombre.includes('madre')) return 'bi-motherboard';
  if (nombre.includes('fuente') || nombre.includes('poder')) return 'bi-lightning-charge';
  return 'bi-pc-display';
}

/* Contenido visual de un producto: su foto si la tiene, o el ícono de su
   categoría si no. La foto usa loading="lazy" (se descarga cuando está
   por aparecer en pantalla) y se ajusta con object-fit: contain en CSS. */
function imagenProducto(producto) {
  if (producto.imagen) {
    return `<img src="${escaparHTML(producto.imagen)}" alt="${escaparHTML(producto.nombre)}" loading="lazy">`;
  }
  return `<i class="bi ${iconoCategoria(producto.categoria_nombre)}" aria-hidden="true"></i>`;
}


/* --------------------------------------------------------------------------
   NOTIFICACIONES (Toast de Bootstrap)
   -------------------------------------------------------------------------- */
function mostrarToast(mensaje, tipo = 'success') {
  const colores = { success: 'text-bg-success', warning: 'text-bg-warning', danger: 'text-bg-danger', info: 'text-bg-dark' };
  const contenedor = document.getElementById('contenedor-toasts');
  const elemento = document.createElement('div');
  elemento.className = `toast align-items-center border-0 ${colores[tipo] || colores.info}`;
  elemento.setAttribute('role', 'status');
  elemento.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">${escaparHTML(mensaje)}</div>
      <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Cerrar"></button>
    </div>`;
  contenedor.appendChild(elemento);
  const toast = new bootstrap.Toast(elemento, { delay: 3500 });
  elemento.addEventListener('hidden.bs.toast', () => elemento.remove());
  toast.show();
}


/* --------------------------------------------------------------------------
   TARJETA DE PRODUCTO (se usa en la portada, el catálogo y el detalle)
   Retorna el HTML de una tarjeta. Todo texto que viene de la API pasa por
   escaparHTML. El botón inferior depende del rol:
   - Visitante o cliente: "Agregar al carro".
   - Administrador (no compra, según la matriz de permisos): "Editar en
     el panel", que abre /panel/?editar=<id> con el formulario listo.
   'columnas' define el ancho de la tarjeta en la grilla de Bootstrap. Si
   la función se usa directo en .map(), el segundo argumento es el índice
   (un número), por eso se valida que sea texto.
   -------------------------------------------------------------------------- */
const COLUMNAS_POR_DEFECTO = 'col-6 col-md-4 col-lg-3';

function tarjetaProducto(producto, columnas = COLUMNAS_POR_DEFECTO) {
  if (typeof columnas !== 'string') columnas = COLUMNAS_POR_DEFECTO;
  const sinStock = producto.stock <= 0;
  const esAdministrador = Sesion.esAdministrador();
  const estadoStock = sinStock
    ? '<span class="badge text-bg-secondary">Sin stock</span>'
    : producto.stock <= 5
      ? `<span class="badge text-bg-warning">Últimas ${producto.stock} unidades</span>`
      : `<span class="badge text-bg-success">Stock: ${producto.stock}</span>`;

  return `
    <div class="${columnas}">
      <article class="tarjeta-producto">
        <a class="imagen-producto ${producto.imagen ? 'con-imagen' : ''}" href="/producto/${producto.id}/" aria-label="Ver ${escaparHTML(producto.nombre)}">
          ${imagenProducto(producto)}
        </a>
        <div class="cuerpo-producto">
          <span class="marca-producto">${escaparHTML(producto.marca)}</span>
          <a class="nombre-producto" href="/producto/${producto.id}/">${escaparHTML(producto.nombre)}</a>
          <span class="sku mb-2">SKU ${escaparHTML(producto.sku)}</span>
          <div class="mb-2">${estadoStock}</div>
          <div class="precio mb-2">${precioCLP(producto.precio)}</div>
          ${esAdministrador ? `
            <a class="btn btn-placa w-100" href="/panel/?editar=${producto.id}">
              <i class="bi bi-pencil-square me-1"></i>Editar<span class="d-none d-sm-inline"> en el panel</span>
            </a>` : `
            <button class="btn btn-cobre w-100" data-agregar-carro="${producto.id}" ${sinStock ? 'disabled' : ''}>
              <i class="bi bi-cart-plus me-1"></i>${sinStock ? 'Sin stock' : 'Agregar<span class="d-none d-sm-inline"> al carro</span>'}
            </button>`}
        </div>
      </article>
    </div>`;
}


/* --------------------------------------------------------------------------
   AGREGAR AL CARRO
   - Visitante sin sesión: se le envía al login.
   - Cliente: POST /api/carro/ y se actualiza el contador.
   El stock no se descuenta aquí (solo al pagar la orden).
   -------------------------------------------------------------------------- */
async function agregarAlCarro(productoId, cantidad = 1, boton = null) {
  if (!Sesion.usuario()) {
    irAlLogin('Inicia sesión para agregar productos a tu carro.');
    return;
  }
  if (!Sesion.esCliente()) {
    mostrarToast('Las cuentas de administrador no pueden comprar.', 'warning');
    return;
  }
  if (boton) boton.disabled = true;
  const { ok, datos } = await apiFetch('/carro/', { method: 'POST', body: { producto: productoId, cantidad } });
  if (boton) boton.disabled = false;

  if (ok) {
    actualizarContadorCarro(datos.total_unidades);
    mostrarToast('Producto agregado al carro.', 'success');
  } else {
    mostrarToast('No se pudo agregar el producto.', 'danger');
  }
}


/* --------------------------------------------------------------------------
   CABECERA: menú de cuenta, categorías y contador del carro
   -------------------------------------------------------------------------- */
function renderizarCuenta() {
  const zona = document.getElementById('zona-cuenta');
  if (!zona) return;
  const usuario = Sesion.usuario();
  const botonCarro = document.getElementById('boton-carro');

  if (!usuario) {
    zona.innerHTML = `
      <a class="accion-nav" href="/login/">
        <i class="bi bi-person-circle"></i>
        <span class="d-none d-md-inline"><small>Bienvenido</small>Ingresa o regístrate</span>
      </a>`;
    return;
  }

  const esAdmin = usuario.rol === 'ADMINISTRADOR';
  if (botonCarro) botonCarro.classList.toggle('d-none', esAdmin);

  zona.innerHTML = `
    <div class="dropdown">
      <button class="accion-nav dropdown-toggle" data-bs-toggle="dropdown" aria-expanded="false">
        <i class="bi ${esAdmin ? 'bi-person-gear' : 'bi-person-check'}"></i>
        <span class="text-start d-none d-md-inline"><small>${esAdmin ? 'Administrador' : 'Hola'}</small>${escaparHTML(usuario.username)}</span>
      </button>
      <ul class="dropdown-menu dropdown-menu-end">
        ${esAdmin
          ? `<li><a class="dropdown-item" href="/panel/"><i class="bi bi-speedometer2 me-2"></i>Panel de administración</a></li>
             <li><a class="dropdown-item" href="/ventas/"><i class="bi bi-graph-up-arrow me-2"></i>Registro de ventas</a></li>`
          : `<li><a class="dropdown-item" href="/carro/"><i class="bi bi-cart3 me-2"></i>Mi carro</a></li>
             <li><a class="dropdown-item" href="/mis-ordenes/"><i class="bi bi-receipt me-2"></i>Mis órdenes</a></li>`}
        <li><hr class="dropdown-divider"></li>
        <li><button class="dropdown-item" id="boton-cerrar-sesion"><i class="bi bi-box-arrow-right me-2"></i>Cerrar sesión</button></li>
      </ul>
    </div>`;
  document.getElementById('boton-cerrar-sesion').addEventListener('click', cerrarSesion);
}

function actualizarContadorCarro(unidades) {
  const contador = document.getElementById('contador-carro');
  if (!contador) return;
  contador.textContent = unidades;
  contador.classList.toggle('d-none', !unidades);
}

async function cargarContadorCarro() {
  if (!document.getElementById('contador-carro') || !Sesion.esCliente()) return;
  const { ok, datos } = await apiFetch('/carro/');
  if (ok) actualizarContadorCarro(datos.total_unidades);
}

async function cargarMenuCategorias() {
  const menu = document.getElementById('menu-categorias');
  if (!menu) return;
  const { ok, datos } = await apiFetch('/categorias/');
  if (!ok) return;
  menu.innerHTML = '<a href="/catalogo/"><i class="bi bi-grid me-1"></i>Todo el catálogo</a>' +
    datos.map(categoria => `
      <a href="/catalogo/?categoria=${categoria.id}">
        <i class="bi ${iconoCategoria(categoria.nombre)} me-1"></i>${escaparHTML(categoria.nombre)}
      </a>`).join('');
}


/* --------------------------------------------------------------------------
   MODO ADMINISTRADOR
   Si la sesión es de un ADMINISTRADOR, se agrega la clase modo-admin al
   <body>. El CSS (modo-admin.css) usa esa clase para mostrar la barra
   superior y la insignia ADMIN junto al logo.
   Es solo un aviso visual: los permisos reales los aplica la API.
   -------------------------------------------------------------------------- */
function mostrarModoAdministrador() {
  const usuario = Sesion.usuario();
  if (!usuario || usuario.rol !== 'ADMINISTRADOR') return;
  document.body.classList.add('modo-admin');
  const nombre = document.getElementById('barra-admin-usuario');
  if (nombre) nombre.textContent = usuario.username;
}


/* --------------------------------------------------------------------------
   MINI-CARRO LATERAL (Offcanvas de Bootstrap)
   - Se abre al presionar el ícono del carro de la cabecera (solo si la
     sesión es de un CLIENTE y no se está ya en la página /carro/).
   - Pide GET /api/carro/ y dibuja cada producto con su foto, cantidad y
     subtotal, más el subtotal general y los botones "Ir a pagar" (va a
     /carro/) y "Seguir comprando" (cierra el panel).
   - Cada producto se puede quitar con DELETE /api/carro/items/{id}/; la
     respuesta trae el carro actualizado y se vuelve a dibujar.
   -------------------------------------------------------------------------- */
function itemMiniCarro(item) {
  // imagenProducto() espera un producto; se arma con los datos del ítem
  const visual = imagenProducto({ imagen: item.producto_imagen, nombre: item.producto_nombre, categoria_nombre: '' });
  return `
    <div class="item-mini">
      <a class="foto-mini" href="/producto/${item.producto}/" aria-label="Ver ${escaparHTML(item.producto_nombre)}">${visual}</a>
      <div class="flex-grow-1 min-w-0">
        <a class="nombre-producto d-block" href="/producto/${item.producto}/">${escaparHTML(item.producto_nombre)}</a>
        <span class="small text-muted">${item.cantidad} x ${precioCLP(item.precio_unitario)}</span>
      </div>
      <div class="text-end">
        <div class="fw-bold">${precioCLP(item.subtotal)}</div>
        <button class="btn btn-link btn-sm text-danger p-0" type="button" data-quitar-mini="${item.id}"
                aria-label="Quitar ${escaparHTML(item.producto_nombre)} del carro">Quitar</button>
      </div>
    </div>`;
}

function dibujarMiniCarro(carro) {
  const cuerpo = document.getElementById('contenido-mini-carro');
  const pie = document.getElementById('pie-mini-carro');
  actualizarContadorCarro(carro.total_unidades);
  document.getElementById('titulo-mini-carro').innerHTML =
    `<i class="bi bi-cart3 me-2"></i>Tu carro${carro.total_unidades ? ` <span class="fw-normal">(${carro.total_unidades} ${carro.total_unidades === 1 ? 'unidad' : 'unidades'})</span>` : ''}`;

  if (!carro.items.length) {
    pie.classList.add('d-none');
    cuerpo.innerHTML = `
      <div class="text-center py-5">
        <i class="bi bi-cart-x mini-vacio" aria-hidden="true"></i>
        <p class="fw-semibold mt-3 mb-1">Tu carro está vacío</p>
        <p class="text-muted small mb-4">Agrega componentes desde el catálogo.</p>
        <a class="btn btn-cobre" href="/catalogo/">Ir al catálogo</a>
      </div>`;
    return;
  }

  cuerpo.innerHTML = carro.items.map(itemMiniCarro).join('');
  document.getElementById('total-mini-carro').textContent = precioCLP(carro.total);
  pie.classList.remove('d-none');
}

async function abrirMiniCarro() {
  // Se ocultan los avisos visibles para que no tapen los botones del panel
  document.querySelectorAll('#contenedor-toasts .toast').forEach(aviso => bootstrap.Toast.getInstance(aviso)?.hide());
  const cuerpo = document.getElementById('contenido-mini-carro');
  document.getElementById('pie-mini-carro').classList.add('d-none');
  cuerpo.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-secondary" role="status"><span class="visually-hidden">Cargando...</span></div></div>';
  bootstrap.Offcanvas.getOrCreateInstance('#mini-carro').show();

  const { ok, datos } = await apiFetch('/carro/');
  if (ok) dibujarMiniCarro(datos);
  else cuerpo.innerHTML = '<div class="alert alert-danger">No se pudo cargar tu carro.</div>';
}

function activarMiniCarro() {
  const botonCarro = document.getElementById('boton-carro');
  const panel = document.getElementById('mini-carro');
  if (!botonCarro || !panel) return;
  botonCarro.setAttribute('aria-controls', 'mini-carro');

  botonCarro.addEventListener('click', evento => {
    // Comportamiento normal del enlace (ir a /carro/) en estos casos:
    // visitante o administrador, ya en /carro/, o Ctrl/Shift/rueda del mouse.
    const abrirEnOtraPestana = evento.ctrlKey || evento.metaKey || evento.shiftKey || evento.button !== 0;
    if (!Sesion.esCliente() || window.location.pathname === '/carro/' || abrirEnOtraPestana) return;
    evento.preventDefault();
    abrirMiniCarro();
  });

  panel.addEventListener('click', async evento => {
    const boton = evento.target.closest('[data-quitar-mini]');
    if (!boton) return;
    boton.disabled = true;
    const { ok, datos } = await apiFetch(`/carro/items/${boton.dataset.quitarMini}/`, { method: 'DELETE' });
    if (ok) dibujarMiniCarro(datos);
    else boton.disabled = false;
  });
}


/* --------------------------------------------------------------------------
   INICIALIZACIÓN COMÚN (se ejecuta en todas las páginas)
   -------------------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {
  mostrarModoAdministrador();
  renderizarCuenta();
  cargarMenuCategorias();
  cargarContadorCarro();
  activarMiniCarro();

  const aviso = tomarAvisoPendiente();
  if (aviso) mostrarToast(aviso.mensaje, aviso.tipo);

  // Delegación de eventos: un solo listener para todos los botones
  // "Agregar al carro", incluso los que se crean después con JavaScript.
  document.body.addEventListener('click', evento => {
    const boton = evento.target.closest('[data-agregar-carro]');
    if (boton) agregarAlCarro(Number(boton.dataset.agregarCarro), 1, boton);
  });
});