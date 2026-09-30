/* ==========================================================================
   PANEL.JS - PANEL DE ADMINISTRACIÓN (solo rol ADMINISTRADOR)
   --------------------------------------------------------------------------
   1. Resumen: totales de productos, stock bajo y órdenes por estado.
   2. CRUD de productos:   POST / PUT / DELETE /api/productos/
      (el formulario se envía como FormData para poder incluir la foto)
   3. CRUD de categorías:  POST / PUT / DELETE /api/categorias/
   4. Gestión de órdenes:  GET /api/ordenes/ y PATCH /api/ordenes/{id}/estado/
   Acceso directo: /panel/?editar=<id> abre el formulario de ese producto
   (lo usan los botones "Editar en el panel" de la tienda).
   Todas las peticiones pasan por apiFetch() (api.js), que envía el token
   JWT. Aunque alguien forzara esta página sin ser administrador, la API
   respondería 403 porque los permisos se validan en el servidor.
   ========================================================================== */

const usuarioPanel = requerirSesion('ADMINISTRADOR');

let productos = [];
let categorias = [];
let productoEditando = null;   // id del producto en edición (null = nuevo)
let categoriaEditando = null;  // id de la categoría en edición (null = nueva)

const modalProducto = new bootstrap.Modal('#modal-producto');
const modalCategoria = new bootstrap.Modal('#modal-categoria');
const modalConfirmar = new bootstrap.Modal('#modal-confirmar');
const formatoFechaPanel = new Intl.DateTimeFormat('es-CL', { dateStyle: 'short', timeStyle: 'short' });


/* --------------------------------------------------------------------------
   UTILIDADES
   -------------------------------------------------------------------------- */

/* Modal de confirmación reutilizable. Devuelve una promesa que se resuelve
   en true si el administrador confirma, o false si cierra el modal. */
function confirmar({ titulo, mensaje, textoBoton, claseBoton = 'btn-danger' }) {
  return new Promise(resolve => {
    const elemento = document.getElementById('modal-confirmar');
    const boton = document.getElementById('boton-confirmar');
    document.getElementById('titulo-modal-confirmar').textContent = titulo;
    document.getElementById('mensaje-modal-confirmar').innerHTML = mensaje;
    boton.className = `btn ${claseBoton}`;
    boton.textContent = textoBoton;

    let aceptado = false;
    const alAceptar = () => { aceptado = true; modalConfirmar.hide(); };
    boton.addEventListener('click', alAceptar, { once: true });
    elemento.addEventListener('hidden.bs.modal', () => {
      boton.removeEventListener('click', alAceptar);
      resolve(aceptado);
    }, { once: true });
    modalConfirmar.show();
  });
}

/* Muestra bajo cada campo los errores que devuelve el serializer de DRF
   (formato { campo: ["mensaje"] }). 'prefijo' es 'p-' o 'c-'. */
function mostrarErroresFormulario(formulario, prefijo, errores = {}) {
  formulario.querySelectorAll('.form-control, .form-select').forEach(campo => {
    const nombre = campo.id.replace(prefijo, '');
    const mensaje = errores[nombre];
    campo.classList.toggle('is-invalid', !!mensaje);
    const retroalimentacion = campo.parentElement.querySelector('.invalid-feedback');
    if (retroalimentacion) retroalimentacion.textContent = mensaje ? [].concat(mensaje).join(' ') : '';
  });
}

function textoStock(stock) {
  if (stock === 0) return `<span class="stock-cero">${stock}</span>`;
  if (stock <= 5) return `<span class="stock-bajo">${stock}</span>`;
  return stock;
}


/* --------------------------------------------------------------------------
   1. RESUMEN
   -------------------------------------------------------------------------- */
