from fastapi import APIRouter, HTTPException, status
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from pydantic import BaseModel
from jose import jwt
from datetime import timezone, datetime, timedelta
import httpx
from app.schemas import AdminCredential, IntraInfo
from app import SETTINGS
from app.database import DbWrapper




def create_access_token(data: dict, expires_in: int | None = None):
    to_encode = data.copy()
    if expires_in is not None:
        expire = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        to_encode["exp"] = expire
    return jwt.encode(to_encode, SETTINGS.secret_key, algorithm=SETTINGS.algorithm)


class AuthCode(BaseModel):
    code: str

router = APIRouter(prefix="/auth")

@router.post("/42/callback")
async def auth_callback(auth: AuthCode):
    async with httpx.AsyncClient() as client:
        token_url = "https://api.intra.42.fr/oauth/token"
        data = {
            "client_id": SETTINGS.client_id,
            "grant_type": "authorization_code",
            "client_secret": SETTINGS.client_secret,
            "code": auth.code,
            "redirect_uri": SETTINGS.redirect_uri,
        }

        token_response = await client.post(token_url, data=data)

        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to authenticate with 42")
        token_json = token_response.json()

        access_token = token_json.get("access_token", None)
        expires_in = token_json.get("expires_in", None)
        if not access_token:
            return {"error": "Failed to get token from 42"}

        user_res = await client.get(
            "https://api.intra.42.fr/v2/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if user_res.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch user data")
        user = IntraInfo.model_validate(user_res.json())

    DbWrapper.add_player(user)
    jwt_payload = {
        "sub": user.login,
        "is_admin": False
    }

    response = {
        "token": create_access_token(jwt_payload, expires_in),
        "user": user.model_dump()
    }

    return response


@router.post("/login")
def login(credentials: AdminCredential):
    password_hash = DbWrapper.get_admin_credential(credentials.username)
    wrong_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password"
    )

    if password_hash is None:
        raise wrong_credentials
    try:
        PasswordHasher().verify(password_hash, credentials.password)
    except VerifyMismatchError:
        raise wrong_credentials
    return {
        "token": create_access_token(
            {
                "sub": credentials.username,
                "is_admin": True
            }
        )
    }
