from app.database import DbWrapper
from app.models import PuzzleTable, SessionLocal
from app.schemas import Puzzle
from ._tools import ensure_game_not_started, verify_admin
from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy import select
from typing import Annotated
from random import shuffle
from itertools import batched





router = APIRouter(dependencies=[Depends(verify_admin)])


def validate_puzzle_setup(puzzle: Puzzle) -> None:
    with SessionLocal() as db:
        ensure_game_not_started(db)
        if puzzle.is_big_puzzle:
            existing = db.scalar(
                select(PuzzleTable.id).where(PuzzleTable.is_big_puzzle.is_(True))
            )
            if existing is not None and existing != puzzle.id:
                raise HTTPException(status.HTTP_409_CONFLICT, "Only one big puzzle can be configured")


@router.post("/puzzle")
def new_puzzle(puzzle: Puzzle):
    validate_puzzle_setup(puzzle)
    DbWrapper.create_puzzle(puzzle)
    return {"detail": "okay"}



@router.put("/puzzle")
def update_puzzle(puzzle: Puzzle):
    if puzzle.id is None or DbWrapper.get_puzzle(puzzle.id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Puzzle id does not exist")
    validate_puzzle_setup(puzzle)
    DbWrapper.update_puzzle(puzzle)
    return {"detail": "okay"}

@router.post("/teams/create")
def create_teams(n: Annotated[int, Query(ge=2)]):
    with SessionLocal() as db:
        ensure_game_not_started(db)
    DbWrapper.clear_teams()
    players = DbWrapper.get_players()

    if not players:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You have 0 players")

    shuffle(players)

    number_of_teams = len(players) // n + (len(players) % n == n - 1)
    teams = [list(_) for _ in batched(players, n)]
    if len(teams) > 1 and len(teams[-1]) + 1 < n:
        extra_team = teams.pop()
        for i, member in enumerate(extra_team):
            teams[i % len(teams)].append(member)
    DbWrapper.create_teams(teams)
    return number_of_teams
