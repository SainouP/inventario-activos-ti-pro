# Inventario de Activos TI Pro

Sistema web empresarial para controlar activos tecnológicos, usuarios,
asignaciones, mantenimientos, garantías y auditoría.

## Diferencias por rol

### Administrador
- Dashboard completo.
- Gestión de usuarios.
- Creación y edición de activos.
- Cambio manual de estado.
- Asignaciones y devoluciones.
- Mantenimientos.
- Baja lógica y eliminación definitiva.
- Exportación CSV.
- Auditoría.

### Técnico
- Dashboard operativo.
- Creación y edición de activos.
- Cambio de estado.
- Asignaciones, devoluciones y mantenimiento.
- No administra usuarios ni elimina activos.

### Empleado
- Vista exclusiva de sus equipos.
- No ve el inventario de la empresa.
- No ve Swagger, reportes ni exportaciones.
- Consulta ficha, garantía e historial de sus activos.

## Instalación

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Aplicación: `http://127.0.0.1:8000`

Swagger: `http://127.0.0.1:8000/docs`

## Usuarios demo

| Rol | Correo | Contraseña |
|---|---|---|
| Administrador | admin@demo.com | Admin123 |
| Técnico | tecnico@demo.com | Tecnico123 |
| Empleado | empleado@demo.com | Empleado123 |

## Pruebas

```powershell
python -m pytest -q --disable-warnings
```

## Tecnologías

Python, FastAPI, SQLModel, SQLite, Jinja2, Chart.js, Pytest, Docker y GitHub Actions.

# Capturas del proyecto

## Login

![Login](screenshots/login.png)

---

## Dashboard Administrador

![Dashboard Admin 1](screenshots/dashboard1_Admin.png)

![Dashboard Admin 2](screenshots/dashboard2_Admin.png)

---

## Gestión de usuarios

![Gestión de usuarios](screenshots/gestion_usuarios_Admin.png)

---

## Exportación de datos

![Exportación](screenshots/exportacion_datos_Admin.png)

---

## Ficha de activo - Administrador

![Ficha Admin 1](screenshots/ficha_activo1_Admin.png)

![Ficha Admin 2](screenshots/ficha_activo2_Admin.png)

---

## Panel Técnico

![Panel Técnico 1](screenshots/panel_Tecnico.png)

![Panel Técnico 2](screenshots/panel2_Tecnico.png)

---

## Ficha de activo - Técnico

![Ficha Técnico 1](screenshots/ficha_activo1_Tecnico.png)

![Ficha Técnico 2](screenshots/ficha_activo2_Tecnico.png)

---

## Vista Empleado

![Inventario Empleado](screenshots/inventario_empresarial_Empleado.png)

![Ficha Empleado](screenshots/ficha_activo_empleado.png)

---

## Swagger

![Swagger](screenshots/swagger.png)

---

## Pruebas automatizadas

![Tests](screenshots/test.png)