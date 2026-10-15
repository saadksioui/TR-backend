from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import (
    AuditLogTable,
    GameStateTable,
    PlayerTable,
    PuzzleTable,
    SessionLocal,
    SubmissionTable,
    TeamTable,
)
from app.schemas import AnswerSubmission, User
from ._tools import verify_user


router = APIRouter(dependencies=[Depends(verify_user)])


def _player_for_login(db, login: str) -> PlayerTable:
    player = db.scalar(select(PlayerTable).where(PlayerTable.login == login))
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player is not registered")
    return player


def _game_state(db) -> GameStateTable:
    state = db.get(GameStateTable, 1)
    if state is None:
        state = GameStateTable(id=1)
        db.add(state)
        db.flush()
    return state


def _team_members(db, team_id: int) -> list[dict]:
    players = db.scalars(
        select(PlayerTable).where(PlayerTable.team_id == team_id).order_by(PlayerTable.login)
    ).all()
    members = []
    for player in players:
        xp = db.scalar(
            select(func.coalesce(func.sum(SubmissionTable.xp_awarded), 0)).where(
                SubmissionTable.user_id == player.id,
                SubmissionTable.is_correct.is_(True),
            )
        )
        members.append({
            "id": player.id,
            "login": player.login,
            "display_name": player.display_name,
            "image": player.image,
            "individual_xp": int(xp or 0),
            "is_team_leader": player.is_team_leader,
        })
    return sorted(members, key=lambda member: (-member["individual_xp"], member["login"]))


def _team_dict(db, team: TeamTable) -> dict:
    return {
        "id": team.id,
        "name": team.name,
        "total_xp": team.total_exp,
        "tokens_collected": team.tokens_collected,
        "puzzles_solved": team.puzzles_solved,
        "finished_at": team.finished_at,
        "members": _team_members(db, team.id),
    }


def _puzzle_view(db, puzzle: PuzzleTable, team: TeamTable | None) -> dict:
    solved = bool(team and db.scalar(
        select(SubmissionTable.id).where(
            SubmissionTable.team_id == team.id,
            SubmissionTable.puzzle_id == puzzle.id,
            SubmissionTable.is_correct.is_(True),
        ).limit(1)
    ))
    state = _game_state(db)
    locked = False
    lock_reason = None
    if team is None:
        locked, lock_reason = True, "not_assigned_to_team"
    elif puzzle.is_big_puzzle and team.tokens_collected < (puzzle.tokens_required or 0):
        locked, lock_reason = True, "not_enough_tokens"
    elif puzzle.category == "middle_ages" and team.total_exp < state.stage_xp_threshold:
        locked, lock_reason = True, "xp_threshold"
    elif puzzle.category == "future" and team.total_exp < state.stage_xp_threshold * 2:
        locked, lock_reason = True, "xp_threshold"

    return {
        "id": puzzle.id,
        "title": puzzle.title,
        "description": puzzle.description,
        "category": puzzle.category,
        "is_special": puzzle.is_special,
        "is_big_puzzle": puzzle.is_big_puzzle,
        "image_url": puzzle.image_url,
        "xp_value": puzzle.xp_value,
        "tokens_awarded": puzzle.tokens_awarded,
        "tokens_required": puzzle.tokens_required,
        "is_solved": solved,
        "is_locked": locked,
        "lock_reason": lock_reason,
        "tokens_collected": team.tokens_collected if team else 0,
    }


@router.get("/game/state")
def game_state():
    with SessionLocal() as db:
        state = _game_state(db)
        winner = db.get(TeamTable, state.winner_team_id) if state.winner_team_id else None
        db.commit()
        return {
            "status": state.status,
            "team_size": state.team_size,
            "stage_xp_threshold": state.stage_xp_threshold,
            "started_at": state.started_at,
            "ended_at": state.ended_at,
            "winner_team_id": state.winner_team_id,
            "winner_team_name": winner.name if winner else None,
        }


@router.get("/puzzles")
def puzzles(user: User = Depends(verify_user)):
    with SessionLocal() as db:
        player = None if user.is_admin else _player_for_login(db, user.login)
        team = db.get(TeamTable, player.team_id) if player and player.team_id else None
        active = db.scalars(
            select(PuzzleTable).where(PuzzleTable.is_active.is_(True)).order_by(PuzzleTable.id)
        ).all()
        return [_puzzle_view(db, puzzle, team) for puzzle in active]


@router.get("/puzzle/{puzzle_id}")
def puzzle_details(puzzle_id: int, user: User = Depends(verify_user)):
    with SessionLocal() as db:
        puzzle = db.get(PuzzleTable, puzzle_id)
        if puzzle is None or not puzzle.is_active:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Puzzle not found")
        player = None if user.is_admin else _player_for_login(db, user.login)
        team = db.get(TeamTable, player.team_id) if player and player.team_id else None
        return _puzzle_view(db, puzzle, team)


