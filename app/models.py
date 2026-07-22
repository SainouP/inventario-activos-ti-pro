from datetime import date, datetime, timezone
from enum import Enum
from sqlmodel import Field, SQLModel

def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

class UserRole(str, Enum):
    ADMIN = "Administrador"
    TECHNICIAN = "Técnico"
    EMPLOYEE = "Empleado"

class AssetType(str, Enum):
    LAPTOP = "Laptop"
    DESKTOP = "PC de escritorio"
    MONITOR = "Monitor"
    PRINTER = "Impresora"
    PHONE = "Celular"
    TABLET = "Tablet"
    NETWORK = "Equipo de red"
    OTHER = "Otro"

class AssetStatus(str, Enum):
    AVAILABLE = "Disponible"
    ASSIGNED = "Asignado"
    MAINTENANCE = "En mantenimiento"
    RETIRED = "Dado de baja"
    LOST = "Perdido"

class MaintenanceType(str, Enum):
    PREVENTIVE = "Preventivo"
    CORRECTIVE = "Correctivo"
    INSPECTION = "Inspección"

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    full_name: str = Field(min_length=2, max_length=100)
    email: str = Field(unique=True, index=True, max_length=150)
    password_hash: str
    role: UserRole = Field(default=UserRole.EMPLOYEE)
    department: str = Field(default="General", max_length=100)
    location: str = Field(default="Lima", max_length=100)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)

class Asset(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    asset_code: str = Field(unique=True, index=True, max_length=50)
    serial_number: str = Field(unique=True, index=True, max_length=100)
    name: str = Field(min_length=2, max_length=120)
    asset_type: AssetType
    brand: str = Field(max_length=80)
    model: str = Field(max_length=100)
    status: AssetStatus = Field(default=AssetStatus.AVAILABLE)
    location: str = Field(default="Lima", max_length=100)
    department: str = Field(default="TI", max_length=100)
    purchase_date: date | None = None
    warranty_end: date | None = None
    purchase_cost: float = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=1500)
    assigned_user_id: int | None = Field(default=None, foreign_key="user.id")
    retired_reason: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

class Assignment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="asset.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    assigned_by: str = Field(max_length=100)
    assigned_at: datetime = Field(default_factory=utc_now)
    returned_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=800)

class Maintenance(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="asset.id", index=True)
    maintenance_type: MaintenanceType
    description: str = Field(min_length=3, max_length=1500)
    technician_name: str = Field(max_length=100)
    scheduled_date: date
    completed_date: date | None = None
    cost: float = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utc_now)

class AssetHistory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="asset.id", index=True)
    action: str = Field(max_length=250)
    performed_by: str = Field(max_length=100)
    created_at: datetime = Field(default_factory=utc_now)

class LoginRequest(SQLModel):
    email: str
    password: str

class TokenResponse(SQLModel):
    access_token: str
    token_type: str = "bearer"
    user_name: str
    role: UserRole

class AssetCreate(SQLModel):
    asset_code: str
    serial_number: str
    name: str
    asset_type: AssetType
    brand: str
    model: str
    location: str = "Lima"
    department: str = "TI"
    purchase_date: date | None = None
    warranty_end: date | None = None
    purchase_cost: float = 0
    notes: str | None = None

class AssetUpdate(SQLModel):
    name: str | None = None
    asset_type: AssetType | None = None
    brand: str | None = None
    model: str | None = None
    status: AssetStatus | None = None
    location: str | None = None
    department: str | None = None
    warranty_end: date | None = None
    purchase_cost: float | None = None
    notes: str | None = None

class AssignmentCreate(SQLModel):
    user_id: int
    notes: str | None = None

class MaintenanceCreate(SQLModel):
    maintenance_type: MaintenanceType
    description: str
    technician_name: str
    scheduled_date: date
    completed_date: date | None = None
    cost: float = 0
