"""Project indexing and retrieval using local embeddings and PostgreSQL."""

import math

from sqlalchemy import delete
from sqlmodel import select

from app.llm import client
from app.models import ProjectChunk
from app.project_files import iter_project_text_files
from config import Config
from db.database import SessionLocal


CHUNK_SIZE = 2400
CHUNK_OVERLAP = 300
EMBED_BATCH_SIZE = 16
MAX_INDEXED_FILES = 1500


def split_into_chunks(text: str) -> list[str]:
    """Split text into overlapping chunks while preserving useful context."""
    text = text.strip()
    if not text:
        return []
    step = CHUNK_SIZE - CHUNK_OVERLAP
    return [part for start in range(0, len(text), step)
            if (part := text[start : start + CHUNK_SIZE].strip())]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Create embeddings using the configured local OpenAI-compatible server."""
    if not texts:
        return []
    response = await client.embeddings.create(
        model=Config.RAG_EMBED_MODEL,
        input=texts,
    )
    ordered = sorted(response.data, key=lambda item: item.index)
    return [item.embedding for item in ordered]


async def index_project(project_name: str) -> int:
    """Index readable project files. Existing data is replaced after embedding succeeds."""
    project_files = list(iter_project_text_files(project_name))[:MAX_INDEXED_FILES]
    chunks: list[dict] = []
    for relative_path, text in project_files:
        for number, content in enumerate(split_into_chunks(text)):
            chunks.append({"path": relative_path, "chunk_number": number, "content": content})

    embedded_rows: list[ProjectChunk] = []
    for start in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[start : start + EMBED_BATCH_SIZE]
        vectors = await embed_texts([item["content"] for item in batch])
        if len(vectors) != len(batch):
            raise RuntimeError("Embedding service returned an unexpected number of vectors.")
        embedded_rows.extend(
            ProjectChunk(
                project_name=project_name,
                file_path=item["path"],
                chunk_number=item["chunk_number"],
                content=item["content"],
                embedding=vector,
            )
            for item, vector in zip(batch, vectors)
        )

    # Don't discard a working index until all embeddings have been generated.
    async with SessionLocal() as session:
        async with session.begin():
            await session.exec(delete(ProjectChunk).where(ProjectChunk.project_name == project_name))
            session.add_all(embedded_rows)
    return len(embedded_rows)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Return cosine similarity between equal-length embedding vectors."""
    if len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


async def search_project_knowledge(
    project_name: str,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """Return the most relevant indexed project passages for a question."""
    query = query.strip()
    if not query:
        return []
    top_k = max(1, min(int(top_k), 8))
    query_vector = (await embed_texts([query]))[0]
    async with SessionLocal() as session:
        result = await session.exec(
            select(ProjectChunk).where(ProjectChunk.project_name == project_name)
        )
        rows = result.all()

    ranked = [
        {
            "path": row.file_path,
            "chunk": row.chunk_number,
            "score": round(cosine_similarity(query_vector, row.embedding), 4),
            "content": row.content,
        }
        for row in rows
    ]
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:top_k]
