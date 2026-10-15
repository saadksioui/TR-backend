from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
    inspect,
    true,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.sql import func

from app import SETTINGS



DB_ENGINE = create_engine(SETTINGS.database_url)


SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=DB_ENGINE)


class Base(DeclarativeBase):
    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}


class AdminTable(Base):
    __tablename__ = 'admin'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(Text)


class TeamTable(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(
        unique=True, autoincrement=True, nullable=False, primary_key=True
    )
    name: Mapped[str] = mapped_column(unique=True, nullable=False)
    total_exp: Mapped[int] = mapped_column(
        server_default='0',
        nullable=False,
        default=0
    )
    tokens_collected: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    puzzles_solved: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )


class PlayerTable(Base):
    __tablename__ = 'players'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, nullable=False)
    intra_id: Mapped[int] = mapped_column(unique=True)
    login: Mapped[str] = mapped_column(String(50), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(100))
    image: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(String(150))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    is_team_leader: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        server_default="FALSE"
    )
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)


class PuzzleTable(Base):
    __tablename__ = 'puzzles'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(15))
    is_special: Mapped[bool] = mapped_column(default=False, server_default='false')
    is_big_puzzle: Mapped[bool] = mapped_column(default=False, server_default='false')
    image_url: Mapped[str | None] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    xp_value: Mapped[int]
    tokens_awarded: Mapped[int] = mapped_column(default=0, server_default='0')
    tokens_required: Mapped[int | None]
    is_active: Mapped[bool] = mapped_column(default=True, server_default='true')

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "category IN ('prehistoric', 'middle_ages', 'future')",
            name='check_category'
        ),
    )


class GameStateTable(Base):
    __tablename__ = "game_state"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    status: Mapped[str] = mapped_column(String(15), nullable=False, default="not_started", server_default="not_started")
    team_size: Mapped[int] = mapped_column(Integer, nullable=False, default=4, server_default="4")
    stage_xp_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    winner_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('not_started', 'in_progress', 'finished')", name="check_game_status"),
        CheckConstraint("team_size > 0", name="check_team_size"),
        CheckConstraint("stage_xp_threshold >= 0", name="check_stage_xp_threshold"),
    )


class SubmissionTable(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    puzzle_id: Mapped[int] = mapped_column(ForeignKey("puzzles.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    submitted_answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    xp_awarded: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now())

    __table_args__ = (
        Index(
            "one_correct_solve_per_team",
            "team_id",
            "puzzle_id",
            unique=True,
            postgresql_where=(is_correct == true()),
            sqlite_where=(is_correct == true()),
        ),
    )


class AuditLogTable(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now())