async function cargarResumen() {
  const [todos, pendientes, pagadas] = await Promise.all([
    apiFetch('/productos/'),
    apiFetch('/ordenes/?estado=PENDIENTE'),
    apiFetch('/ordenes/?estado=PAGADO'),
  ]);
  if (todos.ok) {
    document.getElementById('resumen-productos').textContent = todos.datos.length;
    document.getElementById('resumen-stock-bajo').textContent = todos.datos.filter(p => p.stock <= 5).length;
  }
  if (pendientes.ok) document.getElementById('resumen-pendientes').textContent = pendientes.datos.length;
  if (pagadas.ok) document.getElementById('resumen-por-entregar').textContent = pagadas.datos.length;
}


/* --------------------------------------------------------------------------
   2. PRODUCTOS
   -------------------------------------------------------------------------- */
async function cargarProductosPanel() {
  const busqueda = document.getElementById('busqueda-productos').value.trim();
  const query = busqueda ? `?search=${encodeURIComponent(busqueda)}` : '';
  const { ok, datos } = await apiFetch(`/productos/${query}`);
  const tabla = document.getElementById('tabla-productos');
  if (!ok) {
    tabla.innerHTML = '<tr><td colspan="8" class="text-danger">No se pudieron cargar los productos.</td></tr>';
    return;
  }
  productos = datos;
  if (!productos.length) {
    tabla.innerHTML = `<tr><td colspan="8" class="text-muted text-center py-4">${busqueda ? 'Ningún producto coincide con la búsqueda.' : 'Aún no hay productos. Crea el primero.'}</td></tr>`;
    return;
  }
  tabla.innerHTML = productos.map(producto => `
    <tr>
      <td><div class="miniatura-panel">${imagenProducto(producto)}</div></td>
      <td><a href="/producto/${producto.id}/" class="fw-semibold">${escaparHTML(producto.nombre)}</a></td>
      <td>${escaparHTML(producto.marca)}</td>
      <td><span class="sku">${escaparHTML(producto.sku)}</span></td>
      <td>${escaparHTML(producto.categoria_nombre)}</td>
      <td class="text-end">${precioCLP(producto.precio)}</td>
      <td class="text-end">${textoStock(producto.stock)}</td>
      <td class="text-end text-nowrap">
        <button class="btn btn-sm btn-outline-secondary" data-editar-producto="${producto.id}" aria-label="Editar ${escaparHTML(producto.nombre)}"><i class="bi bi-pencil"></i></button>
        <button class="btn btn-sm btn-outline-danger" data-eliminar-producto="${producto.id}" aria-label="Eliminar ${escaparHTML(producto.nombre)}"><i class="bi bi-trash3"></i></button>
      </td>
    </tr>`).join('');
}

/* Muestra en el recuadro de vista previa una foto (URL) o el ícono vacío. */
function mostrarVistaPrevia(url) {
  document.getElementById('vista-previa-imagen').innerHTML = url
    ? `<img src="${escaparHTML(url)}" alt="Vista previa de la imagen">`
    : '<i class="bi bi-image" aria-hidden="true"></i>';
}

/* Al elegir un archivo se muestra de inmediato, antes de guardarlo.
   URL.createObjectURL crea una dirección temporal al archivo local. */
document.getElementById('p-imagen').addEventListener('change', evento => {
  const archivo = evento.target.files[0];
  if (archivo) {
    mostrarVistaPrevia(URL.createObjectURL(archivo));
    document.getElementById('p-quitar_imagen').checked = false;
  }
});

/* Abre el modal vacío (nuevo) o con los datos del producto (editar). */
function abrirModalProducto(producto = null) {
  const formulario = document.getElementById('formulario-producto');
  formulario.reset();
  mostrarErroresFormulario(formulario, 'p-');
  document.getElementById('error-producto').classList.add('d-none');
  productoEditando = producto ? producto.id : null;
  document.getElementById('titulo-modal-producto').textContent = producto ? 'Editar producto' : 'Nuevo producto';

  document.getElementById('p-categoria').innerHTML =
    '<option value="">Selecciona una categoría</option>' +
    categorias.map(c => `<option value="${c.id}">${escaparHTML(c.nombre)}</option>`).join('');

  if (producto) {
    ['nombre', 'marca', 'sku', 'precio', 'stock', 'categoria', 'descripcion'].forEach(campo => {
      document.getElementById(`p-${campo}`).value = producto[campo] ?? '';
    });
  }

  // Foto: vista previa de la actual y opción "quitar" solo si ya tiene una
  mostrarVistaPrevia(producto && producto.imagen);
  document.getElementById('grupo-quitar-imagen').classList.toggle('d-none', !(producto && producto.imagen));
  modalProducto.show();
}

