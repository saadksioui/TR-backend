from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from fastapi import HTTPException, Depends, status
from app.schemas import User
from app import SETTINGS
from app.models import GameStateTable



def verify_user(token:  HTTPAuthorizationCredentials = Depends(HTTPBearer())) -> User:
    try:
        user = User.model_validate(jwt.decode(token.credentials, SETTINGS.secret_key))
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    return user

def verify_admin(token:  HTTPAuthorizationCredentials = Depends(HTTPBearer())) -> User:
    user = verify_user(token)
    if not user.is_admin:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your not an admin")
    return user


def ensure_game_not_started(db) -> None:
    state = db.get(GameStateTable, 1)
    if state is not None and state.status != "not_started":
        raise HTTPException(status.HTTP_409_CONFLICT, "Reset the game before changing its setup")
