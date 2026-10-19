"""Small arXiv Atom API search tool for research questions."""

import asyncio
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ARXIV_API = "https://export.arxiv.org/api/query"
ATOM = "http://www.w3.org/2005/Atom"
_request_lock = asyncio.Lock()


async def search_arxiv(query: str, max_results: int = 5) -> dict:
    query = query.strip()
    if not query:
        raise ValueError("Search query cannot be empty.")
    max_results = max(1, min(int(max_results), 5))

    def fetch_xml() -> bytes:
        params = urlencode({"search_query": f"all:{query}", "start": 0, "max_results": max_results})
        request = Request(
            f"{ARXIV_API}?{params}",
            headers={"User-Agent": "local-chatbot/1.0"},
        )
        with urlopen(request, timeout=20) as response:
            return response.read()

    async with _request_lock:
        xml_data = await asyncio.to_thread(fetch_xml)

    root = ET.fromstring(xml_data)
    papers = []
    for entry in root.findall(f"{{{ATOM}}}entry"):
        link = next(
            (item.attrib.get("href") for item in entry.findall(f"{{{ATOM}}}link")
             if item.attrib.get("title") == "pdf"),
            None,
        )
        papers.append({
            "title": " ".join((entry.findtext(f"{{{ATOM}}}title") or "").split()),
            "authors": [author.findtext(f"{{{ATOM}}}name") for author in entry.findall(f"{{{ATOM}}}author")],
            "published": entry.findtext(f"{{{ATOM}}}published"),
            "abstract": " ".join((entry.findtext(f"{{{ATOM}}}summary") or "").split())[:1600],
            "url": entry.findtext(f"{{{ATOM}}}id"),
            "pdf_url": link,
        })
    return {"papers": papers}