/* ------------------------------------------------------------------
   Guardar: POST si es nuevo, PUT si se está editando.
   Se usa FormData (multipart/form-data) en vez de JSON porque JSON no
   puede transportar archivos. La foto solo se envía si se eligió una;
   si no, el producto conserva la que ya tenía.
   ------------------------------------------------------------------ */
document.getElementById('formulario-producto').addEventListener('submit', async evento => {
  evento.preventDefault();
  const formulario = evento.currentTarget;
  const valor = campo => document.getElementById(`p-${campo}`).value.trim();
  const archivo = document.getElementById('p-imagen').files[0];

  // Validación previa en el navegador (el backend la vuelve a validar)
  if (archivo && archivo.size > 2 * 1024 * 1024) {
    mostrarErroresFormulario(formulario, 'p-', { imagen: ['La imagen no puede pesar más de 2 MB.'] });
    return;
  }

  const datosProducto = new FormData();
  ['nombre', 'marca', 'sku', 'precio', 'stock', 'categoria', 'descripcion'].forEach(campo => {
    datosProducto.append(campo, valor(campo));
  });
  if (archivo) datosProducto.append('imagen', archivo);
  if (document.getElementById('p-quitar_imagen').checked) datosProducto.append('quitar_imagen', 'true');

  const ruta = productoEditando ? `/productos/${productoEditando}/` : '/productos/';
  const metodo = productoEditando ? 'PUT' : 'POST';
  const { ok, datos } = await apiFetch(ruta, { method: metodo, body: datosProducto });

  if (!ok) {
    mostrarErroresFormulario(formulario, 'p-', datos || {});
    if (datos && datos.detail) {
      const alerta = document.getElementById('error-producto');
      alerta.textContent = datos.detail;
      alerta.classList.remove('d-none');
    }
    return;
  }
  modalProducto.hide();
  mostrarToast(productoEditando ? 'Producto actualizado.' : 'Producto creado.', 'success');
  await Promise.all([cargarProductosPanel(), cargarCategoriasPanel(), cargarResumen()]);
});

async function eliminarProducto(producto) {
  const aceptado = await confirmar({
    titulo: 'Eliminar producto',
    mensaje: `Se eliminará <strong>${escaparHTML(producto.nombre)}</strong> del catálogo y de los carros donde esté.
              Las órdenes ya realizadas conservan su historial.`,
    textoBoton: 'Eliminar producto',
  });
  if (!aceptado) return;
  const { ok, datos } = await apiFetch(`/productos/${producto.id}/`, { method: 'DELETE' });
  if (ok) {
    mostrarToast('Producto eliminado.', 'success');
    await Promise.all([cargarProductosPanel(), cargarCategoriasPanel(), cargarResumen()]);
  } else {
    mostrarToast((datos && datos.detail) || 'No se pudo eliminar el producto.', 'danger');
  }
}

document.getElementById('tabla-productos').addEventListener('click', evento => {
  const editar = evento.target.closest('[data-editar-producto]');
  const eliminar = evento.target.closest('[data-eliminar-producto]');
  if (editar) abrirModalProducto(productos.find(p => p.id === Number(editar.dataset.editarProducto)));
  if (eliminar) eliminarProducto(productos.find(p => p.id === Number(eliminar.dataset.eliminarProducto)));
});
document.getElementById('nuevo-producto').addEventListener('click', () => abrirModalProducto());
document.getElementById('formulario-busqueda-productos').addEventListener('submit', evento => {
  evento.preventDefault();
  cargarProductosPanel();
});


