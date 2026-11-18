import os
from datetime import datetime, timedelta
from typing import Optional, List
from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from supabase import Client

# Configuración JWT
SECRET_KEY = "tu_super_secreto_jwt_aqui"  # Reemplazar en prod
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 horas

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role")
        organization_id: str = payload.get("organization_id")
        
        if user_id is None or role is None:
            raise credentials_exception
            
        return {"id": user_id, "role": role, "organization_id": organization_id}
    except JWTError:
        raise credentials_exception

class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: dict = Depends(get_current_user)):
        if user["role"] not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operación no permitida para el rol de este usuario"
            )
        return user

def check_and_deduct_credit(organization_id: str, supabase_client: Client):
    """Verifica y descuenta 1 crédito de causación a la organización."""
    res = supabase_client.table("company_subscriptions").select("*").eq("organization_id", organization_id).eq("is_active", True).execute()
    
    if not res.data:
        raise HTTPException(status_code=403, detail="La organización no tiene una suscripción activa.")
        
    subscription = res.data[0]
    current_credits = subscription.get("credits_allocated", 0)
    
    if current_credits <= 0:
        raise HTTPException(status_code=402, detail="Créditos insuficientes para causar esta factura.")
        
    new_credits = current_credits - 1
    supabase_client.table("company_subscriptions").update({"credits_allocated": new_credits}).eq("id", subscription["id"]).execute()
    return True