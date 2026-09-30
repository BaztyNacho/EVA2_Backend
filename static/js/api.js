/* ==========================================================================
   API.JS - COMUNICACIÓN CON LA API REST Y MANEJO DE LA SESIÓN JWT
   --------------------------------------------------------------------------
   Todas las páginas de la tienda usan este archivo para hablar con el
   backend. Responsabilidades:
   1. Guardar los tokens (access y refresh) en localStorage después del
      login, y leerlos en cada petición.
   2. Agregar el header "Authorization: Bearer <access>" automáticamente.
   3. Si la API responde 401 porque el access expiró (TTL de 5 min),
      pedir uno nuevo a /api/auth/refresh/ y repetir la petición.
   4. Cerrar sesión enviando el refresh a la blacklist (/api/auth/logout/),
      ya sea porque el usuario lo pide o por inactividad (sesion.js).
   5. Proteger páginas privadas: si no hay sesión, redirigir al login.
   ========================================================================== */

const API_BASE = '/api';
const CLAVE_ACCESS = 'tienda_access';
const CLAVE_REFRESH = 'tienda_refresh';
const CLAVE_AVISO = 'tienda_aviso';
const CLAVE_ACTIVIDAD = 'tienda_ultima_actividad';  // la usa sesion.js
const CLAVE_MOTIVO_CIERRE = 'tienda_motivo_cierre';  // avisa a otras pestañas por qué se cerró


/* --------------------------------------------------------------------------
   DECODIFICAR EL PAYLOAD DE UN JWT
   Un JWT tiene 3 partes separadas por puntos: header.payload.firma.
   El payload está en Base64URL (no encriptado), así que el navegador puede
   leer los claims (username, rol, exp). La FIRMA solo la valida el servidor.
   -------------------------------------------------------------------------- */
function decodificarToken(token) {
  try {
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const texto = decodeURIComponent(
      atob(base64).split('').map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)).join('')
    );
    return JSON.parse(texto);
  } catch (error) {
    return null;
  }
}


/* --------------------------------------------------------------------------
   OBJETO SESION: guardar, leer y borrar los tokens
   La identidad del usuario se lee del REFRESH token, porque dura más
   (10 minutos) y también lleva los claims personalizados. Si el refresh
   ya expiró, la sesión se considera cerrada.
   Al guardar tokens (login o renovación) se registra también la hora de
   la última actividad, que usa el control de inactividad de sesion.js.
   -------------------------------------------------------------------------- */
const Sesion = {
  guardar(access, refresh) {
    localStorage.setItem(CLAVE_ACCESS, access);
    if (refresh) localStorage.setItem(CLAVE_REFRESH, refresh);
    localStorage.setItem(CLAVE_ACTIVIDAD, String(Date.now()));
    localStorage.removeItem(CLAVE_MOTIVO_CIERRE);
  },
  access() { return localStorage.getItem(CLAVE_ACCESS); },
  refresh() { return localStorage.getItem(CLAVE_REFRESH); },
  limpiar() {
    localStorage.removeItem(CLAVE_ACCESS);
    localStorage.removeItem(CLAVE_REFRESH);
    localStorage.removeItem(CLAVE_ACTIVIDAD);
  },
  usuario() {
    const refresh = this.refresh();
    if (!refresh) return null;
    const datos = decodificarToken(refresh);
    if (!datos || datos.exp * 1000 < Date.now()) {
      this.limpiar();
      return null;
    }
    return { id: datos.user_id, username: datos.username, email: datos.email, rol: datos.rol };
  },
  esCliente() { const u = this.usuario(); return !!u && u.rol === 'CLIENTE'; },
  esAdministrador() { const u = this.usuario(); return !!u && u.rol === 'ADMINISTRADOR'; },
};


/* --------------------------------------------------------------------------
   RENOVAR EL ACCESS TOKEN
   Envía el refresh a /api/auth/refresh/. Como en settings.py está activa
   la rotación (ROTATE_REFRESH_TOKENS), la respuesta trae también un
   refresh NUEVO, que reemplaza al anterior.
   La variable 'renovacionEnCurso' evita pedir varios tokens a la vez si
   varias peticiones reciben 401 al mismo tiempo.
   -------------------------------------------------------------------------- */
let renovacionEnCurso = null;