/* --------------------------------------------------------------------------
   3. CATEGORÍAS
   -------------------------------------------------------------------------- */
async function cargarCategoriasPanel() {
  const { ok, datos } = await apiFetch('/categorias/');
  const tabla = document.getElementById('tabla-categorias');
  if (!ok) {
    tabla.innerHTML = '<tr><td colspan="4" class="text-danger">No se pudieron cargar las categorías.</td></tr>';
    return;
  }
  categorias = datos;
  if (!categorias.length) {
    tabla.innerHTML = '<tr><td colspan="4" class="text-muted text-center py-4">Aún no hay categorías. Crea la primera.</td></tr>';
    return;
  }
  tabla.innerHTML = categorias.map(categoria => `
    <tr>
      <td class="fw-semibold">${escaparHTML(categoria.nombre)}</td>
      <td class="text-muted">${escaparHTML(categoria.descripcion) || '-'}</td>
      <td class="text-end">${categoria.total_productos}</td>
      <td class="text-end text-nowrap">
        <button class="btn btn-sm btn-outline-secondary" data-editar-categoria="${categoria.id}" aria-label="Editar ${escaparHTML(categoria.nombre)}"><i class="bi bi-pencil"></i></button>
        <button class="btn btn-sm btn-outline-danger" data-eliminar-categoria="${categoria.id}" aria-label="Eliminar ${escaparHTML(categoria.nombre)}"><i class="bi bi-trash3"></i></button>
      </td>
    </tr>`).join('');
}

function abrirModalCategoria(categoria = null) {
  const formulario = document.getElementById('formulario-categoria');
  formulario.reset();
  mostrarErroresFormulario(formulario, 'c-');
  categoriaEditando = categoria ? categoria.id : null;
  document.getElementById('titulo-modal-categoria').textContent = categoria ? 'Editar categoría' : 'Nueva categoría';
  if (categoria) {
    document.getElementById('c-nombre').value = categoria.nombre;
    document.getElementById('c-descripcion').value = categoria.descripcion;
  }
  modalCategoria.show();
}

document.getElementById('formulario-categoria').addEventListener('submit', async evento => {
  evento.preventDefault();
  const formulario = evento.currentTarget;
  const datosCategoria = {
    nombre: document.getElementById('c-nombre').value.trim(),
    descripcion: document.getElementById('c-descripcion').value.trim(),
  };
  const ruta = categoriaEditando ? `/categorias/${categoriaEditando}/` : '/categorias/';
  const metodo = categoriaEditando ? 'PUT' : 'POST';
  const { ok, datos } = await apiFetch(ruta, { method: metodo, body: datosCategoria });
  if (!ok) {
    mostrarErroresFormulario(formulario, 'c-', datos || {});
    return;
  }
  modalCategoria.hide();
  mostrarToast(categoriaEditando ? 'Categoría actualizada.' : 'Categoría creada.', 'success');
  await Promise.all([cargarCategoriasPanel(), cargarProductosPanel(), cargarMenuCategorias()]);
});

/* Si la categoría tiene productos, la API responde 400 (on_delete=PROTECT)
   y se muestra ese mensaje. */
async function eliminarCategoria(categoria) {
  const aceptado = await confirmar({
    titulo: 'Eliminar categoría',
    mensaje: `Se eliminará la categoría <strong>${escaparHTML(categoria.nombre)}</strong>.`,
    textoBoton: 'Eliminar categoría',
  });
  if (!aceptado) return;
  const { ok, datos } = await apiFetch(`/categorias/${categoria.id}/`, { method: 'DELETE' });
  if (ok) {
    mostrarToast('Categoría eliminada.', 'success');
    await Promise.all([cargarCategoriasPanel(), cargarMenuCategorias()]);
  } else {
    mostrarToast((datos && datos.detail) || 'No se pudo eliminar la categoría.', 'danger');
  }
}

