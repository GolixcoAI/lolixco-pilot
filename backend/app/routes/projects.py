"""FastAPI routes for project management."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import AuthenticatedUser, get_current_user
from app.db.repository import BaseRepository, get_repository
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    user: AuthenticatedUser = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
) -> list[ProjectResponse]:
    """List all projects owned by the authenticated user."""
    projects = repo.list_projects(user.user_id)
    return [
        ProjectResponse(
            id=p.id,
            user_id=p.user_id,
            name=p.name,
            aspect_ratio=p.aspect_ratio,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in projects
    ]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_or_get_project(
    payload: ProjectCreate | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
) -> ProjectResponse:
    """Create a new project or get the active default project."""
    name = payload.name if payload else "Untitled Cut"
    aspect_ratio = payload.aspect_ratio if payload else "9:16"
    record = repo.create_project(user_id=user.user_id, name=name, aspect_ratio=aspect_ratio)
    return ProjectResponse(
        id=record.id,
        user_id=record.user_id,
        name=record.name,
        aspect_ratio=record.aspect_ratio,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
) -> ProjectResponse:
    """Get project details, scoped to authenticated owner."""
    project = repo.get_project(project_id, user.user_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied",
        )
    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        aspect_ratio=project.aspect_ratio,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    repo: BaseRepository = Depends(get_repository),
) -> ProjectResponse:
    """Update project name or aspect ratio."""
    updated = repo.update_project(
        project_id=project_id,
        user_id=user.user_id,
        name=payload.name,
        aspect_ratio=payload.aspect_ratio,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied",
        )
    return ProjectResponse(
        id=updated.id,
        user_id=updated.user_id,
        name=updated.name,
        aspect_ratio=updated.aspect_ratio,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )
