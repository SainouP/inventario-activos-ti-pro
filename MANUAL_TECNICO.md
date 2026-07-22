# Manual Técnico

## Arquitectura
Navegador → FastAPI → SQLModel → SQLite

## Seguridad
- Cookies HTTP-only para la interfaz.
- JWT Bearer para la API.
- Contraseñas con bcrypt.
- Reglas de acceso aplicadas en rutas web y API.

## Actualizaciones parciales
El endpoint PATCH utiliza `exclude_unset=True`, por lo que enviar:

```json
{"status": "Disponible"}
```

solo cambia el estado y no reemplaza nombre, marca, modelo ni otros campos.

## Auditoría
Los cambios de estado, asignaciones, devoluciones, mantenimientos y bajas se
registran en `AssetHistory`.
