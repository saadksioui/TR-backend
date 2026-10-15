from ._env import SETTINGS
from .models import AdminTable, Base, DB_ENGINE
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from argon2 import PasswordHasher

# create tables
Base.metadata.create_all(DB_ENGINE)

if "teams" in inspect(DB_ENGINE).get_table_names():
    existing_columns = {
        column["name"] for column in inspect(DB_ENGINE).get_columns("teams")
    }
    timestamp_type = "TIMESTAMP WITH TIME ZONE" if DB_ENGINE.dialect.name == "postgresql" else "DATETIME"
    team_migrations = {
        "tokens_collected": "INTEGER NOT NULL DEFAULT 0",
        "puzzles_solved": "INTEGER NOT NULL DEFAULT 0",
        "finished_at": timestamp_type,
        "created_at": f"{timestamp_type} NOT NULL DEFAULT CURRENT_TIMESTAMP",
    }
    with DB_ENGINE.begin() as connection:
        for column, definition in team_migrations.items():
            if column not in existing_columns:
                connection.execute(text(f"ALTER TABLE teams ADD COLUMN {column} {definition}"))

# insert admin user
assert isinstance(SETTINGS.init_admin_password, str), "make sure to put `INIT_ADMIN_PASSWORD` inside .env"


with Session(DB_ENGINE) as __session:
    __sql = insert(AdminTable).values(
        username="root",
        password=PasswordHasher().hash(SETTINGS.init_admin_password)
    ).on_conflict_do_nothing(index_elements=["username"])
    __session.execute(__sql)
    __session.commit()


del __sql
