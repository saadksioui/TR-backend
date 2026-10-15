from typing import Any
from .schemas import IntraInfo, Player, Puzzle
from .models import PlayerTable, PuzzleTable, SessionLocal, AdminTable, TeamTable
from sqlalchemy import select, update, delete, or_
from sqlalchemy.dialects.postgresql import insert
import random



class DbWrapper:
    @staticmethod
    def get_admin_credential(username: str) -> str | None:
        with SessionLocal() as db:
            admin = db.scalar(select(AdminTable).where(AdminTable.username == username))
        if admin is None:
            return None
        return admin.password


    @staticmethod
    def add_player(player: IntraInfo) -> None:
        statement = insert(PlayerTable).values(**player.model_dump())
        sql = statement.on_conflict_do_update(
            index_elements=[PlayerTable.intra_id],
            set_={
                "login": statement.excluded.login,
                "display_name": statement.excluded.display_name,
                "image": statement.excluded.image,
                "email": statement.excluded.email,
            },
        )
        with SessionLocal() as db:
            db.execute(sql)
            db.commit()


    @staticmethod
    def get_player(login_or_id: int | str) -> Player | None:
        if isinstance(login_or_id, int):
            where = PlayerTable.id == login_or_id
        else:
            where = PlayerTable.login == login_or_id
        with SessionLocal() as db:
            row = db.execute(
                select(PlayerTable, TeamTable.name.label("team_name"))\
                .outerjoin(TeamTable, PlayerTable.team_id == TeamTable.id)\
                .where(where)).first()
            if row:
                plyr, team_id = row
                data = plyr.to_dict()
                data['team_name'] = team_id
                return Player.model_validate(data)

            return None


    @staticmethod
    def create_puzzle(puzzle: Puzzle) -> None:
        data = puzzle.model_dump()
        data.pop("id", None)
        sql = insert(PuzzleTable).values(**data)
        with SessionLocal() as db:
            db.execute(sql)
            db.commit()


    @staticmethod
    def update_puzzle(puzzle: Puzzle) -> None:
        data = puzzle.model_dump()
        sql = update(PuzzleTable).values(**data).where(PuzzleTable.id == puzzle.id)
        with SessionLocal() as db:
            db.execute(sql)
            db.commit()


    @staticmethod
    def get_puzzle(id: int) -> dict[str, Any] | None:
        with SessionLocal() as db:
            rslt = db.scalar(select(PuzzleTable).where(PuzzleTable.id == id))
        if rslt:
            return rslt.to_dict()
        return None

    @staticmethod
    def players_count() -> int:
        with SessionLocal() as db:
            return db.query(PlayerTable).count()


    @staticmethod
    def clear_teams() -> None:
        sql = update(PlayerTable).values(team_id=None, is_team_leader=False)
        with SessionLocal() as db:
            db.execute(sql)
            db.execute(delete(TeamTable))
            db.commit()


    @staticmethod
    def get_players() -> list[Player]:
        sql = select(PlayerTable, TeamTable.name.label("team_name"))\
            .outerjoin(TeamTable, PlayerTable.team_id == TeamTable.id)
        with SessionLocal() as db:
            return [
                Player.model_validate(
                    {"team_name": team_name, **plyr.to_dict()}
                )
                for plyr, team_name in db.execute(sql)
            ]

    @staticmethod
    def create_teams(teams: list[list[Player]]) -> None:
        team_index = 20
        def create_team():
            nonlocal team_index
            name = f"team -> {team_index}"
            db.execute(insert(TeamTable).values(
                name=name
            ))
            team_index += 1
            row = db.execute(
                select(TeamTable.id).where(TeamTable.name == name)
            ).first()
            return row and row[0]



        with SessionLocal() as db:
            for tm in teams:
                leader = random.choice(tm)
                team_id = create_team()
                db.execute(
                    update(PlayerTable)\
                        .values(team_id=team_id)\
                        .where(or_(*[
                            PlayerTable.id == plyr.id for plyr in tm
                        ]))
                )
                db.execute(
                    update(PlayerTable)\
                        .values(is_team_leader=True)\
                        .where(PlayerTable.id == leader.id)
                )
            db.commit()
