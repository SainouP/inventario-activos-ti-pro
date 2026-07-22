from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
import csv
import io

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from .database import create_db_and_tables, engine, get_session
from .models import (
    Asset, AssetCreate, AssetHistory, AssetStatus, AssetType, AssetUpdate,
    Assignment, AssignmentCreate, LoginRequest, Maintenance, MaintenanceCreate,
    MaintenanceType, TokenResponse, User, UserRole, utc_now
)
from .security import (
    authenticate, create_token, current_api_user, current_web_user,
    hash_password, require_staff
)

BASE_DIR = Path(__file__).resolve().parent

def seed_data(session: Session) -> None:
    if not session.exec(select(User)).first():
        session.add_all([
            User(full_name="Administrador Demo", email="admin@demo.com",
                 password_hash=hash_password("Admin123"), role=UserRole.ADMIN,
                 department="TI", location="San Isidro"),
            User(full_name="Técnico Demo", email="tecnico@demo.com",
                 password_hash=hash_password("Tecnico123"), role=UserRole.TECHNICIAN,
                 department="Infraestructura", location="San Isidro"),
            User(full_name="Empleado Demo", email="empleado@demo.com",
                 password_hash=hash_password("Empleado123"), role=UserRole.EMPLOYEE,
                 department="Contabilidad", location="San Miguel"),
        ])
        session.commit()

    if not session.exec(select(Asset)).first():
        users = session.exec(select(User)).all()
        employee = next(u for u in users if u.role == UserRole.EMPLOYEE)
        assets = [
            Asset(asset_code="ACT-001", serial_number="SN-LAP-001", name="Laptop Contabilidad",
                  asset_type=AssetType.LAPTOP, brand="Lenovo", model="ThinkPad E14",
                  status=AssetStatus.ASSIGNED, location="San Miguel", department="Contabilidad",
                  purchase_date=date.today()-timedelta(days=500),
                  warranty_end=date.today()+timedelta(days=40), purchase_cost=3200,
                  assigned_user_id=employee.id),
            Asset(asset_code="ACT-002", serial_number="SN-MON-002", name="Monitor 24 pulgadas",
                  asset_type=AssetType.MONITOR, brand="LG", model="24MP400",
                  status=AssetStatus.AVAILABLE, location="San Isidro", department="TI",
                  purchase_date=date.today()-timedelta(days=280),
                  warranty_end=date.today()+timedelta(days=300), purchase_cost=650),
            Asset(asset_code="ACT-003", serial_number="SN-PRN-003", name="Impresora Finanzas",
                  asset_type=AssetType.PRINTER, brand="HP", model="LaserJet Pro",
                  status=AssetStatus.MAINTENANCE, location="Miraflores", department="Finanzas",
                  purchase_date=date.today()-timedelta(days=900),
                  warranty_end=date.today()-timedelta(days=170), purchase_cost=1400),
            Asset(asset_code="ACT-004", serial_number="SN-PC-004", name="PC Recepción",
                  asset_type=AssetType.DESKTOP, brand="Dell", model="OptiPlex 7090",
                  status=AssetStatus.AVAILABLE, location="San Isidro", department="Administración",
                  purchase_date=date.today()-timedelta(days=420),
                  warranty_end=date.today()+timedelta(days=120), purchase_cost=2800),
        ]
        session.add_all(assets)
        session.commit()

@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    with Session(engine) as session:
        seed_data(session)
    yield

app = FastAPI(
    title="Inventario de Activos TI Pro",
    description="Inventario empresarial con paneles por rol, auditoría, asignaciones y mantenimiento.",
    version="2.0.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

def web_user(request: Request, session: Session):
    user = current_web_user(request, session)
    return user or RedirectResponse("/login", status_code=303)

def asset_or_404(asset_id: int, session: Session) -> Asset:
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Activo no encontrado")
    return asset

def add_history(session: Session, asset_id: int, action: str, actor: str) -> None:
    session.add(AssetHistory(asset_id=asset_id, action=action, performed_by=actor))

def can_view_asset(user: User, asset: Asset) -> bool:
    return user.role != UserRole.EMPLOYEE or asset.assigned_user_id == user.id

@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})

