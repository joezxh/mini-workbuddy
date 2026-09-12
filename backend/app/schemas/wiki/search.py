"""Wiki 检索 / LLM 问答 Pydantic schemas（G1/G9）。"""
from typing import List, Optional

from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    mode: str = "hybrid"  # semantic | keyword | hybrid
    top_k: int = 5
    knowledge_id: Optional[int] = None
    owl_class_filter: Optional[List[str]] = None


class SearchItem(BaseModel):
    id: int
    slug: str
    title: str
    summary: Optional[str] = None
    snippet: str = ""
    score: float = 0.0
    category_id: Optional[int] = None


class SearchResult(BaseModel):
    query: str
    mode: str
    total: int
    items: List[SearchItem] = []


class CitationItem(BaseModel):
    ref: int
    article_id: int
    slug: str
    title: str
    snippet: str = ""


class LLMWikiAnswer(BaseModel):
    answer: str
    citations: List[CitationItem] = []
    mode: str = "llm_wiki"
