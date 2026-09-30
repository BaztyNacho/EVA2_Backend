/* ==========================================================================
   SESION.JS - CIERRE DE SESIÓN POR INACTIVIDAD (clientes y administrador)
   --------------------------------------------------------------------------
   - Tras 5 minutos sin actividad (mouse, clic, teclado, scroll o toque)
     se cierra la sesión. Los visitantes sin cuenta no tienen límite.
   - Al minuto 4 aparece un modal con una cuenta regresiva de 60 segundos
     y dos opciones: "Seguir conectado" (renueva los tokens) o "Cerrar
     sesión".
   - Mientras el usuario está activo, el access token (TTL de 5 minutos
     en settings.py) se renueva solo antes de vencer, así nunca se corta
     una compra a la mitad.
   - La hora de la última actividad se guarda en localStorage, que es
     compartido por todas las pestañas: si el usuario está activo en una,
     las demás no cierran la sesión.
   Requiere api.js (Sesion, renovarToken, cerrarSesion, decodificarToken).
   ========================================================================== */

const INACTIVIDAD_MAXIMA_MS = 5 * 60 * 1000;  // 5 minutos sin actividad
const DURACION_AVISO_MS = 60 * 1000;          // el aviso aparece 1 minuto antes
const RENOVAR_SI_QUEDAN_MS = 60 * 1000;       // renovar el access si le queda menos de 1 minuto
const PAUSA_REGISTRO_MS = 5 * 1000;           // guardar la actividad como máximo cada 5 segundos

let modalSesion = null;
let avisoVisible = false;
let cerrandoSesion = false;
let ultimoRegistro = 0;


/* --------------------------------------------------------------------------
   ACTIVIDAD DEL USUARIO
   Se guarda la hora en localStorage (compartido entre pestañas). Mientras
   el aviso está en pantalla, moverse no cuenta: hay que elegir un botón.
   -------------------------------------------------------------------------- */
function ultimaActividad() {
  return Number(localStorage.getItem(CLAVE_ACTIVIDAD)) || Date.now();
}

function registrarActividad() {
  if (avisoVisible || !Sesion.usuario()) return;
  const ahora = Date.now();
  if (ahora - ultimoRegistro < PAUSA_REGISTRO_MS) return;
  ultimoRegistro = ahora;
  localStorage.setItem(CLAVE_ACTIVIDAD, String(ahora));
}


/* --------------------------------------------------------------------------
   AVISO (modal de Bootstrap)
   -------------------------------------------------------------------------- */
function mostrarAviso(restanteMs) {
  const segundos = Math.max(0, Math.ceil(restanteMs / 1000));
  document.getElementById('cuenta-regresiva-sesion').textContent =
    `${Math.floor(segundos / 60)}:${String(segundos % 60).padStart(2, '0')}`;
  document.getElementById('barra-sesion').style.width = `${(restanteMs / DURACION_AVISO_MS) * 100}%`;

  if (!avisoVisible) {
    avisoVisible = true;
    modalSesion.show();
  }
}

function ocultarAviso() {
  if (!avisoVisible) return;
  avisoVisible = false;
  modalSesion.hide();
}


/* --------------------------------------------------------------------------
   RENOVACIÓN DEL ACCESS TOKEN MIENTRAS HAY ACTIVIDAD
   Si el usuario estuvo activo en el último minuto y al access le queda
   menos de 1 minuto, se renueva en segundo plano con el refresh.
   -------------------------------------------------------------------------- */
function renovarSiHaceFalta(inactivoMs) {
  const access = Sesion.access();
  const datos = access ? decodificarToken(access) : null;
  if (!datos || inactivoMs > 60 * 1000) return;
  const quedaMs = datos.exp * 1000 - Date.now();
  if (quedaMs < RENOVAR_SI_QUEDAN_MS) renovarToken();
}


/* --------------------------------------------------------------------------
   REVISIÓN CADA SEGUNDO
   -------------------------------------------------------------------------- */
async function revisarSesion() {
  if (cerrandoSesion) return;
  if (!Sesion.usuario()) {
    ocultarAviso();
    return;
  }

  const inactivoMs = Date.now() - ultimaActividad();
  const restanteMs = INACTIVIDAD_MAXIMA_MS - inactivoMs;

  if (restanteMs <= 0) {
    cerrandoSesion = true;
    ocultarAviso();
    await cerrarSesion({ motivo: 'inactividad' });
  } else if (restanteMs <= DURACION_AVISO_MS) {
    mostrarAviso(restanteMs);
  } else {
    ocultarAviso();              // otra pestaña pudo extender la sesión
    renovarSiHaceFalta(inactivoMs);
  }
}


/* --------------------------------------------------------------------------
   BOTONES DEL AVISO
   "Seguir conectado": pide tokens nuevos. Si el refresh ya no sirve, la
   sesión se cierra igual.
   -------------------------------------------------------------------------- */
async function seguirConectado(evento) {
  const boton = evento.currentTarget;
  boton.disabled = true;
  const renovado = await renovarToken();
  boton.disabled = false;
  if (renovado) {
    ocultarAviso();
    mostrarToast('Listo, tu sesión sigue activa.', 'success');
  } else {
    cerrandoSesion = true;
    ocultarAviso();
    await cerrarSesion({ motivo: 'inactividad' });
  }
}


/* --------------------------------------------------------------------------
   INICIO
   -------------------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {
  const elementoModal = document.getElementById('modal-sesion');
  if (!elementoModal) return;
  modalSesion = bootstrap.Modal.getOrCreateInstance(elementoModal);

  ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart', 'wheel'].forEach(tipo =>
    window.addEventListener(tipo, registrarActividad, { passive: true }));

  document.getElementById('boton-seguir-conectado').addEventListener('click', seguirConectado);
  document.getElementById('boton-cerrar-sesion-aviso').addEventListener('click', () => {
    cerrandoSesion = true;
    ocultarAviso();
    cerrarSesion();
  });

  // Si en otra pestaña se cerró la sesión, esta pestaña no debe seguir
  // mostrando datos de una sesión que ya no existe:
  // - si fue por inactividad, va al login con el mismo aviso;
  // - si el usuario cerró sesión a mano, se recarga la página.
  window.addEventListener('storage', evento => {
    if (evento.key !== CLAVE_REFRESH || evento.newValue || cerrandoSesion) return;
    cerrandoSesion = true;
    ocultarAviso();
    if (localStorage.getItem(CLAVE_MOTIVO_CIERRE) === 'inactividad') {
      irAlLogin('Tu sesión se cerró por 5 minutos de inactividad. Vuelve a ingresar para continuar.');
    } else {
      window.location.reload();
    }
  });

  revisarSesion();
  setInterval(revisarSesion, 1000);
});