@app.post("/login", response_class=HTMLResponse, include_in_schema=False)
def login_web(request: Request, email: str = Form(...), password: str = Form(...),
              session: Session = Depends(get_session)):
    user = authenticate(email, password, session)
    if not user:
        return templates.TemplateResponse(
            request=request, name="login.html",
            context={"error": "Correo o contraseña incorrectos"}, status_code=401
        )
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("session_token", create_token(user), httponly=True, samesite="lax", max_age=10800)
    return response

@app.get("/logout", include_in_schema=False)
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("session_token")
    return response

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard(request: Request, session: Session = Depends(get_session)):
    user = web_user(request, session)
    if isinstance(user, RedirectResponse):
        return user

    statement = select(Asset).order_by(Asset.created_at.desc())
    if user.role == UserRole.EMPLOYEE:
        statement = statement.where(Asset.assigned_user_id == user.id)
    assets = session.exec(statement).all()

    users = session.exec(select(User).where(User.is_active == True)).all()
    maintenances = session.exec(select(Maintenance).order_by(Maintenance.created_at.desc())).all()
    histories = session.exec(select(AssetHistory).order_by(AssetHistory.created_at.desc())).all()[:8]
    today = date.today()
    warranty_limit = today + timedelta(days=60)

    stats = {
        "total": len(assets),
        "available": sum(a.status == AssetStatus.AVAILABLE for a in assets),
        "assigned": sum(a.status == AssetStatus.ASSIGNED for a in assets),
        "maintenance": sum(a.status == AssetStatus.MAINTENANCE for a in assets),
        "retired": sum(a.status == AssetStatus.RETIRED for a in assets),
        "warranty": sum(a.warranty_end and today <= a.warranty_end <= warranty_limit for a in assets),
        "value": sum(a.purchase_cost for a in assets),
        "users": len(users),
        "pending_maintenance": sum(m.completed_date is None for m in maintenances),
    }

    status_chart = {
        "labels": [s.value for s in AssetStatus],
        "values": [sum(a.status == s for a in assets) for s in AssetStatus],
    }
    type_chart = {
        "labels": [t.value for t in AssetType],
        "values": [sum(a.asset_type == t for a in assets) for t in AssetType],
    }

    return templates.TemplateResponse(
        request=request, name="dashboard.html",
        context={
            "user": user, "assets": assets, "users": users, "stats": stats,
            "histories": histories, "asset_types": list(AssetType),
            "asset_statuses": list(AssetStatus),
            "status_chart": status_chart, "type_chart": type_chart,
        },
    )

@app.get("/users", response_class=HTMLResponse, include_in_schema=False)
def users_page(request: Request, session: Session = Depends(get_session)):
    user = web_user(request, session)
    if isinstance(user, RedirectResponse):
        return user
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Solo el administrador gestiona usuarios")
    users = session.exec(select(User).order_by(User.created_at.desc())).all()
    return templates.TemplateResponse(
        request=request, name="users.html",
        context={"user": user, "users": users, "roles": list(UserRole)},
    )

@app.post("/web/users", include_in_schema=False)
def create_user_web(
    request: Request, full_name: str = Form(...), email: str = Form(...),
    password: str = Form(...), role: UserRole = Form(...),
    department: str = Form(...), location: str = Form(...),
    session: Session = Depends(get_session),
):
    user = web_user(request, session)
    if isinstance(user, RedirectResponse):
        return user
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Solo el administrador gestiona usuarios")
    if session.exec(select(User).where(User.email == email.lower().strip())).first():
        raise HTTPException(status_code=409, detail="El correo ya existe")
    session.add(User(
        full_name=full_name.strip(), email=email.lower().strip(),
        password_hash=hash_password(password), role=role,
        department=department.strip(), location=location.strip(),
    ))
    session.commit()
    return RedirectResponse("/users", status_code=303)

