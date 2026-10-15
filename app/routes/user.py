from fastapi import APIRouter, Depends, status
from starlette.exceptions import HTTPException
from app.database import DbWrapper
from app.schemas import User
from ._tools import verify_user





router = APIRouter(dependencies=[Depends(verify_user)])


@router.get("/player")
def my_info(user: User = Depends(verify_user)):
    if user.is_admin:
        return {}
    plyr = DbWrapper.get_player(user.login)
    if plyr:
        return plyr
    raise HTTPException(status.HTTP_404_NOT_FOUND)

@router.get("/player/{login_or_id}")
def player_info(login_or_id: str):
    plyr = DbWrapper.get_player(
        int(login_or_id) if login_or_id.isnumeric() else login_or_id
    )
    if plyr:
        return plyr
    raise HTTPException(status.HTTP_404_NOT_FOUND)


@router.get("/players/count")
def players_count():
    return {
        "players": DbWrapper.players_count()
    }


@router.get("/players")
def get_players():
    return DbWrapper.get_players()
