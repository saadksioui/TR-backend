from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from random import shuffle
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select

from app.models import (
    AuditLogTable,
    GameStateTable,
    PlayerTable,
    PuzzleTable,
    SessionLocal,
    SubmissionTable,
    TeamTable,
)
from app.schemas import GameSettings, TeamReassignment, User
from ._tools import ensure_game_not_started, verify_admin


ADMIN_USER = Depends(verify_admin)
IMAGE_FILE = File(...)
router = APIRouter(dependencies=[ADMIN_USER])
UPLOAD_DIRECTORY = Path(__file__).resolve().parents[2] / "uploads"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_TYPES = {
    "image/jpeg": ("jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
    "image/png": ("png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    "image/webp": ("webp", lambda data: data.startswith(b"RIFF") and data[8:12] == b"WEBP"),
}


def _state(db) -> GameStateTable:
    state = db.get(GameStateTable, 1)
    if state is None:
        state = GameStateTable(id=1)
        db.add(state)
        db.flush()
    return state


def _audit(db, action: str, details: dict, user: User) -> None:
    admin = db.scalar(select(PlayerTable).where(PlayerTable.login == user.login))
    db.add(AuditLogTable(
        admin_id=admin.id if admin else None,
        action=action,
        details=details,
    ))


def _team_result(team: TeamTable, members: list[PlayerTable]) -> dict:
    return {
        "id": team.id,
        "name": team.name,
        "total_xp": team.total_exp,
        "tokens_collected": team.tokens_collected,
        "puzzles_solved": team.puzzles_solved,
        "finished_at": team.finished_at,
        "members": [
            {
                "id": member.id,
                "login": member.login,
                "display_name": member.display_name,
                "image": member.image,
                "is_team_leader": member.is_team_leader,
            }
            for member in members
        ],
    }


@router.put("/game/settings")
def update_game_settings(settings: GameSettings, user: User = ADMIN_USER):
    with SessionLocal() as db:
        state = _state(db)
        if state.status != "not_started":
            raise HTTPException(status.HTTP_409_CONFLICT, "Settings are locked after the game starts")
        state.team_size = settings.team_size
        state.stage_xp_threshold = settings.stage_xp_threshold
        _audit(db, "update_game_settings", settings.model_dump(), user)
        db.commit()
        return {"team_size": state.team_size, "stage_xp_threshold": state.stage_xp_threshold}


@router.post("/game/start")
def start_game(settings: GameSettings | None = None, user: User = ADMIN_USER):
    with SessionLocal() as db:
        state = db.scalar(select(GameStateTable).where(GameStateTable.id == 1).with_for_update())
        if state is None:
            state = GameStateTable(id=1)
            db.add(state)
            db.flush()
        if state.status != "not_started":
            raise HTTPException(status.HTTP_409_CONFLICT, "The game has already started")
        if settings is not None:
            state.team_size = settings.team_size
            state.stage_xp_threshold = settings.stage_xp_threshold
        if not db.scalar(select(func.count(PuzzleTable.id)).where(PuzzleTable.is_active.is_(True))):
            raise HTTPException(status.HTTP_409_CONFLICT, "Create at least one active puzzle before starting")
        players = list(db.scalars(select(PlayerTable).order_by(PlayerTable.id)).all())
        if not players:
            raise HTTPException(status.HTTP_409_CONFLICT, "No players have logged in")

        state.winner_team_id = None
        db.flush()
        db.execute(SubmissionTable.__table__.delete())
        db.execute(
            PlayerTable.__table__.update().values(team_id=None, is_team_leader=False)
        )
        db.execute(TeamTable.__table__.delete())
        shuffle(players)
        team_count = ceil(len(players) / state.team_size)
        groups: list[list[PlayerTable]] = [[] for _ in range(team_count)]
        for index, player in enumerate(players):
            groups[index % team_count].append(player)
        for index, members in enumerate(groups, start=1):
            team = TeamTable(name=f"Team {index}")
            db.add(team)
            db.flush()
            leader = members[0]
            for member in members:
                member.team_id = team.id
                member.is_team_leader = member.id == leader.id
        state.status = "in_progress"
        state.started_at = datetime.now(UTC)
        state.ended_at = None
        state.winner_team_id = None
        _audit(db, "start_game", {"team_size": state.team_size, "team_count": team_count}, user)
        db.commit()
        return {"status": state.status, "team_count": team_count, "player_count": len(players)}


@router.post("/game/end")
def end_game(user: User = ADMIN_USER):
    with SessionLocal() as db:
        state = db.scalar(select(GameStateTable).where(GameStateTable.id == 1).with_for_update())
        if state is None or state.status == "not_started":
            raise HTTPException(status.HTTP_409_CONFLICT, "The game has not started")
        if state.status == "finished":
            return {"status": state.status, "winner_team_id": state.winner_team_id}
        if state.winner_team_id is None:
            leading_team = db.scalar(
                select(TeamTable).order_by(TeamTable.total_exp.desc(), TeamTable.name).limit(1)
            )
            state.winner_team_id = leading_team.id if leading_team else None
        state.status = "finished"
        state.ended_at = datetime.now(UTC)
        _audit(db, "end_game", {"winner_team_id": state.winner_team_id}, user)
        db.commit()
        return {"status": state.status, "winner_team_id": state.winner_team_id}


@router.post("/game/reset")
def reset_game(user: User = ADMIN_USER):
    with SessionLocal() as db:
        state = _state(db)
        state.winner_team_id = None
        db.flush()
        db.execute(SubmissionTable.__table__.delete())
        db.execute(PlayerTable.__table__.update().values(team_id=None, is_team_leader=False))
        db.execute(TeamTable.__table__.delete())
        state.status = "not_started"
        state.started_at = None
        state.ended_at = None
        state.winner_team_id = None
        _audit(db, "reset_game", {}, user)
        db.commit()
        return {"status": state.status}


@router.get("/puzzle")
def list_puzzles():
    with SessionLocal() as db:
        puzzles = db.scalars(select(PuzzleTable).order_by(PuzzleTable.id)).all()
        return [puzzle.to_dict() for puzzle in puzzles]


@router.delete("/puzzle/{puzzle_id}")
def delete_puzzle(puzzle_id: int, user: User = ADMIN_USER):
    with SessionLocal() as db:
        ensure_game_not_started(db)
        puzzle = db.get(PuzzleTable, puzzle_id)
        if puzzle is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Puzzle not found")
        db.execute(SubmissionTable.__table__.delete().where(SubmissionTable.puzzle_id == puzzle_id))
        db.delete(puzzle)
        _audit(db, "delete_puzzle", {"puzzle_id": puzzle_id}, user)
        db.commit()
        return {"detail": "Puzzle deleted"}


@router.post("/puzzle/{puzzle_id}/image")
async def upload_puzzle_image(puzzle_id: int, image: UploadFile = IMAGE_FILE):
    with SessionLocal() as db:
        ensure_game_not_started(db)
        puzzle = db.get(PuzzleTable, puzzle_id)
        if puzzle is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Puzzle not found")
        image_type = IMAGE_TYPES.get(image.content_type or "")
        if image_type is None:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Use JPEG, PNG, or WebP")
        contents = await image.read(MAX_IMAGE_BYTES + 1)
        if len(contents) > MAX_IMAGE_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image exceeds 10 MiB")
        extension, signature_matches = image_type
        if not signature_matches(contents):
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "The file content is not a valid image")
        UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid4().hex}.{extension}"
        (UPLOAD_DIRECTORY / filename).write_bytes(contents)
        puzzle.image_url = f"/uploads/{filename}"
        db.commit()
        return {"image_url": puzzle.image_url}