@app.post("/web/users/{user_id}/toggle", include_in_schema=False)
def toggle_user(user_id: int, request: Request, session: Session = Depends(get_session)):
    actor = web_user(request, session)
    if isinstance(actor, RedirectResponse):
        return actor
    if actor.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Solo el administrador gestiona usuarios")
    target = session.get(User, user_id)
    if not target or target.id == actor.id:
        raise HTTPException(status_code=400, detail="Operación no permitida")
    target.is_active = not target.is_active
    session.add(target)
    session.commit()
    return RedirectResponse("/users", status_code=303)

@app.post("/web/assets", include_in_schema=False)
def create_asset_web(
    request: Request, asset_code: str = Form(...), serial_number: str = Form(...),
    name: str = Form(...), asset_type: AssetType = Form(...),
    brand: str = Form(...), model: str = Form(...),
    location: str = Form(...), department: str = Form(...),
    purchase_date: str = Form(default=""), warranty_end: str = Form(default=""),
    purchase_cost: float = Form(default=0), notes: str = Form(default=""),
    session: Session = Depends(get_session),
):
    user = web_user(request, session)
    if isinstance(user, RedirectResponse):
        return user
    if user.role == UserRole.EMPLOYEE:
        raise HTTPException(status_code=403, detail="No puedes crear activos")
    asset = Asset(
        asset_code=asset_code.strip(), serial_number=serial_number.strip(),
        name=name.strip(), asset_type=asset_type, brand=brand.strip(),
        model=model.strip(), location=location.strip(), department=department.strip(),
        purchase_date=date.fromisoformat(purchase_date) if purchase_date else None,
        warranty_end=date.fromisoformat(warranty_end) if warranty_end else None,
        purchase_cost=purchase_cost, notes=notes.strip() or None,
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    add_history(session, asset.id, "Activo registrado", user.full_name)
    session.commit()
    return RedirectResponse("/", status_code=303)

@app.get("/assets/{asset_id}", response_class=HTMLResponse, include_in_schema=False)
def asset_detail(asset_id: int, request: Request, session: Session = Depends(get_session)):
    user = web_user(request, session)
    if isinstance(user, RedirectResponse):
        return user
    asset = asset_or_404(asset_id, session)
    if not can_view_asset(user, asset):
        raise HTTPException(status_code=403, detail="No puedes consultar este activo")
    assignments = session.exec(select(Assignment).where(Assignment.asset_id == asset_id)
                               .order_by(Assignment.assigned_at.desc())).all()
    maintenances = session.exec(select(Maintenance).where(Maintenance.asset_id == asset_id)
                                .order_by(Maintenance.created_at.desc())).all()
    histories = session.exec(select(AssetHistory).where(AssetHistory.asset_id == asset_id)
                             .order_by(AssetHistory.created_at.desc())).all()
    users = session.exec(select(User).where(User.is_active == True)).all()
    return templates.TemplateResponse(
        request=request, name="detail.html",
        context={
            "user": user, "asset": asset, "users": users,
            "assignments": assignments, "maintenances": maintenances,
            "histories": histories, "maintenance_types": list(MaintenanceType),
            "asset_types": list(AssetType), "asset_statuses": list(AssetStatus),
        },
    )

@app.post("/web/assets/{asset_id}/edit", include_in_schema=False)
def edit_asset_web(
    asset_id: int, request: Request, name: str = Form(...),
    asset_type: AssetType = Form(...), brand: str = Form(...), model: str = Form(...),
    status: AssetStatus = Form(...), location: str = Form(...),
    department: str = Form(...), warranty_end: str = Form(default=""),
    purchase_cost: float = Form(default=0), notes: str = Form(default=""),
    session: Session = Depends(get_session),
):
    user = web_user(request, session)
    if isinstance(user, RedirectResponse):
        return user
    if user.role == UserRole.EMPLOYEE:
        raise HTTPException(status_code=403, detail="No puedes editar activos")
    asset = asset_or_404(asset_id, session)
    old_status = asset.status
    asset.name, asset.asset_type = name.strip(), asset_type
    asset.brand, asset.model = brand.strip(), model.strip()
    asset.status, asset.location, asset.department = status, location.strip(), department.strip()
    asset.warranty_end = date.fromisoformat(warranty_end) if warranty_end else None
    asset.purchase_cost, asset.notes = purchase_cost, notes.strip() or None
    asset.updated_at = utc_now()
    if status != AssetStatus.ASSIGNED:
        asset.assigned_user_id = None
    session.add(asset)
    action = "Datos del activo actualizados"
    if old_status != status:
        action = f"Estado cambiado de {old_status.value} a {status.value}"
    add_history(session, asset_id, action, user.full_name)
    session.commit()
    return RedirectResponse(f"/assets/{asset_id}", status_code=303)

@app.post("/web/assets/{asset_id}/assign", include_in_schema=False)
def assign_asset_web(
    asset_id: int, request: Request, user_id: int = Form(...),
    notes: str = Form(default=""), session: Session = Depends(get_session),
):
    user = web_user(request, session)
    if isinstance(user, RedirectResponse):
        return user
    if user.role not in {UserRole.ADMIN, UserRole.TECHNICIAN}:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    asset = asset_or_404(asset_id, session)
    employee = session.get(User, user_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    asset.assigned_user_id, asset.status, asset.updated_at = user_id, AssetStatus.ASSIGNED, utc_now()
    session.add(asset)
    session.add(Assignment(asset_id=asset_id, user_id=user_id, assigned_by=user.full_name,
                           notes=notes.strip() or None))
    add_history(session, asset_id, f"Asignado a {employee.full_name}", user.full_name)
    session.commit()
    return RedirectResponse(f"/assets/{asset_id}", status_code=303)

@app.post("/web/assets/{asset_id}/return", include_in_schema=False)
def return_asset_web(asset_id: int, request: Request, session: Session = Depends(get_session)):
    user = web_user(request, session)
    if isinstance(user, RedirectResponse):
        return user
    if user.role not in {UserRole.ADMIN, UserRole.TECHNICIAN}:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    asset = asset_or_404(asset_id, session)
    active = session.exec(select(Assignment).where(
        Assignment.asset_id == asset_id, Assignment.returned_at == None
    ).order_by(Assignment.assigned_at.desc())).first()
    if active:
        active.returned_at = utc_now()
        session.add(active)
    asset.assigned_user_id, asset.status, asset.updated_at = None, AssetStatus.AVAILABLE, utc_now()
    session.add(asset)
    add_history(session, asset_id, "Activo devuelto y disponible", user.full_name)
    session.commit()
    return RedirectResponse(f"/assets/{asset_id}", status_code=303)

@app.post("/web/assets/{asset_id}/maintenance", include_in_schema=False)
def maintenance_web(
    asset_id: int, request: Request, maintenance_type: MaintenanceType = Form(...),
    description: str = Form(...), scheduled_date: str = Form(...),
    cost: float = Form(default=0), session: Session = Depends(get_session),
):
    user = web_user(request, session)
    if isinstance(user, RedirectResponse):
        return user
    if user.role not in {UserRole.ADMIN, UserRole.TECHNICIAN}:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    asset = asset_or_404(asset_id, session)
    session.add(Maintenance(
        asset_id=asset_id, maintenance_type=maintenance_type,
        description=description.strip(), technician_name=user.full_name,
        scheduled_date=date.fromisoformat(scheduled_date), cost=cost,
    ))
    asset.status, asset.updated_at = AssetStatus.MAINTENANCE, utc_now()
    asset.assigned_user_id = None
    session.add(asset)
    add_history(session, asset_id, f"Mantenimiento {maintenance_type.value} registrado", user.full_name)
    session.commit()
    return RedirectResponse(f"/assets/{asset_id}", status_code=303)

@app.post("/web/assets/{asset_id}/retire", include_in_schema=False)
def retire_asset_web(asset_id: int, request: Request, reason: str = Form(...),
                     session: Session = Depends(get_session)):
    user = web_user(request, session)
    if isinstance(user, RedirectResponse):
        return user
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Solo el administrador puede dar de baja")
    asset = asset_or_404(asset_id, session)
    asset.status, asset.retired_reason = AssetStatus.RETIRED, reason.strip()
    asset.assigned_user_id, asset.updated_at = None, utc_now()
    session.add(asset)
    add_history(session, asset_id, f"Activo dado de baja: {reason.strip()}", user.full_name)
    session.commit()
    return RedirectResponse(f"/assets/{asset_id}", status_code=303)

@app.post("/web/assets/{asset_id}/delete", include_in_schema=False)
def delete_asset_web(asset_id: int, request: Request, session: Session = Depends(get_session)):
    user = web_user(request, session)
    if isinstance(user, RedirectResponse):
        return user
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Solo el administrador puede eliminar")
    asset = asset_or_404(asset_id, session)
    session.delete(asset)
    session.commit()
    return RedirectResponse("/", status_code=303)

@app.get("/web/export/csv", include_in_schema=False)
def export_csv(request: Request, session: Session = Depends(get_session)):
    user = web_user(request, session)
    if isinstance(user, RedirectResponse):
        return user
    if user.role == UserRole.EMPLOYEE:
        raise HTTPException(status_code=403, detail="No puedes exportar el inventario")
    assets = session.exec(select(Asset).order_by(Asset.asset_code)).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Código","Serie","Nombre","Tipo","Marca","Modelo","Estado","Sede","Área","Costo","Garantía"])
    for a in assets:
        writer.writerow([a.asset_code,a.serial_number,a.name,a.asset_type.value,a.brand,a.model,
                         a.status.value,a.location,a.department,a.purchase_cost,a.warranty_end or ""])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition":"attachment; filename=inventario_activos.csv"})

@app.post("/api/auth/login", response_model=TokenResponse, tags=["Autenticación"])
def api_login(data: LoginRequest, session: Session = Depends(get_session)):
    user = authenticate(data.email, data.password, session)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return TokenResponse(access_token=create_token(user), user_name=user.full_name, role=user.role)

@app.get("/api/assets", tags=["Activos"])
def api_list_assets(
    status: AssetStatus | None = Query(default=None),
    asset_type: AssetType | None = Query(default=None),
    session: Session = Depends(get_session), user: User = Depends(current_api_user),
):
    statement = select(Asset)
    if user.role == UserRole.EMPLOYEE:
        statement = statement.where(Asset.assigned_user_id == user.id)
    if status:
        statement = statement.where(Asset.status == status)
    if asset_type:
        statement = statement.where(Asset.asset_type == asset_type)
    return session.exec(statement.order_by(Asset.created_at.desc())).all()

@app.post("/api/assets", status_code=201, tags=["Activos"])
def api_create_asset(data: AssetCreate, session: Session = Depends(get_session),
                     user: User = Depends(require_staff)):
    asset = Asset(**data.model_dump())
    session.add(asset); session.commit(); session.refresh(asset)
    add_history(session, asset.id, "Activo creado mediante API", user.full_name)
    session.commit(); session.refresh(asset)
    return asset

@app.patch("/api/assets/{asset_id}", tags=["Activos"])
def api_update_asset(asset_id: int, data: AssetUpdate, session: Session = Depends(get_session),
                     user: User = Depends(require_staff)):
    asset = asset_or_404(asset_id, session)
    old_status = asset.status
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(asset, key, value)
    asset.updated_at = utc_now()
    session.add(asset)
    action = "Activo actualizado mediante API"
    if data.status and data.status != old_status:
        action = f"Estado cambiado de {old_status.value} a {data.status.value}"
    add_history(session, asset_id, action, user.full_name)
    session.commit(); session.refresh(asset)
    return asset

@app.delete("/api/assets/{asset_id}", status_code=204, tags=["Activos"])
def api_delete_asset(asset_id: int, session: Session = Depends(get_session),
                     user: User = Depends(current_api_user)):
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Solo el administrador puede eliminar")
    asset = asset_or_404(asset_id, session)
    session.delete(asset); session.commit()
    return None

@app.get("/health", tags=["Sistema"])
def health():
    return {"status":"ok","version":"2.0.0"}
