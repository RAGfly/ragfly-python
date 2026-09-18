"""RAGfly Python SDK — official client for the English REST ``/v1`` contract."""

from typing import Any, Optional
from urllib.parse import quote

import httpx

from .models import AgentContext, AgentLayer, AskResponse, Chunk, Document, SearchResult

DEFAULT_BASE_URL = "https://api.ragfly.ai"
#: Default interface function for ``ask()`` (sets the conversation's LLM model).
DEFAULT_FUNCTION = "CHAT-USER"
CLIENT_HEADER = {"X-RAGfly-Client": "sdk-python"}


class RAGflyError(Exception):
    """A ``/v1`` error: ``status_code``, public ``code`` (e.g. ``NOT_FOUND``) and ``details``."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        code: Optional[str] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.details = details or {}


def _segment(value: Any) -> str:
    return quote(str(value), safe="")


def _compact(values: dict) -> dict:
    return {key: value for key, value in values.items() if value is not None}


def _query(values: dict) -> dict:
    return {key: ("true" if value is True else "false" if value is False else value) for key, value in _compact(values).items()}


class RAGfly:
    """Official RAGfly client.

    Basic usage::

        from ragfly import RAGfly

        client = RAGfly(api_key="rf_...")
        print(client.ask("What were Q1 sales?").answer)

    Every method maps to one ``/v1`` route. Operations of the RAGfly
    application that have no named route run through :meth:`list_operations`,
    :meth:`get_operation` and :meth:`run_operation`.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
        *,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=10.0),
            headers={"Authorization": f"Bearer {api_key}", **CLIENT_HEADER},
            transport=transport,
        )

    # ── Transport ────────────────────────────────────────────────────────────

    def _request(self, method: str, path: str, *, params: Optional[dict] = None, body: Any = None) -> Any:
        resp = self._http.request(
            method,
            f"{self._base_url}{path}",
            params=_query(params or {}) or None,
            json=body,
        )
        if resp.status_code >= 400:
            try:
                payload = resp.json()
            except ValueError:
                payload = {}
            payload = payload if isinstance(payload, dict) else {}
            raise RAGflyError(
                payload.get("message") or resp.text or f"HTTP {resp.status_code}",
                status_code=resp.status_code,
                code=payload.get("code"),
                details=payload.get("details"),
            )
        if not resp.content:
            return None
        return resp.json()

    # ── Session and documents ────────────────────────────────────────────────

    def session(self) -> dict:
        """Identity, group and entity of the credential."""
        return self._request("GET", "/v1/session")

    def list_documents(self, *, status: Optional[str] = None, limit: int = 20, page: int = 1) -> dict:
        """List documents. ``status`` in English, e.g. ``VECTORIZED``."""
        return self._request("GET", "/v1/documents", params={"status": status, "limit": limit, "page": page})

    def get_document(self, document_code: str) -> dict:
        return self._request("GET", f"/v1/documents/{_segment(document_code)}")

    def document_edges(self, document_code: str, *, neighbor_limit: int = 50) -> dict:
        return self._request(
            "GET", f"/v1/documents/{_segment(document_code)}/edges", params={"neighbor_limit": neighbor_limit}
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        min_similarity: float = 0.0,
        entity_code: Optional[str] = None,
    ) -> SearchResult:
        """Hybrid semantic search (vector + lexical)."""
        data = self._request(
            "POST",
            "/v1/documents/search",
            body=_compact({"query": query, "limit": limit, "min_similarity": min_similarity, "entity_code": entity_code}),
        ) or {}
        documents = [
            Document(
                code=d.get("code"),
                name=d.get("name"),
                summary=d.get("summary"),
                location=d.get("location"),
                url=d.get("url"),
                rrf_score=d.get("rrf_score"),
                max_similarity=d.get("max_similarity"),
                rerank_score=d.get("rerank_score"),
                fs=d.get("fs"),
                chunks=[
                    Chunk(text=c.get("text", ""), page=c.get("page"), extra=c.get("extra") or {})
                    for c in d.get("chunks") or []
                ],
            )
            for d in data.get("documents") or []
        ]
        return SearchResult(
            query=query,
            total_documents=data.get("total_documents", len(documents)),
            total_chunks=data.get("total_chunks", 0),
            duration_ms=data.get("duration_ms"),
            documents=documents,
        )

    # ── Working spaces ───────────────────────────────────────────────────────

    def list_spaces(self, *, limit: int = 20) -> dict:
        return self._request("GET", "/v1/spaces", params={"limit": limit})

    def get_space(self, space_id: int, *, document_limit: int = 20) -> dict:
        return self._request("GET", f"/v1/spaces/{_segment(space_id)}", params={"document_limit": document_limit})

    def refresh_space(self, space_id: int) -> dict:
        return self._request("POST", f"/v1/spaces/{_segment(space_id)}/refresh")

    def promote_space(self, space_id: int) -> dict:
        return self._request("POST", f"/v1/spaces/{_segment(space_id)}/promote")

    def compose_spaces(
        self, operation: str, space_id_a: int, space_id_b: int, *, name: str = "", space_type: str = "AREA"
    ) -> dict:
        """``operation``: union, intersection, difference or symmetric_difference."""
        return self._request("POST", "/v1/spaces/compose", body={
            "operation": operation, "space_id_a": space_id_a, "space_id_b": space_id_b,
            "name": name, "space_type": space_type,
        })

    def read_space(self, space_id: int, *, resolution: str = "manifest", query: str = "", limit: int = 50) -> dict:
        """``resolution``: count, manifest, chunks or text."""
        return self._request(
            "POST", f"/v1/spaces/{_segment(space_id)}/read",
            body={"resolution": resolution, "query": query, "limit": limit},
        )

    # ── Queue, catalog and skills ────────────────────────────────────────────

    def queue(self, *, process: Optional[str] = None, status: Optional[str] = None, limit: int = 20) -> dict:
        return self._request("GET", "/v1/queue", params={"process": process, "status": status, "limit": limit})

    def list_runs(self, *, limit: int = 10) -> dict:
        return self._request("GET", "/v1/runs", params={"limit": limit})

    def catalog(self, *, type: str = "ALL") -> dict:
        """``type``: ALL, FUNCTIONS or SKILLS."""
        return self._request("GET", "/v1/catalog", params={"type": type})

    def get_function(self, function_code: str) -> dict:
        """A function (screen) with its behaviors and the operations it allows."""
        return self._request("GET", f"/v1/functions/{_segment(function_code)}")

    def list_skills(self) -> dict:
        return self._request("GET", "/v1/skills")

    def get_skill(self, skill_code: str) -> dict:
        return self._request("GET", f"/v1/skills/{_segment(skill_code)}")

    def run_skill(self, skill_code: str, *, space_id: Optional[int] = None, document_code: Optional[str] = None) -> dict:
        return self._request(
            "POST", f"/v1/skills/{_segment(skill_code)}/run",
            body=_compact({"space_id": space_id, "document_code": document_code}),
        )

    # ── Answers and agents ───────────────────────────────────────────────────

    def ask(
        self, question: str, *, conversation_id: Optional[int] = None, function_code: str = DEFAULT_FUNCTION
    ) -> AskResponse:
        """RAG end to end: retrieve and generate. Reuse ``conversation_id`` to continue."""
        data = self._request("POST", "/v1/ask", body=_compact({
            "question": question, "conversation_id": conversation_id, "function_code": function_code,
        })) or {}
        return AskResponse(
            answer=data.get("answer", ""),
            conversation_id=data.get("conversation_id"),
            extra={k: v for k, v in data.items() if k not in {"answer", "conversation_id"}},
        )

    def agent_context(self, *, function_profile: str = "user_chat") -> AgentContext:
        """The authenticated prompt, identity and tools for an agent."""
        data = self._request("GET", "/v1/agent/context", params={"function_profile": function_profile})
        return AgentContext(
            function_profile=data["function_profile"],
            system_prompt=data["system_prompt"],
            system_prompt_hash=data["system_prompt_hash"],
            # Only the model's fields: a field the server adds later must not break the client.
            layers=[
                AgentLayer(code=item.get("code", ""), name=item.get("name", ""), sha256=item.get("sha256", ""))
                for item in data.get("layers", [])
                if isinstance(item, dict)
            ],
            identity=data.get("identity") or {},
            tools=data.get("tools") or [],
            limits=data.get("limits") or {},
        )

    def run_agent_tool(self, public_name: str, arguments: dict, *, function_profile: str = "user_chat") -> Any:
        """Run one tool authorized by :meth:`agent_context`."""
        if not isinstance(arguments, dict):
            raise TypeError("arguments must be a dict")
        return self._request(
            "POST", f"/v1/agent/tools/{_segment(public_name)}",
            body={"arguments": arguments, "function_profile": function_profile},
        )

    # ── Organization profile ─────────────────────────────────────────────────

    def get_organization(self, *, entity_code: Optional[str] = None) -> dict:
        return self._request("GET", "/v1/organization", params={"entity_code": entity_code})

    def update_organization(
        self,
        *,
        group_description: Optional[str] = None,
        group_system_prompt: Optional[str] = None,
        entity_description: Optional[str] = None,
        entity_system_prompt: Optional[str] = None,
        entity_code: Optional[str] = None,
    ) -> dict:
        """Only the fields you pass are written."""
        return self._request("PUT", "/v1/organization", body=_compact({
            "group_description": group_description,
            "group_system_prompt": group_system_prompt,
            "entity_description": entity_description,
            "entity_system_prompt": entity_system_prompt,
            "entity_code": entity_code,
        }))

    def draft_organization(self, *, source_text: str = "", entity_code: Optional[str] = None) -> dict:
        return self._request(
            "POST", "/v1/organization/draft", body=_compact({"source_text": source_text, "entity_code": entity_code})
        )

    # ── Usage, conversations and processes ───────────────────────────────────

    def get_usage(self) -> dict:
        return self._request("GET", "/v1/usage")

    def list_conversations(self, *, function_code: Optional[str] = None, limit: int = 50) -> dict:
        return self._request("GET", "/v1/conversations", params={"function_code": function_code, "limit": limit})

    def delete_conversation(self, conversation_id: int) -> Any:
        return self._request("DELETE", f"/v1/conversations/{_segment(conversation_id)}")

    def list_processes(
        self,
        *,
        status: Optional[str] = None,
        process_type: Optional[str] = None,
        category: Optional[str] = None,
        mine: Optional[bool] = None,
        only_open: Optional[bool] = None,
        limit: int = 20,
        page: int = 1,
    ) -> dict:
        return self._request("GET", "/v1/processes", params={
            "status": status, "process_type": process_type, "category": category,
            "mine": mine, "only_open": only_open, "limit": limit, "page": page,
        })

    def get_process(self, process_code: str) -> dict:
        return self._request("GET", f"/v1/processes/{_segment(process_code)}")

    def update_process(
        self,
        process_code: str,
        *,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        comments: Optional[str] = None,
        assigned_to: Optional[str] = None,
        due_at: Optional[str] = None,
        finished_at: Optional[str] = None,
        cost: Optional[float] = None,
    ) -> dict:
        """Only the fields you pass are written."""
        return self._request("PATCH", f"/v1/processes/{_segment(process_code)}", body=_compact({
            "status": status, "priority": priority, "name": name, "description": description,
            "comments": comments, "assigned_to": assigned_to, "due_at": due_at,
            "finished_at": finished_at, "cost": cost,
        }))

    # ── Generic operations ───────────────────────────────────────────────────

    def list_operations(self) -> dict:
        """Operations this credential can run: code, kind and confirm_required."""
        return self._request("GET", "/v1/operations")

    def get_operation(self, code: str) -> dict:
        """One operation with its ``input_schema`` and ``output_schema``."""
        return self._request("GET", f"/v1/operations/{_segment(code)}")

    def run_operation(self, code: str, input: Optional[dict] = None, *, confirm: bool = False) -> dict:
        """Run an operation. A ``write_confirm`` operation only runs with ``confirm=True``;
        without it the result is ``{"executed": False, "preview": ...}``."""
        return self._request(
            "POST", f"/v1/operations/{_segment(code)}:execute",
            body={"input": input or {}, "confirm": bool(confirm)},
        )

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
