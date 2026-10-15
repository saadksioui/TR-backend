from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator



class AdminCredential(BaseModel):
    username: str
    password: str


class User(BaseModel):
    login: str = Field(alias="sub")
    is_admin: bool


class Player(BaseModel):
    id: int
    display_name: str | None = None
    login: str
    image: str | None = None
    email: str | None = None
    puzzles: list[int] = Field(default_factory=list)
    team_id: int | None = None
    team_name: str | None = None
    individual_xp: int = 0




class IntraInfo(BaseModel):
    login: str
    intra_id: int = Field(alias="id")
    display_name: str = Field(alias="displayname")
    image: str = Field(alias="image")
    email: str | None = None


    @field_validator("image", mode="before")
    @classmethod
    def _get_avatar_url(cls, v):
        if isinstance(v, dict) and "link" in v:
            return v["link"]
        return v


class Puzzle(BaseModel):
    id: int | None = None
    title: str = Field(min_length=1)
    description: str | None = None
    category: Literal['prehistoric', 'middle_ages', 'future']
    is_special: bool = False
    is_big_puzzle: bool = False
    image_url: str | None = None
    answer: str = Field(min_length=1)
    xp_value: int = Field(ge=0)
    tokens_awarded: int = Field(default=0, ge=0)
    tokens_required: int | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_special_rules(self):
        if self.is_big_puzzle and not self.is_special:
            raise ValueError("The big puzzle must be marked special")
        if self.is_big_puzzle and (self.tokens_required is None or self.tokens_required < 1):
            raise ValueError("The big puzzle must require at least one token")
        if not self.is_big_puzzle and self.tokens_required is not None:
            raise ValueError("Only the big puzzle can require tokens")
        if not self.is_special and self.tokens_awarded:
            raise ValueError("Only special puzzles can award tokens")
        return self


class AnswerSubmission(BaseModel):
    answer: str = Field(min_length=1, max_length=500)


class GameSettings(BaseModel):
    team_size: int = Field(default=4, ge=1, le=100)
    stage_xp_threshold: int = Field(default=100, ge=0)


class TeamReassignment(BaseModel):
    team_id: int | None
