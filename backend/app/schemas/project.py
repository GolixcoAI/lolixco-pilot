"""Pydantic schemas for projects."""

from datetime import datetime

from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    name: str = Field(default="Untitled Cut", min_length=1, max_length=100)
    aspect_ratio: str = Field(default="9:16", pattern="^(9:16|16:9|1:1|4:5)$")


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    aspect_ratio: str | None = Field(default=None, pattern="^(9:16|16:9|1:1|4:5)$")


class ProjectResponse(ProjectBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
