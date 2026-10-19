"""Allowlisted tools available to the chat agent."""

import json

from app.agent_tools.arxiv_search import search_arxiv
from app.project_files import list_project_files, read_project_file, search_project_files
from app.project_memory import save_project_note
from app.rag import search_project_knowledge


PROJECT_TOOLS = [
    {"type": "function", "function": {
        "name": "list_project_files",
        "description": "List supported text and code files in the selected project.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    }},
    {"type": "function", "function": {
        "name": "read_project_file",
        "description": "Read a project-relative code, text, or Markdown file.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"], "additionalProperties": False},
    }},
    {"type": "function", "function": {
        "name": "search_project_files",
        "description": "Find a literal text string in the selected project's files.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 20},
        }, "required": ["query"], "additionalProperties": False},
    }},
    {"type": "function", "function": {
        "name": "search_project_knowledge",
        "description": "Retrieve relevant passages from the selected project's RAG index.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 8},
        }, "required": ["query"], "additionalProperties": False},
    }},
    {"type": "function", "function": {
        "name": "remember_project_note",
        "description": "Save concise project context only when the user explicitly asks.",
        "parameters": {"type": "object", "properties": {"note": {"type": "string"}}, "required": ["note"], "additionalProperties": False},
    }},
]

ARXIV_TOOL = {"type": "function", "function": {
    "name": "search_arxiv",
    "description": "Search arXiv for research papers when the user asks for academic research.",
    "parameters": {"type": "object", "properties": {
        "query": {"type": "string"},
        "max_results": {"type": "integer", "minimum": 1, "maximum": 5},
    }, "required": ["query"], "additionalProperties": False},
}}


def get_tool_definitions(has_project: bool, user_request: str = "") -> list[dict]:
    """Offer tools only when the request signals that tools are useful.

    Small local models can over-call tools if they are shown on every turn. A
    plain factual or conversational question should go straight to the model.
    """
    request = user_request.casefold()
    project_intent = any(term in request for term in (
        "project", "codebase", "repository", "repo", "folder", "readme",
        "backend", "frontend", "source code", "this app", "my app", "our app",
        "this code", "my code", "fix the error", "debug this", "search files",
        "in the code", "in this file", "save progress", "remember this",
        "continue this project", "index project",
    ))
    research_intent = any(term in request for term in (
        "arxiv", "research paper", "original paper", "academic paper", "papers",
        "citation", "literature review", "research study",
    ))

    tools = PROJECT_TOOLS if has_project and project_intent else []
    if research_intent:
        tools = [*tools, ARXIV_TOOL]
    return tools


async def dispatch_tool(project_name: str | None, tool_name: str, raw_arguments: str) -> str:
    """Validate and run an allowlisted tool without evaluating model code."""
    try:
        arguments = json.loads(raw_arguments or "{}")
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be a JSON object.")
        if tool_name == "search_arxiv":
            result = await search_arxiv(arguments["query"], arguments.get("max_results", 5))
        elif not project_name:
            result = {"error": "Choose a configured project to use project tools."}
        elif tool_name == "list_project_files":
            result = list_project_files(project_name)
        elif tool_name == "read_project_file":
            result = read_project_file(project_name, arguments["path"])
        elif tool_name == "search_project_files":
            result = search_project_files(project_name, arguments["query"], arguments.get("max_results", 10))
        elif tool_name == "search_project_knowledge":
            result = await search_project_knowledge(project_name, arguments["query"], arguments.get("top_k", 5))
        elif tool_name == "remember_project_note":
            result = await save_project_note(project_name, arguments["note"])
        else:
            result = {"error": "Tool is not available."}
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        result = {"error": f"Tool arguments were invalid: {exc}"}
    except Exception:
        result = {"error": "The tool failed. Check the backend terminal and service configuration."}
    return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
