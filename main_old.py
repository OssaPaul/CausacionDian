import os
from dotenv import load_dotenv

import uuid
import traceback
from datetime import date, timedelta
from typing import Optional, Dict, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client
from apscheduler.schedulers.background import BackgroundScheduler

from dian_parser import DianXmlParser
from puc_engine import PucAccountingEngine, GroupingMode
from imap_ingestion import DianImapIngestionEngine
from erp_exporter import ErpExporterEngine
from auth_security import (
    hash_password, verify_password, create_access_token,
    get_current_user, RoleChecker
)

load_dotenv()

# URL Y CLAVE DE SUPABASE
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("[DEBUG INIT] Cliente de Supabase conectado a URL oficial (vacjvjbmhntmhqybyovq).")
except Exception as e:
    print(f"[ERROR CRÍTICO] Error al inicializar Supabase: {str(e)}")

templates = Jinja2Templates(directory="templates")
scheduler = BackgroundScheduler()


# --- HELPER CENTRAL DE CONTROL DE SUSCRIPCIÓN Y CRÉDITOS ---

def validate_organization_subscription(organization_id: str, require_available_credit: bool = True) -> dict:
    """
    Valida que la organización tenga una suscripción activa en company_subscriptions
    y opcionalmente que cuente con créditos disponibles.
    """
    if not organization_id:
        raise HTTPException(status_code=422, detail="Relación requerida: organization_id es obligatorio.")

    res = supabase.table("company_subscriptions")\
        .select("*")\
        .eq("organization_id", organization_id)\
        .eq("is_active", True)\
        .limit(1)\
        .execute()

    if not res or not res.data:
        raise HTTPException(
            status_code=402,
            detail="Suscripción requerida: La organización no tiene un plan activo registrado en company_subscriptions. Contacte al Super Admin."
        )

    sub = res.data[0]
    allocated = int(sub.get("credits_allocated") or 0)
    used = int(sub.get("credits_used") or 0)
    remaining = allocated - used

    end_date_str = sub.get("end_date")
    if end_date_str:
        try:
            if date.fromisoformat(str(end_date_str)[:10]) < date.today():
                raise HTTPException(
                    status_code=402,
                    detail=f"Suscripción vencida: El plan venció el {end_date_str}. Renueve la suscripción para continuar."
                )
        except ValueError:
            pass

    if require_available_credit and remaining <= 0:
        raise HTTPException(
            status_code=402,
            detail=f"Sin créditos disponibles: Se consumieron los {allocated} créditos asignados al plan ({sub.get('plan_name')})."
        )

    return sub


def consume_subscription_credit(subscription: dict, credits_to_consume: int = 1):
    """Incrementa credits_used en company_subscriptions."""
    current_used = int(subscription.get("credits_used") or 0)
    new_used = current_used + credits_to_consume
    supabase.table("company_subscriptions")\
        .update({"credits_used": new_used})\
        .eq("id", subscription["id"])\
        .execute()
    return new_used


def run_scheduled_email_sync(target_org_id: Optional[str] = None):
    """Ejecución programada o manual con bloqueo por suscripción activa"""
    processed_accounts = 0
    skipped_orgs = []
    try:
        query = supabase.table("company_email_integrations").select("*").eq("is_active", True)
        if target_org_id:
            query = query.eq("organization_id", target_org_id)
        res = query.execute()

        if not res or not res.data:
            print("[IMAP SYNC] No se encontraron cuentas de correo IMAP activas para sincronizar.")
            return {"processed_accounts": 0, "message": "No hay cuentas IMAP activas configuradas."}

        for config in res.data:
            org_id = config.get("organization_id")
            if not org_id:
                continue

            # Validar suscripción activa antes de descargar correos
            try:
                validate_organization_subscription(org_id, require_available_credit=True)
            except HTTPException as sub_err:
                print(f"[IMAP SYNC BLOQUEADO] Org {org_id}: {sub_err.detail}")
                skipped_orgs.append({"organization_id": org_id, "reason": sub_err.detail})
                if target_org_id:
                    return {"processed_accounts": 0, "error": sub_err.detail}
                continue

            print(f"[IMAP SYNC] Conectando a {config['email_account']} ({config['imap_server']}:{config['imap_port']})...")
            engine = DianImapIngestionEngine(
                integration_id=config["id"],
                organization_id=org_id,
                direction=config["direction"],
                server=config["imap_server"],
                port=config["imap_port"],
                user=config["email_account"],
                password=config["email_password"],
                folder_name=config.get("folder_name", "INBOX"),
                api_url="http://127.0.0.1:8000/upload-xml",
                supabase_client=supabase
            )
            engine.process_mailbox()
            processed_accounts += 1

        return {
            "processed_accounts": processed_accounts,
            "skipped_organizations": skipped_orgs,
            "message": f"Sincronización finalizada sobre {processed_accounts} cuenta(s) IMAP."
        }
    except Exception as e:
        err_msg = str(e)
        print(f"[IMAP SYNC ERROR] Error en sincronización de correos: {err_msg}")
        traceback.print_exc()
        return {"processed_accounts": processed_accounts, "error": err_msg}


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(run_scheduled_email_sync, 'interval', minutes=5, id='email_sync_job')
    scheduler.start()
    print("[SYSTEM] Scheduler de ingesta IMAP iniciado correctamente (Ciclo: 5 min).")
    yield
    scheduler.shutdown()
    print("[SYSTEM] Scheduler detenido.")

