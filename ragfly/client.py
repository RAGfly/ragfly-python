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
        """Identity, group and active workspace of the credential."""
        return self._request("GET", "/v1/session")

    def set_active_workspace(self, workspace_code: Optional[str]) -> dict:
        """Set an authorized workspace focus; pass ``None`` to release it."""
        return self._request(
            "POST", "/v1/session/active-workspace", body={"workspace_code": workspace_code}
        )

    def set_active_area(self, area_code: Optional[str]) -> dict:
        """Set an authorized area focus (it also selects its workspace); pass ``None`` to release it."""
        return self._request("POST", "/v1/session/active-area", body={"area_code": area_code})

    def list_areas(
        self,
        *,
        workspace_code: Optional[str] = None,
        parent_code: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> dict:
        """Visible organizational areas and the cursor of the next page."""
        return self._request("GET", "/v1/areas", params={
            "workspace_code": workspace_code, "parent_code": parent_code, "query": query, "limit": limit, "cursor": cursor,
        })

    def list_locations(
        self,
        *,
        workspace_code: Optional[str] = None,
        parent_code: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> dict:
        """Visible document folders and the cursor of the next page. Their codes go in ``location_code``."""
        return self._request("GET", "/v1/locations", params={
            "workspace_code": workspace_code, "parent_code": parent_code, "query": query, "limit": limit, "cursor": cursor,
        })

    def list_documents(
        self, *, status: Optional[str] = None, limit: int = 20, page: int = 1, location_code: Optional[str] = None
    ) -> dict:
        """List documents. ``status`` in English, e.g. ``VECTORIZED``; ``location_code`` keeps one folder subtree."""
        return self._request("GET", "/v1/documents", params={
            "status": status, "limit": limit, "page": page, "location_code": location_code,
        })

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
        workspace_code: Optional[str] = None,
        collection_id: Optional[int] = None,
        location_code: Optional[str] = None,
    ) -> SearchResult:
        """Hybrid semantic search (vector + lexical).

        ``collection_id`` limits it to one collection; ``location_code`` to one visible folder subtree,
        for this request only.
        """
        return self._search({
            "query": query, "limit": limit, "min_similarity": min_similarity,
            "workspace_code": workspace_code, "collection_id": collection_id, "location_code": location_code,
        }, query)

    def search_filtered(
        self,
        query: str,
        *,
        filter: dict,
        limit: Optional[int] = None,
        min_similarity: Optional[float] = None,
        workspace_code: Optional[str] = None,
        collection_id: Optional[int] = None,
        location_code: Optional[str] = None,
    ) -> SearchResult:
        """Search with a structured ``filter`` (``document_types``, ``attributes``, ``characteristics``).

        The catalog codes the filter accepts come from :meth:`list_document_types` and
        :meth:`list_characteristics`.
        """
        if not isinstance(filter, dict):
            raise TypeError("filter must be a dict")
        return self._search({
            "query": query, "filter": filter, "limit": limit, "min_similarity": min_similarity,
            "workspace_code": workspace_code, "collection_id": collection_id, "location_code": location_code,
        }, query)

    def _search(self, body: dict, query: str) -> SearchResult:
        data = self._request("POST", "/v1/documents/search", body=_compact(body)) or {}
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

    # ── Collections ──────────────────────────────────────────────────────────

    def list_collections(self, *, limit: int = 20) -> dict:
        return self._request("GET", "/v1/collections", params={"limit": limit})

    def get_collection(self, collection_id: int, *, document_limit: int = 20) -> dict:
        return self._request("GET", f"/v1/collections/{_segment(collection_id)}", params={"document_limit": document_limit})

    def refresh_collection(self, collection_id: int) -> dict:
        return self._request("POST", f"/v1/collections/{_segment(collection_id)}/refresh")

    def save_collection(self, collection_id: int) -> dict:
        return self._request("POST", f"/v1/collections/{_segment(collection_id)}/save")

    def compose_collections(
        self, operation: str, collection_id_a: int, collection_id_b: int, *, name: str = "", collection_type: str = "TEMPORARY"
    ) -> dict:
        """``operation``: union, intersection, difference or symmetric_difference."""
        return self._request("POST", "/v1/collections/compose", body={
            "operation": operation, "collection_id_a": collection_id_a, "collection_id_b": collection_id_b,
            "name": name, "collection_type": collection_type,
        })

    def read_collection(self, collection_id: int, *, resolution: str = "manifest", query: str = "", limit: int = 50) -> dict:
        """``resolution``: count, manifest, chunks or text."""
        return self._request(
            "POST", f"/v1/collections/{_segment(collection_id)}/read",
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

    def list_document_types(self, *, workspace_code: Optional[str] = None) -> dict:
        """Document types of the workspace as a tree. Their codes go in ``filter.document_types``."""
        return self._request("GET", "/v1/catalog/document-types", params=_query({"workspace_code": workspace_code}))

    def list_characteristics(
        self, *, document_types: Optional[list] = None, workspace_code: Optional[str] = None
    ) -> dict:
        """Characteristics available for those types (each includes its more specific types)."""
        return self._request("GET", "/v1/catalog/characteristics", params=_query({
            "document_types": ",".join(document_types) if document_types else None, "workspace_code": workspace_code,
        }))

    def get_function(self, function_code: str) -> dict:
        """A function (screen) with its behaviors and the operations it allows."""
        return self._request("GET", f"/v1/functions/{_segment(function_code)}")

    def list_skills(self) -> dict:
        return self._request("GET", "/v1/skills")

    def get_skill(self, skill_code: str) -> dict:
        return self._request("GET", f"/v1/skills/{_segment(skill_code)}")

    def run_skill(self, skill_code: str, *, collection_id: Optional[int] = None, document_code: Optional[str] = None) -> dict:
        return self._request(
            "POST", f"/v1/skills/{_segment(skill_code)}/run",
            body=_compact({"collection_id": collection_id, "document_code": document_code}),
        )

    # ── Answers and agents ───────────────────────────────────────────────────

    def ask(
        self,
        question: str,
        *,
        conversation_id: Optional[int] = None,
        function_code: str = DEFAULT_FUNCTION,
        location_code: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> AskResponse:
        """RAG end to end: retrieve and generate. Reuse ``conversation_id`` to continue.

        ``mode="help"`` answers questions about RAGfly itself (how to use or integrate it)
        instead of searching your documents, without links to web screens. Left as ``None``
        the call is the usual document answer. ``location_code`` narrows only this request to one
        visible folder subtree.
        """
        if mode not in (None, "default", "help"):
            raise ValueError("mode must be 'default' or 'help'")
        data = self._request("POST", "/v1/ask", body=_compact({
            "question": question, "conversation_id": conversation_id, "function_code": function_code,
            "location_code": location_code, "mode": mode,
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

    def get_organization(self, *, workspace_code: Optional[str] = None) -> dict:
        return self._request("GET", "/v1/organization", params={"workspace_code": workspace_code})

    def update_organization(
        self,
        *,
        group_description: Optional[str] = None,
        group_system_prompt: Optional[str] = None,
        workspace_description: Optional[str] = None,
        workspace_system_prompt: Optional[str] = None,
        workspace_code: Optional[str] = None,
    ) -> dict:
        """Only the fields you pass are written."""
        return self._request("PUT", "/v1/organization", body=_compact({
            "group_description": group_description,
            "group_system_prompt": group_system_prompt,
            "workspace_description": workspace_description,
            "workspace_system_prompt": workspace_system_prompt,
            "workspace_code": workspace_code,
        }))

    def draft_organization(self, *, source_text: str = "", workspace_code: Optional[str] = None) -> dict:
        return self._request(
            "POST", "/v1/organization/draft", body=_compact({"source_text": source_text, "workspace_code": workspace_code})
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
