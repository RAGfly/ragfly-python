from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Chunk:
    texto: str
    similitud: Optional[float] = None
    score_rerank: Optional[float] = None
    pagina: Optional[int] = None
    extra: dict = field(default_factory=dict)


@dataclass
class Document:
    codigo: str
    nombre: str
    resumen: Optional[str] = None
    url: Optional[str] = None
    rrf_score: Optional[float] = None
    similitud_max: Optional[float] = None
    chunks: list[Chunk] = field(default_factory=list)


@dataclass
class SearchResult:
    query: str
    total_documentos: int
    total_chunks: int
    duracion_ms: Optional[float]
    documents: list[Document]


@dataclass
class AskChunk:
    """Un token/fragmento del stream de respuesta."""
    delta: str


@dataclass
class AskResponse:
    """Respuesta completa (no-streaming)."""
    answer: str
    conversation_id: int
    message_id: Optional[int] = None


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