app = FastAPI(
    title="DIAN Invoice SaaS - Engine & Dashboard",
    description="API SaaS Multi-Tenant de Un Nivel (Organizaciones)",
    version="3.5.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

allow_super_admin = RoleChecker(["SUPER_ADMIN"])
allow_company_admin = RoleChecker(["SUPER_ADMIN", "COMPANY_ADMIN"])
allow_operator = RoleChecker(["SUPER_ADMIN", "COMPANY_ADMIN", "COMPANY_OPERATOR"])
allow_exporter = RoleChecker(["SUPER_ADMIN", "COMPANY_ADMIN", "COMPANY_OPERATOR", "COMPANY_EXPORTER"])


# --- ESQUEMAS PYDANTIC MULTI-TENANT ---

class LoginSchema(BaseModel):
    email: EmailStr
    password: str
    selected_organization_id: Optional[str] = None

class RegisterUserSchema(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    organization_id: str
    role: str = "COMPANY_OPERATOR"

class UpdateUserSchema(BaseModel):
    full_name: str
    email: EmailStr
    role: str
    password: Optional[str] = None
    is_active: Optional[bool] = True

class OrganizationSchema(BaseModel):
    name: str
    nit: str
    is_active: Optional[bool] = True

class CompanyExceptionSchema(BaseModel):
    name: str
    nit: str
    organization_id: Optional[str] = None
    is_active: Optional[bool] = True
    unspsc: Optional[str] = None

class SubscriptionSchema(BaseModel):
    organization_id: str
    plan_name: str = "ENTERPRISE"
    credits_allocated: int = 1000
    credits_used: Optional[int] = 0
    monthly_fee: float = 0.0
    billing_cycle: str = "MONTHLY"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_active: bool = True

class SubscriptionPlanCreate(BaseModel):
    code: str
    name: str
    credits_allocated: int
    monthly_fee: float
    additional_credit_fee: float
    is_active: Optional[bool] = True

class SubscriptionPlanUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    credits_allocated: Optional[int] = None
    monthly_fee: Optional[float] = None
    additional_credit_fee: Optional[float] = None
    is_active: Optional[bool] = None

class AccountingParameterSchema(BaseModel):
    concept_code: str
    concept_name: str
    account_puc: str
    account_name: str
    nature: str  # 'D' o 'C'
    tipo_documento: str = "01"  # '01', '91', '92'
    organization_id: Optional[str] = None

class UnspscSchema(BaseModel):
    code: str
    description: str
    category_type: str  # COMPRA, GASTO, COSTO
    suggested_puc_account: str
    tipo_documento: str = "01"  # '01', '91', '92'
    suggested_tipmov: str = "D"  # 'D' o 'C'

class EmailConfigSchema(BaseModel):
    organization_id: Optional[str] = None
    direction: str = "RECIBIDA"
    imap_server: str
    imap_port: int = 993
    email_account: str
    email_password: Optional[str] = None
    folder_name: str = "INBOX"
    scan_frequency_minutes: int = 15
    is_active: bool = True

class BatchCausarSchema(BaseModel):
    invoice_ids: List[str]
    grouping_mode: GroupingMode = GroupingMode.CONSOLIDATED

class UploadResponse(BaseModel):
    success: bool
    message: str
    invoice_id: str
    cufe: str
    full_number: str
    payable_amount: float
    items_count: int
    taxes_count: int

class AccountingLineResponse(BaseModel):
    account_puc: str
    account_name: str
    third_party_nit: str
    third_party_name: str
    debit: float
    credit: float
    description: str

class JournalEntryResponse(BaseModel):
    invoice_id: str
    full_number: str
    grouping_mode: str
    total_debit: float
    total_credit: float
    is_balanced: bool
    lines: List[AccountingLineResponse]


@app.get("/", response_class=HTMLResponse)
def render_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")


# --- ENDPOINTS AUTENTICACIÓN & TENANT MAESTRO ---

@app.get("/auth/organizations")
def get_public_organizations_list():
    """Devuelve las organizaciones para alimentar el selector del login"""
    try:
        res = supabase.table("organizations").select("*").execute()
        data = res.data or []
        return {"organizations": data, "companies": data}
    except Exception as e:
        print(f"[ERROR AUTH ORGS] {str(e)}")
        return {"organizations": [], "companies": []}

@app.get("/auth/companies")
def get_public_companies_compatibility_list():
    """Endpoint espejo para compatibilidad con el frontend"""
    return get_public_organizations_list()


@app.post("/auth/login")
def login(credentials: LoginSchema):
    email_clean = credentials.email.lower().strip()

    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": email_clean,
            "password": credentials.password
        })
        if not auth_response or not auth_response.user:
            raise HTTPException(status_code=401, detail="Credenciales inválidas.")
        
        user_auth_id = auth_response.user.id
    except Exception as ex:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Credenciales inválidas o error de autenticación: {str(ex)}"
        )

    try:
        res = supabase.table("users_profile").select("*").eq("id", user_auth_id).execute()
    except Exception:
        res = None

    if not res or not res.data:
        user_data = {
            "id": user_auth_id,
            "full_name": "Paul Ossa",
            "email": email_clean,
            "role": "SUPER_ADMIN",
            "organization_id": credentials.selected_organization_id,
            "is_active": True
        }
    else:
        user_data = res.data[0]

    user_role = user_data.get("role", "SUPER_ADMIN")
    active_org_id = user_data.get("organization_id")

    if user_role == "SUPER_ADMIN":
        active_org_id = credentials.selected_organization_id
        if not active_org_id:
            raise HTTPException(
                status_code=400,
                detail="Debe seleccionar una organización activa para iniciar sesión como Super Admin."
            )
    else:
        if not active_org_id:
            raise HTTPException(
                status_code=400,
                detail="Error relacional: El usuario no pertenece a ninguna organización válida."
            )
        if credentials.selected_organization_id and credentials.selected_organization_id != active_org_id:
            raise HTTPException(
                status_code=403,
                detail="Acceso denegado: Su usuario pertenece a una Organización distinta a la seleccionada."
            )

    token = create_access_token({
        "sub": user_data["id"],
        "email": user_data["email"],
        "role": user_role,
        "organization_id": active_org_id
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_data["id"],
            "full_name": user_data.get("full_name", "Usuario"),
            "email": user_data["email"],
            "role": user_role,
            "organization_id": active_org_id,
            "company_id": active_org_id
        }
    }


# --- GESTIÓN DE ORGANIZACIONES (SOLO SUPER_ADMIN) ---

@app.get("/organizations", dependencies=[Depends(allow_super_admin)])
def list_all_organizations():
    try:
        res = supabase.table("organizations").select("*").order("name").execute()
        return {"organizations": res.data or [], "data": res.data or []}
    except Exception:
        return {"organizations": [], "data": []}

@app.post("/organizations", dependencies=[Depends(allow_super_admin)])
def create_organization(org: OrganizationSchema):
    if not org.name or not org.name.strip():
        raise HTTPException(status_code=422, detail="Validación: El nombre de la organización es obligatorio.")
    if not org.nit or not org.nit.strip():
        raise HTTPException(status_code=422, detail="Validación: El NIT de la organización es obligatorio.")

    payload = {
        "name": org.name.strip(),
        "nit": org.nit.strip()
    }

    try:
        res = supabase.table("organizations").insert(payload).execute()
        return {"success": True, "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando organización principal: {str(e)}")

@app.put("/organizations/{org_id}", dependencies=[Depends(allow_super_admin)])
def update_organization(org_id: str, org: OrganizationSchema):
    try:
        res = supabase.table("organizations").update({
            "name": org.name.strip(),
            "nit": org.nit.strip()
        }).eq("id", org_id).execute()
        return {"success": True, "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando organización: {str(e)}")