document.getElementById('tabla-categorias').addEventListener('click', evento => {
  const editar = evento.target.closest('[data-editar-categoria]');
  const eliminar = evento.target.closest('[data-eliminar-categoria]');
  if (editar) abrirModalCategoria(categorias.find(c => c.id === Number(editar.dataset.editarCategoria)));
  if (eliminar) eliminarCategoria(categorias.find(c => c.id === Number(eliminar.dataset.eliminarCategoria)));
});
document.getElementById('nueva-categoria').addEventListener('click', () => abrirModalCategoria());


/* --------------------------------------------------------------------------
   4. ÓRDENES
   ACCIONES replica la máquina de estados del modelo Orden
   (TRANSICIONES_VALIDAS): cada estado muestra solo los botones de los
   cambios permitidos, con una explicación del efecto sobre el stock.
   La validación real la hace igual el backend (services.py).
   -------------------------------------------------------------------------- */
const ACCIONES = {
  PENDIENTE: [
    { estado: 'PAGADO', texto: 'Marcar pagada', clase: 'btn-placa',
      efecto: 'Se verificará el stock de todos los productos y se descontará. Si alguno no alcanza, el cambio se rechaza.' },
    { estado: 'CANCELADO', texto: 'Cancelar', clase: 'btn-outline-danger',
      efecto: 'La orden nunca descontó stock, así que no se repone nada.' },
  ],
  PAGADO: [
    { estado: 'ENTREGADO', texto: 'Marcar entregada', clase: 'btn-success',
      efecto: 'El stock ya se descontó al pagar; solo cambia el estado.' },
    { estado: 'CANCELADO', texto: 'Cancelar', clase: 'btn-outline-danger',
      efecto: 'Se repondrá al catálogo el stock que descontó esta orden.' },
  ],
};

async function cargarOrdenesPanel() {
  const estado = document.getElementById('filtro-estado').value;
  const usuario = document.getElementById('filtro-usuario').value.trim();
  const parametros = new URLSearchParams();
  if (estado) parametros.set('estado', estado);
  if (usuario) parametros.set('usuario', usuario);
  const query = parametros.toString() ? `?${parametros}` : '';

  const { ok, datos } = await apiFetch(`/ordenes/${query}`);
  const tabla = document.getElementById('tabla-ordenes');
  if (!ok) {
    tabla.innerHTML = '<tr><td colspan="6" class="text-danger">No se pudieron cargar las órdenes.</td></tr>';
    return;
  }
  if (!datos.length) {
    tabla.innerHTML = '<tr><td colspan="6" class="text-muted text-center py-4">No hay órdenes con estos filtros.</td></tr>';
    return;
  }

  tabla.innerHTML = datos.map(orden => `
    <tr>
      <td>
        <button class="btn btn-link p-0 codigo-orden" type="button" data-bs-toggle="collapse" data-bs-target="#items-orden-${orden.id}"
                aria-expanded="false" aria-controls="items-orden-${orden.id}" title="Ver productos">
          #${orden.codigo.slice(0, 8).toUpperCase()}
        </button>
      </td>
      <td>${escaparHTML(orden.usuario)}</td>
      <td class="text-nowrap">${formatoFechaPanel.format(new Date(orden.fecha_creacion))}</td>
      <td class="text-end">${precioCLP(orden.total)}</td>
      <td><span class="badge badge-estado-${orden.estado}">${escaparHTML(orden.estado_display)}</span></td>
      <td class="text-end text-nowrap">
        ${(ACCIONES[orden.estado] || []).map(accion => `
          <button class="btn btn-sm ${accion.clase}" type="button" data-orden="${orden.id}" data-actual="${orden.estado}"
                  data-estado="${accion.estado}" data-codigo="${orden.codigo.slice(0, 8).toUpperCase()}">${accion.texto}</button>`).join(' ')
          || '<span class="text-muted small">Sin acciones</span>'}
      </td>
    </tr>
    <tr class="collapse fila-items" id="items-orden-${orden.id}">
      <td colspan="6">
        <ul class="mb-0 small">
          ${orden.items.map(item => `<li>${item.cantidad} x ${escaparHTML(item.nombre_producto)} (${precioCLP(item.precio_unitario)} c/u)</li>`).join('')}
        </ul>
      </td>
    </tr>`).join('');
}

