# Tienda de Hardware y Componentes PC

**EVA 2 · Desarrollo Backend**
**Alumno:** Bastian Ignacio Sandoval Reyes · **Sección:** AP-N4-C2 · **Año:** 2026

E-commerce de componentes informáticos construido con **Django REST Framework** y
**PostgreSQL**. Incluye una API REST con autenticación **JWT** por roles, carro de
compras persistente, control transaccional de stock, filtros con django-filter,
documentación Swagger/OpenAPI y una tienda web (Bootstrap 5) que consume la propia API.

## Tecnologías

- Python 3 · Django · Django REST Framework
- PostgreSQL (driver psycopg)
- djangorestframework-simplejwt (access, refresh, rotación y blacklist)
- django-filter · drf-spectacular (Swagger / OpenAPI)
- Pillow (fotos de productos) · python-decouple (variables de entorno)
- Bootstrap 5, Bootstrap Icons y Chart.js (interfaz)

## Instalación

Requisitos: Python 3, PostgreSQL y Git.

1. **Clonar el repositorio** y entrar a la carpeta:
```bash
   git clone <url-del-repositorio>
   cd <carpeta-del-proyecto>
```
2. **Crear y activar el entorno virtual:**
```bash
   python -m venv venv
   venv\Scripts\activate
```
   En PowerShell, si aparece un error de ejecución de scripts, ejecutar antes
   `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
3. **Instalar las dependencias:**
```bash
   pip install -r requirements.txt
```
4. **Crear la base de datos** en PostgreSQL (por ejemplo, desde pgAdmin) con el
   nombre `tienda_hardware_db`.
5. **Crear el archivo `.env`:** copiar `.env.example` como `.env` y completar
   `SECRET_KEY` y `DB_PASSWORD`. Para generar una SECRET_KEY:
```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
6. **Crear las tablas y cargar el catálogo** (6 categorías y 48 productos con sus fotos):
```bash
   python manage.py migrate
   python manage.py importar_datos
```
7. **Crear la cuenta de administrador.** Queda automáticamente con rol ADMINISTRADOR
   y acceso al panel, al registro de ventas, a Swagger y al admin de Django:
```bash
   python manage.py createsuperuser
```
8. **Levantar el servidor** y abrir `http://127.0.0.1:8000/`:
```bash
   python manage.py runserver
```
9. **Cuenta de cliente:** registrarse desde `http://127.0.0.1:8000/registro/` para
   probar el carro, el checkout y el pago.
10. **(Opcional) Ventas de demostración** para ver el dashboard `/ventas/` con datos.
    Crea clientes `demo_cliente_1` a `demo_cliente_8` (clave `DemoTienda2026`) y
    70 órdenes en los últimos 90 días, sin alterar el stock:
```bash
    python manage.py generar_ventas_demo
```

## Páginas de la tienda

| Ruta | Descripción | Acceso |
|---|---|---|
| `/` | Portada con carrusel, categorías y productos recientes | Público |
| `/catalogo/` | Catálogo con filtros (categoría, marca, precio, stock, búsqueda y orden) | Público |
| `/producto/<id>/` | Detalle de producto | Público |
| `/login/` · `/registro/` | Inicio de sesión y registro | Público |
| `/carro/` | Carro de compras y checkout (además, mini-carro lateral desde la cabecera) | Cliente |
| `/mis-ordenes/` | Historial de órdenes y pago | Cliente |
| `/panel/` | CRUD de productos (con fotos) y categorías, y gestión de estados de órdenes | Administrador |
| `/ventas/` | Registro de ventas: indicadores, gráficos y tablas | Administrador |
| `/api/docs/` | Documentación Swagger / OpenAPI | Superusuario |
| `/admin/` | Admin de Django | Superusuario |

## Endpoints de la API

