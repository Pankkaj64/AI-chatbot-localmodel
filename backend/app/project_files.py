"""Safe, read-only access to explicitly configured project directories."""

from pathlib import Path

from config import Config


TEXT_EXTENSIONS = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".html", ".htm", ".css", ".scss", ".json", ".md", ".txt", ".rst",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".sql", ".sh",
    ".env.example", ".xml", ".svg", ".java", ".kt", ".go", ".rs", ".c",
    ".h", ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift", ".dockerfile", ".pdf",
}
SPECIAL_TEXT_FILES = {"dockerfile", "makefile", "readme", ".gitignore", ".dockerignore", ".env.example"}
IGNORED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build",
    ".next", "coverage", ".idea", ".vscode", "target",
}
MAX_FILE_BYTES = 512_000
MAX_READ_CHARS = 40_000


def project_root(project_name: str) -> Path:
    """Resolve a project name from the allowlist and reject missing folders."""
    configured = Config.PROJECTS.get(project_name)
    if not configured:
        raise ValueError("Project is not configured.")
    root = Path(configured).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("The configured project directory does not exist.")
    return root


def _is_inside(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _supported(path: Path) -> bool:
    lower_name = path.name.lower()
    return lower_name in SPECIAL_TEXT_FILES or path.suffix.lower() in TEXT_EXTENSIONS


def _read_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError("PDF reading requires pypdf; install backend requirements.") from exc
        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    return path.read_text(encoding="utf-8")


def iter_project_text_files(project_name: str):
    """Yield (relative path, content) for supported, bounded text files."""
    root = project_root(project_name)
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part.lower() in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        if not _supported(path) or _is_secret_filename(path.name):
            continue
        try:
            resolved = path.resolve()
            if not _is_inside(root, resolved) or resolved.stat().st_size > MAX_FILE_BYTES:
                continue
            content = _read_text(resolved)
        except (OSError, UnicodeError, ValueError):
            continue
        yield path.relative_to(root).as_posix(), content


def _resolve_file(project_name: str, relative_path: str) -> tuple[Path, Path]:
    root = project_root(project_name)
    requested = Path(relative_path)
    if requested.is_absolute():
        raise ValueError("Use a project-relative path.")
    path = (root / requested).resolve()
    if not _is_inside(root, path):
        raise ValueError("The requested path is outside the configured project.")
    if not path.is_file() or not _supported(path):
        raise ValueError("The file does not exist or is not a supported text file.")
    if _is_secret_filename(path.name):
        raise ValueError("Environment secret files cannot be read.")
    if any(part.lower() in IGNORED_DIRS for part in path.relative_to(root).parts):
        raise ValueError("Files in generated or dependency directories cannot be read.")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("The file is too large to read.")
    return root, path


def _is_secret_filename(name: str) -> bool:
    lowered = name.lower()
    if lowered == ".env.example":
        return False
    return (
        lowered == ".env"
        or lowered.startswith(".env.")
        or lowered.endswith((".pem", ".key", ".p12", ".pfx"))
        or lowered in {"id_rsa", "id_ed25519", "credentials", "secrets.json"}
    )


def list_project_files(project_name: str, max_results: int = 300) -> dict:
    paths = [relative for relative, _ in iter_project_text_files(project_name)]
    return {"files": paths[:max_results], "truncated": len(paths) > max_results}


def read_project_file(project_name: str, relative_path: str) -> dict:
    root, path = _resolve_file(project_name, relative_path)
    text = _read_text(path)
    return {
        "path": path.relative_to(root).as_posix(),
        "content": text[:MAX_READ_CHARS],
        "truncated": len(text) > MAX_READ_CHARS,
    }


def search_project_files(project_name: str, query: str, max_results: int = 10) -> dict:
    query = query.strip()
    if not query:
        raise ValueError("Search text cannot be empty.")
    max_results = max(1, min(int(max_results), 20))
    matches = []
    for relative_path, content in iter_project_text_files(project_name):
        for line_number, line in enumerate(content.splitlines(), start=1):
            if query.casefold() in line.casefold():
                matches.append({"path": relative_path, "line": line_number, "text": line[:500]})
                if len(matches) >= max_results:
                    return {"matches": matches, "truncated": True}
    return {"matches": matches, "truncated": False}