/* PATCH /api/ordenes/{id}/estado/  con confirmación previa */
async function cambiarEstadoOrden(boton) {
  const { orden, actual, estado, codigo } = boton.dataset;
  const accion = ACCIONES[actual].find(a => a.estado === estado);

  const aceptado = await confirmar({
    titulo: `${accion.texto}: orden #${codigo}`,
    mensaje: `<p class="mb-0">${accion.efecto}</p>`,
    textoBoton: accion.texto,
    claseBoton: estado === 'CANCELADO' ? 'btn-danger' : accion.clase,
  });
  if (!aceptado) return;

  const mensaje = document.getElementById('mensaje-ordenes');
  const { ok, status, datos } = await apiFetch(`/ordenes/${orden}/estado/`, { method: 'PATCH', body: { estado } });

  if (ok) {
    mensaje.innerHTML = '';
    mostrarToast(`Orden #${codigo} actualizada a ${datos.estado_display}.`, 'success');
  } else if (status === 409) {
    const detalle = datos.productos.map(p => p.motivo
      ? `<li><strong>${escaparHTML(p.producto)}</strong>: ${escaparHTML(p.motivo)}</li>`
      : `<li><strong>${escaparHTML(p.producto)}</strong>: se piden ${p.solicitado}, hay ${p.disponible}.</li>`).join('');
    mensaje.innerHTML = `
      <div class="alert alert-danger alert-dismissible" role="alert">
        <p class="fw-semibold mb-1">No se pudo marcar como pagada la orden #${escaparHTML(codigo)}: stock insuficiente.</p>
        <ul class="mb-1">${detalle}</ul>
        <p class="small mb-0">No se modificó el stock. Puedes cancelar la orden o reponer inventario.</p>
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Cerrar"></button>
      </div>`;
  } else {
    mostrarToast((datos && datos.detail) || 'No se pudo cambiar el estado.', 'danger');
  }
  await Promise.all([cargarOrdenesPanel(), cargarProductosPanel(), cargarResumen()]);
}

document.getElementById('tabla-ordenes').addEventListener('click', evento => {
  const boton = evento.target.closest('[data-estado]');
  if (boton) cambiarEstadoOrden(boton);
});
document.getElementById('formulario-filtro-ordenes').addEventListener('submit', evento => {
  evento.preventDefault();
  cargarOrdenesPanel();
});


/* --------------------------------------------------------------------------
   ACCESO DIRECTO A EDITAR: /panel/?editar=<id>
   Después de cargar los productos, si la URL trae ?editar, se abre el
   formulario de ese producto. Luego se quita el parámetro de la URL
   (history.replaceState) para que al recargar no se vuelva a abrir.
   -------------------------------------------------------------------------- */
function abrirEdicionDesdeUrl() {
  const parametros = new URLSearchParams(window.location.search);
  const id = Number(parametros.get('editar'));
  if (!id) return;
  history.replaceState(null, '', window.location.pathname);
  const producto = productos.find(p => p.id === id);
  if (producto) {
    abrirModalProducto(producto);
  } else {
    mostrarToast('El producto que intentas editar ya no existe.', 'warning');
  }
}


/* --------------------------------------------------------------------------
   INICIO
   Primero las categorías (el formulario de producto las necesita) y los
   productos (para el acceso directo ?editar); el resto en paralelo.
   -------------------------------------------------------------------------- */
if (usuarioPanel) {
  document.addEventListener('DOMContentLoaded', async () => {
    await cargarCategoriasPanel();
    cargarOrdenesPanel();
    cargarResumen();
    await cargarProductosPanel();
    abrirEdicionDesdeUrl();
  });
}