@router.post("/puzzle/{puzzle_id}/submit")
def submit_answer(puzzle_id: int, submission: AnswerSubmission, user: User = Depends(verify_user)):
    if user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins cannot submit puzzle answers")
    with SessionLocal() as db:
        state = db.scalar(select(GameStateTable).where(GameStateTable.id == 1).with_for_update())
        if state is None or state.status != "in_progress":
            raise HTTPException(status.HTTP_409_CONFLICT, "The game is not in progress")
        player = _player_for_login(db, user.login)
        if player.team_id is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "You are not assigned to a team")
        team = db.scalar(select(TeamTable).where(TeamTable.id == player.team_id).with_for_update())
        puzzle = db.get(PuzzleTable, puzzle_id)
        if puzzle is None or not puzzle.is_active:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Puzzle not found")
        if puzzle.category == "middle_ages" and team.total_exp < state.stage_xp_threshold:
            raise HTTPException(status.HTTP_423_LOCKED, "This era is still locked")
        if puzzle.category == "future" and team.total_exp < state.stage_xp_threshold * 2:
            raise HTTPException(status.HTTP_423_LOCKED, "This era is still locked")
        if puzzle.is_big_puzzle and team.tokens_collected < (puzzle.tokens_required or 0):
            raise HTTPException(status.HTTP_423_LOCKED, "Your team does not have enough tokens")
        already_solved = db.scalar(
            select(SubmissionTable.id).where(
                SubmissionTable.team_id == team.id,
                SubmissionTable.puzzle_id == puzzle.id,
                SubmissionTable.is_correct.is_(True),
            ).limit(1)
        )
        if already_solved:
            raise HTTPException(status.HTTP_409_CONFLICT, "Your team already solved this puzzle")

        normalized_answer = " ".join(submission.answer.split()).casefold()
        normalized_solution = " ".join(puzzle.answer.split()).casefold()
        correct = normalized_answer == normalized_solution
        xp_awarded = puzzle.xp_value if correct else 0
        db.add(SubmissionTable(
            puzzle_id=puzzle.id,
            team_id=team.id,
            user_id=player.id,
            submitted_answer=submission.answer.strip(),
            is_correct=correct,
            xp_awarded=xp_awarded,
        ))
        if correct:
            team.total_exp += xp_awarded
            team.puzzles_solved += 1
            if puzzle.is_special:
                team.tokens_collected += puzzle.tokens_awarded
            active_count = db.scalar(
                select(func.count(PuzzleTable.id)).where(PuzzleTable.is_active.is_(True))
            ) or 0
            if team.puzzles_solved >= active_count:
                team.finished_at = datetime.now(timezone.utc)
                if state.winner_team_id is None:
                    state.winner_team_id = team.id
                    state.status = "finished"
                    state.ended_at = team.finished_at
        db.add(AuditLogTable(
            admin_id=None,
            action="submit_answer",
            details={"puzzle_id": puzzle.id, "team_id": team.id, "user_id": player.id, "is_correct": correct},
        ))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "Your team already solved this puzzle")
        return {
            "is_correct": correct,
            "xp_awarded": xp_awarded,
            "tokens_awarded": puzzle.tokens_awarded if correct and puzzle.is_special else 0,
            "team_total_xp": team.total_exp,
            "team_tokens": team.tokens_collected,
            "game_status": state.status,
        }


@router.get("/team")
def my_team(user: User = Depends(verify_user)):
    if user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins do not have a team")
    with SessionLocal() as db:
        player = _player_for_login(db, user.login)
        if player.team_id is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "You are not assigned to a team")
        return _team_dict(db, db.get(TeamTable, player.team_id))


@router.get("/teams/{team_id}")
def team_details(team_id: int):
    with SessionLocal() as db:
        team = db.get(TeamTable, team_id)
        if team is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
        return _team_dict(db, team)


@router.get("/leaderboard")
def leaderboard():
    with SessionLocal() as db:
        teams = db.scalars(
            select(TeamTable).order_by(TeamTable.total_exp.desc(), TeamTable.name)
        ).all()
        return [_team_dict(db, team) for team in teams]


@router.get("/endgame")
def endgame():
    with SessionLocal() as db:
        state = _game_state(db)
        if state.status != "finished" or state.winner_team_id is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "The game has not finished")
        winner = db.get(TeamTable, state.winner_team_id)
        return {"game": {"status": state.status, "ended_at": state.ended_at}, "winner": _team_dict(db, winner)}