@router.get("/teams")
def list_teams():
    with SessionLocal() as db:
        teams = db.scalars(select(TeamTable).order_by(TeamTable.name)).all()
        return [
            _team_result(team, db.scalars(
                select(PlayerTable).where(PlayerTable.team_id == team.id).order_by(PlayerTable.login)
            ).all())
            for team in teams
        ]


@router.put("/users/{player_id}/team")
def reassign_player(player_id: int, assignment: TeamReassignment, user: User = ADMIN_USER):
    with SessionLocal() as db:
        player = db.get(PlayerTable, player_id)
        if player is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found")
        if assignment.team_id is not None and db.get(TeamTable, assignment.team_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
        old_team_id = player.team_id
        player.team_id = assignment.team_id
        player.is_team_leader = False
        _audit(db, "reassign_team", {
            "player_id": player.id,
            "from_team_id": old_team_id,
            "to_team_id": assignment.team_id,
        }, user)
        db.commit()
        return {"player_id": player.id, "team_id": player.team_id}


@router.get("/users")
def list_users():
    with SessionLocal() as db:
        players = db.scalars(select(PlayerTable).order_by(PlayerTable.login)).all()
        return [
            {
                "id": player.id,
                "intra_id": player.intra_id,
                "login": player.login,
                "display_name": player.display_name,
                "image": player.image,
                "email": player.email,
                "team_id": player.team_id,
                "is_team_leader": player.is_team_leader,
            }
            for player in players
        ]


@router.get("/submissions")
def list_submissions(
    team_id: int | None = None,
    puzzle_id: int | None = None,
    correct: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
):
    with SessionLocal() as db:
        query = (
            select(SubmissionTable, PlayerTable.login, TeamTable.name, PuzzleTable.title)
            .join(PlayerTable, SubmissionTable.user_id == PlayerTable.id)
            .join(TeamTable, SubmissionTable.team_id == TeamTable.id)
            .join(PuzzleTable, SubmissionTable.puzzle_id == PuzzleTable.id)
        )
        if team_id is not None:
            query = query.where(SubmissionTable.team_id == team_id)
        if puzzle_id is not None:
            query = query.where(SubmissionTable.puzzle_id == puzzle_id)
        if correct is not None:
            query = query.where(SubmissionTable.is_correct.is_(correct))
        rows = db.execute(query.order_by(SubmissionTable.created_at.desc()).limit(limit)).all()
        return [
            {
                **submission.to_dict(),
                "login": login,
                "team_name": team_name,
                "puzzle_title": title,
            }
            for submission, login, team_name, title in rows
        ]


@router.get("/audit")
def list_audit(limit: int = Query(default=100, ge=1, le=500)):
    with SessionLocal() as db:
        rows = db.execute(
            select(AuditLogTable, PlayerTable.login)
            .outerjoin(PlayerTable, AuditLogTable.admin_id == PlayerTable.id)
            .order_by(AuditLogTable.created_at.desc())
            .limit(limit)
        ).all()
        return [
            {**entry.to_dict(), "admin_login": admin_login}
            for entry, admin_login in rows
        ]


@router.get("/dashboard")
def admin_dashboard():
    with SessionLocal() as db:
        state = _state(db)
        return {
            "game": {
                "status": state.status,
                "team_size": state.team_size,
                "stage_xp_threshold": state.stage_xp_threshold,
                "started_at": state.started_at,
                "ended_at": state.ended_at,
                "winner_team_id": state.winner_team_id,
            },
            "players": db.scalar(select(func.count(PlayerTable.id))) or 0,
            "teams": db.scalar(select(func.count(TeamTable.id))) or 0,
            "active_puzzles": db.scalar(select(func.count(PuzzleTable.id)).where(PuzzleTable.is_active.is_(True))) or 0,
            "submissions": db.scalar(select(func.count(SubmissionTable.id))) or 0,
        }