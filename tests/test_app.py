from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from app.database import get_session
from app.main import app, seed_data

engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
def override_session():
    with Session(engine) as session: yield session
app.dependency_overrides[get_session]=override_session
client=TestClient(app)

def setup_function():
    SQLModel.metadata.drop_all(engine);SQLModel.metadata.create_all(engine)
    with Session(engine) as session: seed_data(session)

def token(email,password):
    r=client.post("/api/auth/login",json={"email":email,"password":password});assert r.status_code==200
    return r.json()["access_token"]
def auth(t): return {"Authorization":f"Bearer {t}"}
def payload(code="ACT-100",serial="SER-100"):
    return {"asset_code":code,"serial_number":serial,"name":"Laptop prueba","asset_type":"Laptop",
    "brand":"Dell","model":"Latitude","location":"San Isidro","department":"TI",
    "purchase_date":str(date.today()),"warranty_end":str(date.today()+timedelta(days=365)),
    "purchase_cost":3500,"notes":"Prueba"}

def test_health(): assert client.get("/health").json()["status"]=="ok"
def test_admin_creates_asset():
    r=client.post("/api/assets",json=payload(),headers=auth(token("admin@demo.com","Admin123")))
    assert r.status_code==201 and r.json()["asset_code"]=="ACT-100"
def test_employee_cannot_create():
    r=client.post("/api/assets",json=payload("ACT-101","SER-101"),headers=auth(token("empleado@demo.com","Empleado123")))
    assert r.status_code==403
def test_patch_only_changes_status():
    admin=token("admin@demo.com","Admin123")
    created=client.post("/api/assets",json=payload("ACT-102","SER-102"),headers=auth(admin)).json()
    r=client.patch(f"/api/assets/{created['id']}",json={"status":"En mantenimiento"},headers=auth(admin))
    assert r.status_code==200 and r.json()["status"]=="En mantenimiento" and r.json()["name"]=="Laptop prueba"
def test_employee_sees_only_assigned_assets():
    employee=token("empleado@demo.com","Empleado123")
    r=client.get("/api/assets",headers=auth(employee))
    assert r.status_code==200
    assert all(a["assigned_user_id"]==3 for a in r.json())
def test_technician_cannot_delete():
    tech=token("tecnico@demo.com","Tecnico123")
    r=client.delete("/api/assets/1",headers=auth(tech))
    assert r.status_code==403