| Método y ruta | Descripción | Acceso |
|---|---|---|
| `POST /api/auth/login/` · `POST /api/auth/refresh/` | Tokens JWT (access y refresh) | Público |
| `POST /api/auth/registro/` | Crear cuenta de cliente | Público |
| `GET /api/auth/perfil/` · `POST /api/auth/logout/` | Perfil y cierre de sesión (blacklist) | Autenticado |
| `GET /api/productos/` · `GET /api/categorias/` | Catálogo con filtros | Público |
| `POST/PUT/PATCH/DELETE /api/productos/` y `/api/categorias/` | Gestión de inventario | Administrador |
| `GET/POST/DELETE /api/carro/` · `PATCH/DELETE /api/carro/items/{id}/` | Carro persistente | Cliente |
| `POST /api/ordenes/checkout/` | Convertir el carro en una orden | Cliente |
| `POST /api/ordenes/{id}/pagar/` | Pagar una orden (descuenta stock) | Cliente |
| `GET /api/mis-ordenes/` | Historial del cliente | Cliente |
| `GET /api/ordenes/` · `PATCH /api/ordenes/{id}/estado/` | Gestión de órdenes | Administrador |
| `GET /api/reportes/ventas/?dias=30` | Reporte del dashboard de ventas | Administrador |

El rol viaja como claim (`rol`) dentro del token JWT. Los usuarios creados con
`createsuperuser` quedan como ADMINISTRADOR; los registrados en la tienda, como CLIENTE.

## Reglas de negocio

- **Carro persistente:** relación 1 a 1 con el usuario, guardado en PostgreSQL; se
  conserva al cerrar sesión o al entrar desde otro dispositivo. Un producto repetido
  suma cantidad en vez de duplicarse.
- **Checkout:** crea una orden PENDIENTE y congela nombre, SKU y precio de cada producto.
- **Stock:** se descuenta solo cuando la orden pasa a PAGADO, dentro de una transacción
  atómica (`transaction.atomic` + `select_for_update`). Si un producto no alcanza, el
  pago se rechaza completo (409) y la orden sigue PENDIENTE. Si una orden PAGADA se
  cancela, el stock se repone.
- **Estados:** PENDIENTE → PAGADO → ENTREGADO, o CANCELADO desde PENDIENTE o PAGADO.

## Seguridad

- **JWT:** access token de 5 minutos (TTL) y refresh de 10 minutos, con rotación y blacklist.
- **Inactividad:** la tienda cierra la sesión tras 5 minutos sin actividad, con un aviso
  y cuenta regresiva desde el minuto 4.
- **Admin de Django y Swagger:** solo para el superusuario. La sesión de Django vence
  tras 5 minutos de inactividad y al cerrar el navegador. La documentación se puede
  hacer pública con `DOCS_SOLO_ADMIN=False` en el `.env`.
- **Rutas inexistentes:** un `re_path` comodín muestra una página 404 propia (o un
  404 en JSON para rutas bajo `/api/`).

## Comandos útiles

| Comando | Qué hace |
|---|---|
| `python manage.py importar_datos` | Carga el catálogo (`datos/catalogo.json`) en una base de datos nueva |
| `python manage.py exportar_datos --solo-catalogo` | Exporta categorías y productos a `datos/catalogo.json` |
| `python manage.py generar_ventas_demo` | Crea un historial de ventas de demostración sin alterar el stock |
| `python manage.py generar_ventas_demo --borrar` | Elimina las ventas y clientes de demostración |

## Estructura del proyecto

```
tienda_hardware/   Configuración, rutas, vistas HTML y documentación protegida
usuarios/          Usuario con rol, JWT con claims y permisos por rol
catalogo/          Categorías y productos (con fotos), filtros
carrito/           Carro persistente y señal que lo crea
ordenes/           Órdenes, lógica de stock (services.py), reporte de ventas y comandos
templates/         Plantillas HTML de la tienda
static/            CSS, JavaScript e imágenes del banner y del login
media/             Fotos de productos
datos/             Catálogo exportado (catalogo.json)
```