@app.delete("/organizations/{org_id}", dependencies=[Depends(allow_super_admin)])
def delete_organization(org_id: str):
    try:
        supabase.table("organizations").delete().eq("id", org_id).execute()
        return {"success": True, "message": "Organización eliminada"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se puede eliminar la organización (puede tener registros asociados): {str(e)}")


# --- GESTIÓN DE EXCEPCIONES NIT / COMPANIES (SUPER_ADMIN Y COMPANY_ADMIN) ---

@app.get("/companies", dependencies=[Depends(allow_company_admin)])
def list_companies(current_user: dict = Depends(get_current_user)):
    active_org_id = current_user.get("organization_id")
    try:
        query = supabase.table("companies").select("*")
        if active_org_id:
            query = query.eq("organization_id", active_org_id)
        res = query.order("name").execute()
        return {"companies": res.data or [], "data": res.data or []}
    except Exception:
        return {"companies": [], "data": []}

@app.post("/companies", dependencies=[Depends(allow_company_admin)])
def create_company_exception(comp: CompanyExceptionSchema, current_user: dict = Depends(get_current_user)):
    target_org = current_user.get("organization_id") or comp.organization_id
    if not target_org:
        raise HTTPException(status_code=422, detail="Relación requerida: organization_id es obligatorio.")

    payload = {
        "name": comp.name.strip(),
        "nit": comp.nit.strip(),
        "organization_id": target_org,
        "unspsc": comp.unspsc.strip() if comp.unspsc else None,
        "is_active": True
    }
    try:
        res = supabase.table("companies").insert(payload).execute()
        return {"success": True, "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando excepción NIT: {str(e)}")

@app.put("/companies/{company_id}", dependencies=[Depends(allow_company_admin)])
def update_company_exception(company_id: str, comp: CompanyExceptionSchema):
    try:
        res = supabase.table("companies").update({
            "name": comp.name.strip(),
            "nit": comp.nit.strip(),
            "unspsc": comp.unspsc.strip() if comp.unspsc else None
        }).eq("id", company_id).execute()
        return {"success": True, "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando excepción NIT: {str(e)}")

@app.delete("/companies/{company_id}", dependencies=[Depends(allow_company_admin)])
def delete_company_exception(company_id: str):
    try:
        supabase.table("companies").delete().eq("id", company_id).execute()
        return {"success": True, "message": "Excepción NIT eliminada"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando excepción NIT: {str(e)}")


# --- GESTIÓN DE SUSCRIPCIONES (SOLO SUPER_ADMIN) Y CONSULTA DE ESTADO ---

@app.get("/subscription/current", dependencies=[Depends(allow_exporter)])
def get_current_org_subscription(current_user: dict = Depends(get_current_user)):
    """Devuelve el estado de suscripción y créditos de la organización activa en sesión."""
    active_org_id = current_user.get("organization_id")
    if not active_org_id:
        return {"has_subscription": False, "subscription": None}

    res = supabase.table("company_subscriptions")\
        .select("*")\
        .eq("organization_id", active_org_id)\
        .limit(1)\
        .execute()

    if not res or not res.data:
        return {"has_subscription": False, "subscription": None}

    sub = res.data[0]
    allocated = int(sub.get("credits_allocated") or 0)
    used = int(sub.get("credits_used") or 0)
    return {
        "has_subscription": True,
        "subscription": {
            **sub,
            "credits_remaining": max(0, allocated - used)
        }
    }

@app.get("/subscriptions", dependencies=[Depends(allow_super_admin)])
def list_subscriptions():
    res = supabase.table("company_subscriptions").select("*, organizations(name, nit)").execute()
    return {"subscriptions": res.data or [], "data": res.data or []}

@app.post("/subscriptions", dependencies=[Depends(allow_super_admin)])
def create_subscription(sub: SubscriptionSchema):
    if not sub.organization_id:
        raise HTTPException(status_code=422, detail="Relación requerida: organization_id es obligatorio.")

    today_str = date.today().isoformat()
    end_str = (date.today() + timedelta(days=30)).isoformat()

    payload = {
        "organization_id": sub.organization_id,
        "plan_name": sub.plan_name.upper().strip(),
        "credits_allocated": sub.credits_allocated,
        "credits_used": sub.credits_used or 0,
        "monthly_fee": sub.monthly_fee,
        "billing_cycle": sub.billing_cycle.upper().strip(),
        "start_date": sub.start_date or today_str,
        "end_date": sub.end_date or end_str,
        "is_active": sub.is_active
    }

    try:
        res = supabase.table("company_subscriptions").insert(payload).execute()
        return {"success": True, "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error registrando suscripción: {str(e)}")

@app.put("/subscriptions/{sub_id}", dependencies=[Depends(allow_super_admin)])
def update_subscription(sub_id: str, sub: SubscriptionSchema):
    update_payload = {
        "organization_id": sub.organization_id,
        "plan_name": sub.plan_name.upper().strip(),
        "credits_allocated": sub.credits_allocated,
        "credits_used": sub.credits_used if sub.credits_used is not None else 0,
        "monthly_fee": sub.monthly_fee,
        "billing_cycle": sub.billing_cycle.upper().strip(),
        "is_active": sub.is_active
    }
    if sub.start_date:
        update_payload["start_date"] = sub.start_date
    if sub.end_date:
        update_payload["end_date"] = sub.end_date

    try:
        res = supabase.table("company_subscriptions").update(update_payload).eq("id", sub_id).execute()
        return {"success": True, "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando suscripción: {str(e)}")

@app.delete("/subscriptions/{sub_id}", dependencies=[Depends(allow_super_admin)])
def delete_subscription(sub_id: str):
    try:
        supabase.table("company_subscriptions").delete().eq("id", sub_id).execute()
        return {"success": True, "message": "Suscripción eliminada"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando suscripción: {str(e)}")


# --- MÓDULO DE FACTURACIÓN SAAS A CLIENTES (EXCLUSIVO SUPER_ADMIN) ---

@app.get("/billing/summary", dependencies=[Depends(allow_super_admin)])
def get_saas_billing_summary():
    """
    Consolida para el SUPER_ADMIN el estado comercial, consumo de créditos y valor a facturar
    de todas las organizaciones registradas en la plataforma.
    """
    orgs_res = supabase.table("organizations").select("*").order("name").execute()
    subs_res = supabase.table("company_subscriptions").select("*").order("id", desc=True).execute()
    inv_res = supabase.table("invoices").select("id, organization_id, status, payable_amount").execute()

    orgs = orgs_res.data or []
    subs = subs_res.data or []
    invoices = inv_res.data or []

    billing_rows = []
    total_mrr = 0.0
    total_invoices_caused = 0

    for org in orgs:
        org_id = org["id"]
        org_subs = [s for s in subs if s.get("organization_id") == org_id]
        active_sub = next((s for s in org_subs if s.get("is_active")), org_subs[0] if org_subs else None)

        org_invoices = [i for i in invoices if i.get("organization_id") == org_id]
        parsed_count = len([i for i in org_invoices if i.get("status") == "PARSEADO"])
        caused_count = len([i for i in org_invoices if i.get("status") == "CAUSADO"])
        total_org_invoices = len(org_invoices)

        credits_allocated = int(active_sub.get("credits_allocated") or 0) if active_sub else 0
        credits_used = int(active_sub.get("credits_used") or 0) if active_sub else 0
        credits_remaining = max(0, credits_allocated - credits_used)
        monthly_fee = float(active_sub.get("monthly_fee") or 0.0) if active_sub else 0.0
        plan_name = active_sub.get("plan_name", "SIN PLAN") if active_sub else "SIN PLAN"
        is_active = bool(active_sub.get("is_active")) if active_sub else False
        end_date = active_sub.get("end_date") if active_sub else None

        if is_active:
            total_mrr += monthly_fee
        total_invoices_caused += caused_count

        billing_rows.append({
            "organization_id": org_id,
            "organization_name": org["name"],
            "organization_nit": org["nit"],
            "subscription_id": active_sub["id"] if active_sub else None,
            "plan_name": plan_name,
            "is_active": is_active,
            "credits_allocated": credits_allocated,
            "credits_used": credits_used,
            "credits_remaining": credits_remaining,
            "invoices_parsed": parsed_count,
            "invoices_caused": caused_count,
            "invoices_total": total_org_invoices,
            "monthly_fee": monthly_fee,
            "billing_cycle": active_sub.get("billing_cycle", "MONTHLY") if active_sub else "-",
            "end_date": end_date,
            "billing_status": "AL DÍA / FACTURABLE" if is_active else "SIN SUSCRIPCIÓN ACTIVA"
        })

    return {
        "kpis": {
            "total_organizations": len(orgs),
            "active_subscriptions": len([r for r in billing_rows if r["is_active"]]),
            "total_mrr": total_mrr,
            "total_invoices_caused": total_invoices_caused
        },
        "organizations_billing": billing_rows
    }


# --- GESTIÓN DE USUARIOS CON JERARQUÍA ESTRICTA ---

@app.get("/auth/users", dependencies=[Depends(allow_company_admin)])
def list_users_by_org(current_user: dict = Depends(get_current_user)):
    active_org_id = current_user.get("organization_id")
    query = supabase.table("users_profile").select("*")
    if active_org_id:
        query = query.eq("organization_id", active_org_id)
    res = query.order("full_name").execute()
    return {"users": res.data or [], "data": res.data or []}

@app.post("/auth/users", dependencies=[Depends(allow_company_admin)])
def create_sub_user(user_data: RegisterUserSchema, current_user: dict = Depends(get_current_user)):
    target_org = current_user.get("organization_id") or user_data.organization_id
    creator_role = current_user.get("role")

    if not target_org:
        raise HTTPException(status_code=422, detail="Relación requerida: El usuario debe tener asignado un organization_id.")

    if creator_role == "SUPER_ADMIN":
        allowed_roles = ["COMPANY_ADMIN", "COMPANY_OPERATOR", "COMPANY_EXPORTER"]
    elif creator_role == "COMPANY_ADMIN":
        allowed_roles = ["COMPANY_OPERATOR", "COMPANY_EXPORTER"]
    else:
        allowed_roles = []

    if user_data.role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail=f"Jerarquía no permitida: Un {creator_role} solo puede crear usuarios con rol {', '.join(allowed_roles)}."
        )

    try:
        auth_res = supabase.auth.admin.create_user({
            "email": user_data.email.lower().strip(),
            "password": user_data.password,
            "email_confirm": True
        })
        new_user_id = auth_res.user.id
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creando autenticación del usuario: {str(e)}")

    payload = {
        "id": new_user_id,
        "full_name": user_data.full_name,
        "email": user_data.email.lower().strip(),
        "role": user_data.role,
        "organization_id": target_org,
        "is_active": True
    }

    try:
        res = supabase.table("users_profile").insert(payload).execute()
        return {"success": True, "message": "Usuario creado y asociado a la organización exitosamente.", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando perfil de usuario: {str(e)}")

@app.put("/auth/users/{user_id}", dependencies=[Depends(allow_company_admin)])
def update_sub_user(user_id: str, user_data: UpdateUserSchema, current_user: dict = Depends(get_current_user)):
    creator_role = current_user.get("role")
    if creator_role == "SUPER_ADMIN":
        allowed_roles = ["COMPANY_ADMIN", "COMPANY_OPERATOR", "COMPANY_EXPORTER"]
    elif creator_role == "COMPANY_ADMIN":
        allowed_roles = ["COMPANY_OPERATOR", "COMPANY_EXPORTER"]
    else:
        allowed_roles = []

    if user_data.role not in allowed_roles and user_id != current_user.get("sub"):
        raise HTTPException(
            status_code=403,
            detail=f"Jerarquía no permitida: Un {creator_role} no puede asignar el rol {user_data.role}."
        )

    try:
        res = supabase.table("users_profile").update({
            "full_name": user_data.full_name,
            "email": user_data.email.lower().strip(),
            "role": user_data.role,
            "is_active": user_data.is_active
        }).eq("id", user_id).execute()

        if user_data.password and user_data.password.strip():
            supabase.auth.admin.update_user_by_id(user_id, {"password": user_data.password.strip()})

        return {"success": True, "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando usuario: {str(e)}")

@app.delete("/auth/users/{user_id}", dependencies=[Depends(allow_company_admin)])
def delete_sub_user(user_id: str, current_user: dict = Depends(get_current_user)):
    if user_id == current_user.get("sub"):
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propio usuario mientras tienes sesión abierta.")
    try:
        supabase.table("users_profile").delete().eq("id", user_id).execute()
        supabase.auth.admin.delete_user(user_id)
        return {"success": True, "message": "Usuario eliminado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando usuario: {str(e)}")


# --- GESTIÓN DE PARÁMETROS CONTABLES PUC / DIAN (SUPER_ADMIN Y COMPANY_ADMIN) ---

@app.get("/accounting-parameters", dependencies=[Depends(allow_company_admin)])
def list_accounting_parameters(tipo_documento: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    active_org_id = current_user.get("organization_id")
    if not active_org_id:
        return {"parameters": [], "data": []}
    query = supabase.table("company_accounting_parameters")\
        .select("*")\
        .eq("organization_id", active_org_id)
    if tipo_documento and tipo_documento != "ALL":
        query = query.eq("tipo_documento", tipo_documento.strip())
    res = query.order("concept_code").execute()
    return {"parameters": res.data or [], "data": res.data or []}

@app.post("/accounting-parameters", dependencies=[Depends(allow_company_admin)])
def create_accounting_parameter(param: AccountingParameterSchema, current_user: dict = Depends(get_current_user)):
    target_org = current_user.get("organization_id") or param.organization_id
    if not target_org:
        raise HTTPException(status_code=422, detail="Relación requerida: organization_id es obligatorio.")
    doc_type = (param.tipo_documento or "").strip()
    if doc_type not in ("01", "91", "92"):
        raise HTTPException(status_code=422, detail="Debe filtrar/seleccionar un tipo_documento válido ('01', '91' o '92') antes de insertar.")

    payload = {
        "organization_id": target_org,
        "tipo_documento": doc_type,
        "concept_code": param.concept_code.upper().strip(),
        "concept_name": param.concept_name.strip(),
        "account_puc": param.account_puc.strip(),
        "account_name": param.account_name.strip(),
        "nature": param.nature.upper().strip()
    }
    try:
        res = supabase.table("company_accounting_parameters").insert(payload).execute()
        return {"success": True, "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando parámetro contable: {str(e)}")

@app.put("/accounting-parameters/{param_id}", dependencies=[Depends(allow_company_admin)])
def update_accounting_parameter(param_id: str, param: AccountingParameterSchema, tipo_documento: Optional[str] = None):
    doc_type = (param.tipo_documento or tipo_documento or "").strip()
    if doc_type not in ("01", "91", "92"):
        raise HTTPException(status_code=422, detail="Debe filtrar/seleccionar un tipo_documento válido ('01', '91' o '92') antes de modificar.")
    try:
        res = supabase.table("company_accounting_parameters").update({
            "tipo_documento": doc_type,
            "concept_code": param.concept_code.upper().strip(),
            "concept_name": param.concept_name.strip(),
            "account_puc": param.account_puc.strip(),
            "account_name": param.account_name.strip(),
            "nature": param.nature.upper().strip()
        }).eq("id", param_id).eq("tipo_documento", doc_type).execute()
        return {"success": True, "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando parámetro contable: {str(e)}")

@app.delete("/accounting-parameters/{param_id}", dependencies=[Depends(allow_company_admin)])
def delete_accounting_parameter(param_id: str, tipo_documento: Optional[str] = None):
    try:
        query = supabase.table("company_accounting_parameters").delete().eq("id", param_id)
        if tipo_documento and tipo_documento != "ALL":
            query = query.eq("tipo_documento", tipo_documento.strip())
        query.execute()
        return {"success": True, "message": "Parámetro contable eliminado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando parámetro contable: {str(e)}")
        
# ============================================================================
# GESTIÓN DE CÓDIGOS UNSPSC Y CUENTAS SUGERIDAS (MAESTRO GLOBAL)
# ============================================================================

@app.get("/unspsc-master", dependencies=[Depends(allow_company_admin)])
def list_unspsc_master(tipo_documento: Optional[str] = None):
    try:
        query = supabase.table("unspsc").select("*")
        if tipo_documento and tipo_documento != "ALL":
            query = query.eq("tipo_documento", tipo_documento.strip())
        res = query.order("code").execute()
        return {"data": res.data or [], "unspsc": res.data or []}
    except Exception as e:
        return {"data": [], "unspsc": []}

@app.post("/unspsc-master", dependencies=[Depends(allow_super_admin)])
def create_unspsc_item(item: UnspscSchema):
    doc_type = (item.tipo_documento or "").strip()
    if doc_type not in ("01", "91", "92"):
        raise HTTPException(status_code=422, detail="Debe filtrar/seleccionar un tipo_documento válido ('01', '91' o '92') antes de insertar en UNSPSC.")
    try:
        payload = {
            "tipo_documento": doc_type,
            "code": item.code.strip(),
            "description": item.description.strip(),
            "category_type": item.category_type.upper().strip(),
            "suggested_puc_account": item.suggested_puc_account.strip(),
            "suggested_tipmov": (item.suggested_tipmov or ("C" if doc_type == "91" else "D")).upper().strip()
        }
        res = supabase.table("unspsc").insert(payload).execute()
        return {"success": True, "message": "Código UNSPSC registrado exitosamente", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error registrando UNSPSC: {str(e)}")

@app.put("/unspsc-master/{item_id}", dependencies=[Depends(allow_super_admin)])
def update_unspsc_item(item_id: str, item: UnspscSchema, tipo_documento: Optional[str] = None):
    doc_type = (item.tipo_documento or tipo_documento or "").strip()
    if doc_type not in ("01", "91", "92"):
        raise HTTPException(status_code=422, detail="Debe filtrar/seleccionar un tipo_documento válido ('01', '91' o '92') antes de modificar UNSPSC.")
    try:
        payload = {
            "tipo_documento": doc_type,
            "code": item.code.strip(),
            "description": item.description.strip(),
            "category_type": item.category_type.upper().strip(),
            "suggested_puc_account": item.suggested_puc_account.strip(),
            "suggested_tipmov": (item.suggested_tipmov or ("C" if doc_type == "91" else "D")).upper().strip()
        }
        res = supabase.table("unspsc").update(payload).eq("id", item_id).eq("tipo_documento", doc_type).execute()
        return {"success": True, "message": "Código UNSPSC actualizado", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando UNSPSC: {str(e)}")

@app.delete("/unspsc-master/{item_id}", dependencies=[Depends(allow_super_admin)])
def delete_unspsc_item(item_id: str, tipo_documento: Optional[str] = None):
    try:
        query = supabase.table("unspsc").delete().eq("id", item_id)
        if tipo_documento and tipo_documento != "ALL":
            query = query.eq("tipo_documento", tipo_documento.strip())
        query.execute()
        return {"success": True, "message": "Código UNSPSC eliminado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando UNSPSC: {str(e)}")

# --- GESTIÓN CRUD COMPLETO DE INTEGRACIONES DE CORREO IMAP (company_email_integrations) ---

@app.get("/email-integrations", dependencies=[Depends(allow_company_admin)])
def list_email_integrations(current_user: dict = Depends(get_current_user)):
    active_org_id = current_user.get("organization_id")
    if not active_org_id:
        return {"integrations": [], "data": []}
    res = supabase.table("company_email_integrations")\
        .select("*")\
        .eq("organization_id", active_org_id)\
        .order("direction")\
        .execute()
    return {"integrations": res.data or [], "data": res.data or []}

@app.post("/email-integrations", dependencies=[Depends(allow_company_admin)])
def create_email_integration(config: EmailConfigSchema, current_user: dict = Depends(get_current_user)):
    target_org = current_user.get("organization_id") or config.organization_id
    if not target_org:
        raise HTTPException(status_code=422, detail="Relación requerida: organization_id es obligatorio.")
    if not config.email_password or not config.email_password.strip():
        raise HTTPException(status_code=422, detail="La contraseña o App Password IMAP es obligatoria.")

    payload = {
        "organization_id": target_org,
        "direction": config.direction.upper().strip(),
        "imap_server": config.imap_server.strip(),
        "imap_port": config.imap_port,
        "email_account": config.email_account.strip(),
        "email_password": config.email_password.strip(),
        "folder_name": config.folder_name.strip() or "INBOX",
        "scan_frequency_minutes": config.scan_frequency_minutes,
        "is_active": config.is_active
    }
    try:
        res = supabase.table("company_email_integrations").insert(payload).execute()
        return {"success": True, "message": "Integración IMAP creada exitosamente.", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando integración IMAP: {str(e)}")

@app.put("/email-integrations/{integration_id}", dependencies=[Depends(allow_company_admin)])
def update_email_integration(integration_id: str, config: EmailConfigSchema):
    update_payload = {
        "direction": config.direction.upper().strip(),
        "imap_server": config.imap_server.strip(),
        "imap_port": config.imap_port,
        "email_account": config.email_account.strip(),
        "folder_name": config.folder_name.strip() or "INBOX",
        "scan_frequency_minutes": config.scan_frequency_minutes,
        "is_active": config.is_active
    }
    if config.email_password and config.email_password.strip():
        update_payload["email_password"] = config.email_password.strip()

    try:
        res = supabase.table("company_email_integrations")\
            .update(update_payload)\
            .eq("id", integration_id)\
            .execute()
        return {"success": True, "message": "Integración IMAP actualizada.", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando integración IMAP: {str(e)}")

@app.delete("/email-integrations/{integration_id}", dependencies=[Depends(allow_company_admin)])
def delete_email_integration(integration_id: str):
    try:
        supabase.table("company_email_integrations").delete().eq("id", integration_id).execute()
        return {"success": True, "message": "Integración IMAP eliminada"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando integración IMAP: {str(e)}")

@app.post("/organization/{organization_id}/email-config", dependencies=[Depends(allow_company_admin)])
def save_email_config(organization_id: str, config: EmailConfigSchema, current_user: dict = Depends(get_current_user)):
    if not organization_id:
        raise HTTPException(status_code=422, detail="Relación requerida: organization_id es obligatorio.")

    if current_user.get("role") != "SUPER_ADMIN" and current_user.get("organization_id") != organization_id:
        raise HTTPException(status_code=403, detail="No tiene permisos para gestionar la organización solicitada.")

    payload = {
        "organization_id": organization_id,
        "direction": config.direction.upper(),
        "imap_server": config.imap_server,
        "imap_port": config.imap_port,
        "email_account": config.email_account,
        "email_password": config.email_password,
        "folder_name": config.folder_name,
        "scan_frequency_minutes": config.scan_frequency_minutes,
        "is_active": config.is_active
    }

    try:
        res = supabase.table("company_email_integrations").upsert(
            payload, on_conflict="organization_id, direction"
        ).execute()
        return {"success": True, "message": "Configuración IMAP guardada exitosamente.", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al guardar configuración: {str(e)}")


# --- SINCRONIZACIÓN MANUAL IMAP ---

@app.post("/sync-emails", dependencies=[Depends(allow_operator)])
def trigger_manual_email_sync(current_user: dict = Depends(get_current_user)):
    active_org_id = current_user.get("organization_id")
    # Validar suscripción activa antes de intentar sincronizar
    validate_organization_subscription(active_org_id, require_available_credit=True)

    print(f"[MANUAL SYNC] Iniciando sincronización IMAP manual para org={active_org_id}...")
    result = run_scheduled_email_sync(target_org_id=active_org_id)
    if "error" in result:
        raise HTTPException(status_code=500, detail=f"Error sincronizando IMAP: {result['error']}")
    return {"success": True, **result}


# --- LISTADO DE FACTURAS DE LA ORGANIZACIÓN ---

@app.get("/invoices", dependencies=[Depends(allow_exporter)])
def list_organization_invoices(current_user: dict = Depends(get_current_user)):
    active_org_id = current_user.get("organization_id")
    if not active_org_id:
        return {"invoices": [], "data": []}
    try:
        res = supabase.table("invoices")\
            .select("*")\
            .eq("organization_id", active_org_id)\
            .order("created_at", desc=True)\
            .execute()
        return {"invoices": res.data or [], "data": res.data or []}
    except Exception as e:
        print(f"[ERROR INVOICES LIST] {str(e)}")
        return {"invoices": [], "data": []}


# --- INGESTA, CAUSACIÓN & EXPORTACIÓN ---

@app.post("/upload-xml", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_xml(
    organization_id: str = Form(...),
    direction: str = Form("RECIBIDA"),
    file: UploadFile = File(...)
):
    print(f"[UPLOAD XML] Recibiendo archivo '{file.filename}' para org={organization_id}, direction={direction}")

    # Bloqueo estricto si la organización no tiene suscripción activa con créditos
    validate_organization_subscription(organization_id, require_available_credit=True)

    if not (file.filename.endswith('.xml') or file.filename.endswith('.zip')):
        print(f"[UPLOAD XML ERROR 400] Extensión inválida: {file.filename}")
        raise HTTPException(status_code=400, detail="Extensión no permitida (.xml o .zip).")

    try:
        content = await file.read()
        parser = DianXmlParser(content)
        parsed_data = parser.parse()
        print(f"[UPLOAD XML PARSED] CUFE={parsed_data.cufe} | Num={parsed_data.full_number} | Emisor={parsed_data.issuer_nit}")
    except Exception as e:
        print(f"[UPLOAD XML ERROR 422 PARSER] Archivo '{file.filename}': {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=422, detail=f"Error parseando XML: {str(e)}")

    try:
        existing = supabase.table("invoices").select("id").eq("cufe", parsed_data.cufe).execute()
        if existing.data:
            print(f"[UPLOAD XML ERROR 409 DUPLICADO] CUFE ya existe: {parsed_data.cufe}")
            raise HTTPException(status_code=409, detail=f"CUFE duplicado: {parsed_data.cufe}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[UPLOAD XML ERROR 500 DB CHECK] {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error de base de datos verificando CUFE: {str(e)}")

    invoice_payload = {
        "organization_id": organization_id,
        "direction": direction.upper(),
        "document_type": parsed_data.document_type,
        "cufe": parsed_data.cufe,
        "billing_reference": getattr(parsed_data, 'billing_reference', None),
        "prefix": parsed_data.prefix,
        "number": parsed_data.number,
        "full_number": parsed_data.full_number,
        "issue_date": parsed_date if (parsed_date := getattr(parsed_data, 'issue_date', None)) else "2026-01-01",
        "issue_time": parsed_data.issue_time,
        "issuer_nit": parsed_data.issuer_nit,
        "issuer_name": parsed_data.issuer_name,
        "receiver_nit": parsed_data.receiver_nit,
        "receiver_name": parsed_data.receiver_name,
        "currency": parsed_data.currency,
        "line_extension_amount": parsed_data.line_extension_amount,
        "tax_exclusive_amount": parsed_data.tax_exclusive_amount,
        "tax_inclusive_amount": parsed_data.tax_inclusive_amount,
        "payable_amount": parsed_data.payable_amount,
        "classification": "PENDIENTE",
        "status": "PARSEADO",
        "raw_xml_url": f"https://storage.tu-saas.com/{organization_id}/{file.filename}"
    }

    try:
        invoice_res = supabase.table("invoices").insert(invoice_payload).execute()
        invoice_id = invoice_res.data[0]["id"]
        print(f"[UPLOAD XML DB OK] Factura insertada con ID={invoice_id}")

        if parsed_data.items:
            items_payload = [{
                "invoice_id": invoice_id, "line_number": item.line_number,
                "seller_item_id": item.seller_item_id, "unspsc_code": item.unspsc_code,
                "description": item.description, "quantity": item.quantity,
                "unit_price": item.unit_price, "subtotal": item.subtotal
            } for item in parsed_data.items]
            supabase.table("invoice_items").insert(items_payload).execute()

        if parsed_data.taxes:
            taxes_payload = []
            invoice_base = float(getattr(parsed_data, 'line_extension_amount', 0.0) or getattr(parsed_data, 'tax_exclusive_amount', 0.0) or 0.0)
            
            from collections import defaultdict
            tax_groups = defaultdict(list)
            
            for tax in parsed_data.taxes:
                if isinstance(tax, dict):
                    t_type = str(tax.get("tax_type") or tax.get("type", "")).upper()
                    t_percent = float(tax.get("percent", 0.0) or 0.0)
                    t_taxable = float(tax.get("taxable_amount", 0.0) or 0.0)
                    t_amount = float(tax.get("tax_amount", 0.0) or 0.0)
                else:
                    t_type = str(getattr(tax, "tax_type", getattr(tax, "type", ""))).upper()
                    t_percent = float(getattr(tax, "percent", 0.0) or 0.0)
                    t_taxable = float(getattr(tax, "taxable_amount", 0.0) or 0.0)
                    t_amount = float(getattr(tax, "tax_amount", 0.0) or 0.0)

                if not t_type:
                    continue

                tax_groups[(t_type, t_percent)].append({
                    "invoice_id": invoice_id,
                    "type": t_type,
                    "percent": t_percent,
                    "taxable_amount": round(t_taxable, 4),
                    "tax_amount": round(t_amount, 4)
                })

            # Evaluar cada grupo de impuesto de forma inteligente
            for (t_type, t_percent), entries in tax_groups.items():
                # Buscar si alguna entrada cubre el total global de la factura (con tolerancia de 1 unidad por redondeo)
                header_entry = next((e for e in entries if invoice_base > 0 and abs(e["taxable_amount"] - invoice_base) < 1.0), None)
                
                if header_entry:
                    # Si existe el global de cabecera, usamos solo ese y descartamos el ruido de líneas
                    taxes_payload.append(header_entry)
                else:
                    # Si no hay uno global, conservamos los subtotales parciales independientes (ej. factura 37725)
                    seen_signatures = set()
                    for entry in entries:
                        sig = (entry["type"], entry["percent"], entry["taxable_amount"], entry["tax_amount"])
                        if sig not in seen_signatures:
                            seen_signatures.add(sig)
                            taxes_payload.append(entry)

            if taxes_payload:
                print(f"[UPLOAD XML] Insertando {len(taxes_payload)} impuestos optimizados de cabecera.")
                supabase.table("invoice_taxes").insert(taxes_payload).execute()
                
    except Exception as e:
        print(f"[UPLOAD XML ERROR 500 INSERT SUPABASE] Archivo '{file.filename}': {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error insertando factura relacional: {str(e)}")

    return UploadResponse(
        success=True, message="Factura vinculada a la organización exitosamente.",
        invoice_id=invoice_id, cufe=parsed_data.cufe,
        full_number=parsed_data.full_number, payable_amount=parsed_data.payable_amount,
        items_count=len(parsed_data.items), taxes_count=len(parsed_data.taxes)
    )


def _execute_single_invoice_causation(invoice_id: str, grouping_mode: GroupingMode) -> JournalEntryResponse:
    inv_res = supabase.table("invoices").select("*").eq("id", invoice_id).execute()
    if not inv_res.data:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    invoice = inv_res.data[0]
    org_id = invoice["organization_id"]

    # Validar suscripción y cupo disponible
    sub = validate_organization_subscription(org_id, require_available_credit=True)

    doc_type = str(invoice.get("document_type") or invoice.get("tipo_documento") or "01").strip()

    # 1. Cargar parámetros contables de la organización conservando tipo_documento
    params_res = supabase.table("company_accounting_parameters").select("*").eq("organization_id", org_id).execute()
    company_params: Dict[str, Dict[str, str]] = {}
    if params_res.data:
        for row in params_res.data:
            concept = str(row["concept_code"]).strip()
            row_doc = str(row.get("tipo_documento") or "").strip()
            entry = {
                "account": row["account_puc"],
                "name": row["account_name"],
                "nature": row.get("nature", ""),
                "tipo_documento": row_doc,
            }
            if row_doc:
                company_params[f"{concept}_{row_doc}"] = entry
                if row_doc == doc_type or concept not in company_params:
                    company_params[concept] = entry
            else:
                company_params[concept] = entry

    # 2. Cargar reglas de excepción por NIT desde la tabla 'companies'
    rules_res = supabase.table("companies").select("*").eq("organization_id", org_id).execute()
    provider_rules: Dict[str, Dict[str, str]] = {}
    if rules_res.data:
        for row in rules_res.data:
            nit_val = (row.get("nit") or "").strip()
            unspsc_val = (row.get("unspsc") or "").strip()
            row_doc = str(row.get("tipo_documento") or "").strip()
            if nit_val and unspsc_val:
                if not row_doc or row_doc == doc_type or nit_val not in provider_rules:
                    provider_rules[nit_val] = {
                        "unspsc_code": unspsc_val,
                        "tipo_documento": row_doc,
                    }

    # 3. Cargar el maestro global UNSPSC preservando tipo_documento y suggested_tipmov
    unspsc_res = supabase.table("unspsc").select("*").execute()
    unspsc_master: Dict[str, Dict[str, str]] = {}
    if unspsc_res.data:
        for row in unspsc_res.data:
            code_str = str(row["code"]).strip()
            row_doc = str(row.get("tipo_documento") or "").strip()
            payload_unspsc = {
                "code": code_str,
                "category_type": row["category_type"],
                "suggested_puc_account": row["suggested_puc_account"],
                "suggested_tipmov": row.get("suggested_tipmov", ""),
                "description": row["description"],
                "tipo_documento": row_doc,
            }
            if row_doc:
                unspsc_master[f"{code_str}_{row_doc}"] = payload_unspsc
                if row_doc == doc_type or code_str not in unspsc_master:
                    unspsc_master[code_str] = payload_unspsc
            else:
                unspsc_master[code_str] = payload_unspsc

    items_res = supabase.table("invoice_items").select("*").eq("invoice_id", invoice_id).execute()
    taxes_res = supabase.table("invoice_taxes").select("*").eq("invoice_id", invoice_id).execute()

    items_data = items_res.data or []
    taxes_data = taxes_res.data or []

    # 4. Instanciar el motor con el maestro UNSPSC y reglas integradas
    engine = PucAccountingEngine(
        company_parameters=company_params,
        provider_rules=provider_rules,
        unspsc_master=unspsc_master
    )

    journal_entry = engine.generate_journal_entry(
        invoice_id=invoice["id"],
        full_number=invoice["full_number"],
        document_type=doc_type,
        tipo_documento=doc_type,
        issuer_nit=invoice["issuer_nit"],
        issuer_name=invoice["issuer_name"],
        line_extension_amount=invoice["line_extension_amount"],
        payable_amount=invoice["payable_amount"],
        items=items_data,
        taxes=taxes_data,
        mode=grouping_mode
    )
    
    # --- PERSISTIR CUENTAS RESUELTAS EN CADA ÍTEM (invoice_items) ---
    if grouping_mode == GroupingMode.CONSOLIDATED:
        primary_acc = journal_entry.resolved_purchase_accounts_audit[0]['account'] if journal_entry.resolved_purchase_accounts_audit else None
        for item in items_data:
            if primary_acc:
                supabase.table("invoice_items").update({
                    "puc_account_debit": primary_acc,
                    "puc_account_credit": None
                }).eq("id", item["id"]).execute()
    else:
        # Modo detallado: Asignar la cuenta específica calculada por línea/UNSPSC
        for idx, item in enumerate(items_data):
            if idx < len(journal_entry.resolved_purchase_accounts_audit):
                line_acc = journal_entry.resolved_purchase_accounts_audit[idx]['account']
                supabase.table("invoice_items").update({
                    "puc_account_debit": line_acc,
                    "puc_account_credit": None
                }).eq("id", item["id"]).execute()

    # --- PERSISTIR CUENTAS RESUELTAS EN CADA IMPUESTO (invoice_taxes) ---
    for tax in taxes_data:
        t_type = str(tax.get('type', '')).upper()
        t_percent = float(tax.get('percent', 0.0))
        
        matching_res = next((t for t in journal_entry.resolved_taxes if t['type'] == t_type and t['percent'] == t_percent), None)
        if matching_res:
            acc = matching_res['account']
            update_data = {}
            if t_type in ['RETEFUENTE', 'RETEIVA', 'RETEICA']:
                update_data["puc_account_debit"] = None
                update_data["puc_account_credit"] = acc
            else:
                update_data["puc_account_debit"] = acc
                update_data["puc_account_credit"] = None
                
            supabase.table("invoice_taxes").update(update_data).eq("id", tax["id"]).execute()

    # --- PERSISTENCIA EN EL LIBRO DIARIO (journal_lines) ---
    supabase.table("journal_lines").delete().eq("invoice_id", invoice_id).execute()

    journal_records = []
    for l in journal_entry.lines:
        journal_records.append({
            "organization_id": org_id,
            "invoice_id": invoice["id"],
            "account_code": l.account_puc,
            "account_name": l.account_name,
            "third_party_nit": l.third_party_nit,
            "description": l.description,
            "debit": float(l.debit),
            "credit": float(l.credit)
        })

    if journal_records:
        supabase.table("journal_lines").insert(journal_records).execute()

    supabase.table("invoices").update({"status": "CAUSADO"}).eq("id", invoice_id).execute()

    if invoice.get("status") != "CAUSADO":
        consume_subscription_credit(sub, credits_to_consume=1)

    return JournalEntryResponse(
        invoice_id=journal_entry.invoice_id,
        full_number=journal_entry.full_number,
        grouping_mode=journal_entry.grouping_mode.value,
        total_debit=journal_entry.total_debit,
        total_credit=journal_entry.total_credit,
        is_balanced=journal_entry.is_balanced,
        lines=[
            AccountingLineResponse(
                account_puc=l.account_puc,
                account_name=l.account_name,
                third_party_nit=l.third_party_nit,
                third_party_name=l.third_party_name,
                debit=l.debit,
                credit=l.credit,
                description=l.description
            ) for l in journal_entry.lines
        ]
    )
    
@app.post("/causar-factura/{invoice_id}", response_model=JournalEntryResponse, dependencies=[Depends(allow_operator)])
def causar_factura(invoice_id: str, grouping_mode: GroupingMode = GroupingMode.CONSOLIDATED):
    return _execute_single_invoice_causation(invoice_id, grouping_mode)

@app.get("/invoices/{invoice_id}/journal", response_model=JournalEntryResponse, dependencies=[Depends(allow_exporter)])
def get_invoice_journal(invoice_id: str):
    inv_res = supabase.table("invoices").select("*").eq("id", invoice_id).execute()
    if not inv_res.data:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    invoice = inv_res.data[0]

    lines_res = supabase.table("journal_lines").select("*").eq("invoice_id", invoice_id).execute()
    lines_data = lines_res.data or []

    total_debit = sum(float(l.get("debit", 0)) for l in lines_data)
    total_credit = sum(float(l.get("credit", 0)) for l in lines_data)
    is_balanced = round(total_debit, 2) == round(total_credit, 2)

    accounting_lines = [
        AccountingLineResponse(
            account_puc=l.get("account_code"),
            account_name=l.get("account_name"),
            third_party_nit=l.get("third_party_nit"),
            third_party_name=invoice.get("issuer_name", ""),
            debit=float(l.get("debit", 0)),
            credit=float(l.get("credit", 0)),
            description=l.get("description", "")
        ) for l in lines_data
    ]

    return JournalEntryResponse(
        invoice_id=invoice["id"],
        full_number=invoice["full_number"],
        grouping_mode="CONSOLIDATED",
        total_debit=total_debit,
        total_credit=total_credit,
        is_balanced=is_balanced,
        lines=accounting_lines
    )

@app.get("/invoices/{invoice_id}/details", dependencies=[Depends(allow_exporter)])
def get_invoice_details(invoice_id: str):
    """Devuelve la cabecera, ítems e impuestos de una factura para el visor detallado."""
    inv_res = supabase.table("invoices").select("*").eq("id", invoice_id).execute()
    if not inv_res.data:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    invoice = inv_res.data[0]

    items_res = supabase.table("invoice_items").select("*").eq("invoice_id", invoice_id).execute()
    taxes_res = supabase.table("invoice_taxes").select("*").eq("invoice_id", invoice_id).execute()

    return {
        "invoice": invoice,
        "items": items_res.data or [],
        "taxes": taxes_res.data or []
    }

@app.post("/causar-masivo", dependencies=[Depends(allow_operator)])
def causar_facturas_masivo(payload: BatchCausarSchema):
    results = []
    errors = []
    for inv_id in payload.invoice_ids:
        try:
            entry = _execute_single_invoice_causation(inv_id, payload.grouping_mode)
            results.append(entry)
        except HTTPException as he:
            errors.append({"invoice_id": inv_id, "detail": he.detail})
            if he.status_code == 402:
                break
        except Exception as e:
            errors.append({"invoice_id": inv_id, "detail": str(e)})

    return {
        "success": len(results) > 0,
        "caused_count": len(results),
        "errors_count": len(errors),
        "results": results,
        "errors": errors
    }

# --- GESTIÓN DE PLANES DE SUSCRIPCIÓN (SOLO SUPER_ADMIN) ---

@app.get("/subscription-plans", dependencies=[Depends(allow_exporter)])
def get_subscription_plans():
    """Lista todos los planes de suscripción disponibles."""
    try:
        res = supabase.table("subscription_plans").select("*").order("name").execute()
        return {"data": res.data or [], "plans": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listando planes: {str(e)}")

@app.post("/subscription-plans", dependencies=[Depends(allow_super_admin)])
def create_subscription_plan(plan: SubscriptionPlanCreate):
    """Crea un nuevo plan comercial (Requiere rol SUPER_ADMIN)."""
    try:
        payload = plan.dict()
        res = supabase.table("subscription_plans").insert(payload).execute()
        return {"success": True, "message": "Plan creado exitosamente", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando plan: {str(e)}")

@app.put("/subscription-plans/{plan_id}", dependencies=[Depends(allow_super_admin)])
def update_subscription_plan(plan_id: str, plan: SubscriptionPlanUpdate):
    """Actualiza un plan comercial existente."""
    try:
        update_data = {k: v for k, v in plan.dict().items() if v is not None}
        res = supabase.table("subscription_plans").update(update_data).eq("id", plan_id).execute()
        return {"success": True, "message": "Plan actualizado exitosamente", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando plan: {str(e)}")

@app.delete("/subscription-plans/{plan_id}", dependencies=[Depends(allow_super_admin)])
def delete_subscription_plan(plan_id: str):
    """Elimina o inactiva un plan comercial."""
    try:
        supabase.table("subscription_plans").delete().eq("id", plan_id).execute()
        return {"success": True, "message": "Plan eliminado exitosamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando plan: {str(e)}")

@app.get("/export/{target_erp}/{organization_id}", dependencies=[Depends(allow_exporter)])
def export_erp_file(target_erp: str, organization_id: str):
    target = target_erp.lower().strip()
    exporter = ErpExporterEngine(supabase_client=supabase)

    try:
        if target == "siigo":
            content = exporter.export_siigo(organization_id)
            filename = f"Importacion_Siigo_{organization_id[:8]}.xlsx"
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif target == "helisa":
            content = exporter.export_helisa(organization_id)
            filename = f"Importacion_Helisa_{organization_id[:8]}.csv"
            media_type = "text/csv"
        elif target == "loggro":
            content = exporter.export_loggro(organization_id)
            filename = f"Importacion_Loggro_{organization_id[:8]}.xlsx"
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif target == "syscafe":
            content = exporter.export_syscafe(organization_id)
            filename = f"Importacion_SysCafe_{organization_id[:8]}.txt"
            media_type = "text/plain"
        elif target == "alegra":
            content = exporter.export_alegra(organization_id)
            filename = f"Importacion_Alegra_{organization_id[:8]}.xlsx"
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif target == "world_office":
            content = exporter.export_world_office(organization_id)
            filename = f"Importacion_WorldOffice_{organization_id[:8]}.xlsx"
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            raise HTTPException(
                status_code=400,
                detail="ERP no soportado. Las opciones válidas son: siigo, helisa, loggro, syscafe, alegra, world_office"
            )

        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar exportación: {str(e)}")