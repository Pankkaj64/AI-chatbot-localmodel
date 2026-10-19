from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.rag import index_project
from config import Config


agent_router = APIRouter()


class IndexRequest(BaseModel):
    project_name: str


@agent_router.get("/projects")
async def get_projects():
    """Return only the projects explicitly configured in backend/.env."""
    projects = sorted(Config.PROJECTS.keys())
    return {
        "projects": projects,
        "default_project": (
            Config.DEFAULT_PROJECT
            if Config.DEFAULT_PROJECT in Config.PROJECTS
            else (projects[0] if projects else "")
        ),
    }


@agent_router.post("/index")
async def index_selected_project(request: IndexRequest):
    """Index one configured project for RAG."""
    if request.project_name not in Config.PROJECTS:
        raise HTTPException(status_code=404, detail="Project is not configured.")

    try:
        chunk_count = await index_project(request.project_name)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not index this project. Check Ollama and the backend terminal.",
        ) from exc

    return {
        "project_name": request.project_name,
        "indexed_chunks": chunk_count,
    }