function renovarToken() {
  if (!renovacionEnCurso) {
    renovacionEnCurso = fetch(`${API_BASE}/auth/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: Sesion.refresh() }),
    })
      .then(async respuesta => {
        if (!respuesta.ok) return false;
        const datos = await respuesta.json();
        Sesion.guardar(datos.access, datos.refresh);
        return true;
      })
      .catch(() => false)
      .finally(() => { renovacionEnCurso = null; });
  }
  return renovacionEnCurso;
}


/* --------------------------------------------------------------------------
   APIFETCH: FUNCIÓN ÚNICA PARA LLAMAR A LA API
   Uso: const { ok, status, datos } = await apiFetch('/carro/', { method: 'POST', body: {...} });
   - Convierte el body a JSON y agrega el token automáticamente.
   - Si el body es un FormData (formulario con archivos, como la foto de
     un producto), se envía tal cual: el navegador arma el formato
     multipart/form-data y su Content-Type, por eso no se fija aquí.
   - Ante un 401: intenta renovar el access y repite la petición UNA vez.
     Si no se puede renovar, borra la sesión y reintenta sin token (útil
     en páginas públicas como el catálogo).
   - Si aun así la API exige sesión, redirige al login (salvo que se
     indique redirigir401: false, como en el propio formulario de login).
   -------------------------------------------------------------------------- */
async function apiFetch(ruta, { method = 'GET', body = null, redirigir401 = true } = {}, esReintento = false) {
  const headers = { Accept: 'application/json' };
  const esFormulario = body instanceof FormData;
  if (body !== null && !esFormulario) headers['Content-Type'] = 'application/json';

  const access = Sesion.access();
  if (access) headers.Authorization = `Bearer ${access}`;

  const respuesta = await fetch(`${API_BASE}${ruta}`, {
    method,
    headers,
    body: body === null ? undefined : (esFormulario ? body : JSON.stringify(body)),
  });

  if (respuesta.status === 401 && !esReintento) {
    if (Sesion.refresh() && await renovarToken()) {
      return apiFetch(ruta, { method, body, redirigir401 }, true);
    }
    if (access) {
      Sesion.limpiar();
      return apiFetch(ruta, { method, body, redirigir401 }, true);
    }
  }

  if (respuesta.status === 401 && redirigir401) {
    irAlLogin('Tu sesión expiró. Vuelve a ingresar.');
  }

  let datos = null;
  if (![204, 205].includes(respuesta.status)) {
    try { datos = await respuesta.json(); } catch (error) { datos = null; }
  }
  return { ok: respuesta.ok, status: respuesta.status, datos };
}


/* --------------------------------------------------------------------------
   AVISOS ENTRE PÁGINAS
   Un aviso guardado en sessionStorage se muestra como toast al cargar la
   siguiente página (ej: "Bienvenido" después de redirigir desde el login).
   -------------------------------------------------------------------------- */
function guardarAviso(mensaje, tipo = 'success') {
  sessionStorage.setItem(CLAVE_AVISO, JSON.stringify({ mensaje, tipo }));
}

function tomarAvisoPendiente() {
  const aviso = sessionStorage.getItem(CLAVE_AVISO);
  sessionStorage.removeItem(CLAVE_AVISO);
  return aviso ? JSON.parse(aviso) : null;
}


/* --------------------------------------------------------------------------
   REDIRECCIONES DE SESIÓN
   - irAlLogin(): envía al login recordando la página actual en ?next=,
     para volver a ella después de ingresar.
   - requerirSesion(rol): se llama al inicio de cada página PRIVADA
     (carro, mis órdenes, panel). Sin sesión -> login. Con un rol
     distinto al requerido -> inicio. Las páginas públicas no la usan.
   -------------------------------------------------------------------------- */
function irAlLogin(mensaje) {
  if (mensaje) guardarAviso(mensaje, 'warning');
  const actual = window.location.pathname + window.location.search;
  window.location.href = `/login/?next=${encodeURIComponent(actual)}`;
}

function requerirSesion(rolRequerido = null) {
  const usuario = Sesion.usuario();
  if (!usuario) {
    irAlLogin('Debes iniciar sesión para ver esa página.');
    return null;
  }
  if (rolRequerido && usuario.rol !== rolRequerido) {
    guardarAviso('Tu cuenta no tiene acceso a esa página.', 'warning');
    window.location.href = '/';
    return null;
  }
  return usuario;
}


/* --------------------------------------------------------------------------
   CERRAR LA SESIÓN DEL ADMIN DE DJANGO
   El admin de Django (/admin/) y la documentación usan una sesión propia
   (cookie), distinta del JWT de la tienda. Para no dejarla abierta en el
   navegador, al cerrar sesión en la tienda también se cierra esa sesión
   con POST /admin/logout/. Django exige el token CSRF en los POST: se lee
   de la cookie 'csrftoken' y se envía en el header X-CSRFToken.
   -------------------------------------------------------------------------- */
function leerCookie(nombre) {
  const cookie = document.cookie.split('; ').find(fila => fila.startsWith(`${nombre}=`));
  return cookie ? decodeURIComponent(cookie.split('=')[1]) : null;
}

async function cerrarSesionAdminDjango() {
  const tokenCsrf = leerCookie('csrftoken');
  if (!tokenCsrf) return;
  try {
    await fetch('/admin/logout/', {
      method: 'POST',
      headers: { 'X-CSRFToken': tokenCsrf },
      credentials: 'same-origin',
    });
  } catch (error) {
    // Si falla, la sesión igual vence sola por inactividad (5 minutos).
  }
}


/* --------------------------------------------------------------------------
   CERRAR SESIÓN
   Envía el refresh a la blacklist y borra los tokens del navegador.
   Si la cuenta es de administrador, cierra también la sesión del admin de
   Django. El carro NO se borra: sigue guardado en PostgreSQL.
   motivo:
   - 'manual' (por defecto): el usuario lo pidió -> vuelve al inicio.
   - 'inactividad': lo cerró sesion.js -> va al login recordando la
     página actual (?next=), para volver a ella al ingresar.
   El motivo se deja en localStorage antes de borrar los tokens, para que
   las otras pestañas abiertas sepan por qué se cerró (ver sesion.js).
   -------------------------------------------------------------------------- */
async function cerrarSesion({ motivo = 'manual' } = {}) {
  const refresh = Sesion.refresh();
  const eraAdministrador = Sesion.esAdministrador();
  if (refresh) {
    await apiFetch('/auth/logout/', { method: 'POST', body: { refresh }, redirigir401: false });
  }
  if (eraAdministrador) await cerrarSesionAdminDjango();
  localStorage.setItem(CLAVE_MOTIVO_CIERRE, motivo);
  Sesion.limpiar();

  if (motivo === 'inactividad') {
    irAlLogin('Tu sesión se cerró por 5 minutos de inactividad. Vuelve a ingresar para continuar.');
    return;
  }
  guardarAviso('Cerraste sesión. Tu carro queda guardado para la próxima vez.', 'success');
  window.location.href = '/';
}