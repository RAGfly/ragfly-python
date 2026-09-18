from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Chunk:
    text: str
    page: Optional[int] = None
    extra: dict = field(default_factory=dict)


@dataclass
class Document:
    code: Optional[str]
    name: Optional[str]
    summary: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    rrf_score: Optional[float] = None
    max_similarity: Optional[float] = None
    rerank_score: Optional[float] = None
    #: How to open the original file (see ``fs.how_to_open``).
    fs: Optional[dict] = None
    chunks: list[Chunk] = field(default_factory=list)


@dataclass
class SearchResult:
    query: str
    total_documents: int
    total_chunks: int
    duration_ms: Optional[float]
    documents: list[Document]


@dataclass
class AskResponse:
    """Full answer of :meth:`RAGfly.ask`."""
    answer: str
    conversation_id: Optional[int]
    #: Remaining fields of the answer, e.g. ``message_id`` and ``user_message_id``.
    extra: dict = field(default_factory=dict)


@dataclass
class AgentLayer:
    code: str
    name: str
    sha256: str


@dataclass
class AgentContext:
    function_profile: str
    system_prompt: str
    system_prompt_hash: str
    layers: list[AgentLayer] = field(default_factory=list)
    identity: dict = field(default_factory=dict)
    tools: list[dict] = field(default_factory=list)
    limits: dict = field(default_factory=dict)
