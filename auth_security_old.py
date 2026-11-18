import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import Client

# Configuración JWT
SECRET_KEY = "DIAN_SAAS_SECRET_KEY_CHANGE_IN_PRODUCTION_POSSAR_SALES"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # Token válido por 24 horas

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    """Encripta una contraseña en texto plano."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña ingresada coincide con el hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Genera un Token JWT firmado."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decodifica y valida un Token JWT."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="El token ha expirado. Inicie sesión de nuevo.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de autenticación inválido.")


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme)
) -> dict:
    """Extrae y valida el usuario actual desde el Bearer Token HTTP."""
    token = credentials.credentials
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    role = payload.get("role")
    company_id = payload.get("company_id")

    if not user_id or not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Payload de token incompleto.")

    return {
        "user_id": user_id,
        "email": payload.get("email"),
        "role": role,
        "company_id": company_id
    }


class RoleChecker:
    """Guardián de roles para proteger endpoints de FastAPI."""
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in self.allowed_roles and current_user["role"] != "SUPER_ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Se requiere alguno de los siguientes roles: {', '.join(self.allowed_roles)}"
            )
        return current_user


def check_and_deduct_credit(company_id: str, supabase_client: Client) -> bool:
    """Verifica si la empresa tiene créditos disponibles y descuenta 1 por causación."""
    res = supabase_client.table("company_subscriptions").select("*").eq("company_id", company_id).execute()
    if not res.data:
        raise HTTPException(status_code=402, detail="La empresa no cuenta con una suscripción o bolsa de créditos activa.")
    
    sub = res.data[0]
    if sub["subscription_status"] != "ACTIVE":
        raise HTTPException(status_code=402, detail="La suscripción de la empresa está suspendida o vencida.")
    
    available = sub.get("available_credits", 0)
    if available <= 0:
        raise HTTPException(
            status_code=402, 
            detail="Ha agotado sus créditos de causación. Recargue su plan para continuar procesando facturas."
        )

    # Descuenta 1 crédito e incrementa las facturas procesadas
    supabase_client.table("company_subscriptions").update({
        "available_credits": available - 1,
        "total_processed_invoices": sub.get("total_processed_invoices", 0) + 1
    }).eq("id", sub["id"]).execute()

    return True