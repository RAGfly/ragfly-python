"""RAGfly Python SDK — cliente oficial."""

import json
from typing import Generator, Iterator, Optional, Union
from urllib.parse import urljoin

import httpx

from .codes import CodeTranslator
from .models import AskChunk, AskResponse, Chunk, Document, SearchResult

DEFAULT_BASE_URL = "https://api.ragfly.ai"
# Esquema de timeouts del SDK (h.210):
# - Requests normales: `timeout` del constructor (default 60s, connect 10s).
# - Streaming SSE (ask stream=True y ask sync, que lo reusa): SIN read-timeout
#   (Timeout(None, connect=10.0)) porque la generación LLM puede superar
#   cualquier tope entre tokens; el truncamiento se detecta por el evento
#   'done' y la validación de líneas (no por timeout).
#: Default interface function for ``ask()`` (sets the conversation's LLM model).
#: English public code; the SDK translates it to the internal code on the wire.
DEFAULT_FUNCION = "CHAT-USER"


class RAGflyError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class RAGfly:
    """Official RAGfly client.

    Basic usage::

        from ragfly import RAGfly

        client = RAGfly(api_key="slm_live_...")
        resp = client.ask("What were Q1 sales?")
        print(resp.answer)

    Streaming::

        for chunk in client.ask("What were Q1 sales?", stream=True):
            print(chunk.delta, end="", flush=True)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=10.0),
            headers={"Authorization": f"Bearer {api_key}"},
        )
        self._async_http: Optional[httpx.AsyncClient] = None
        # Public-code translator: English on the SDK surface, internal on the wire.
        self._codes = CodeTranslator(self._fetch_code_map)

    # ── Internos ─────────────────────────────────────────────────────────────

    def _url(self, path: str) -> str:
        return f"{self._base_url}/{path.lstrip('/')}"

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise RAGflyError(detail, status_code=resp.status_code)

    def _get_or_create_conversation(self, codigo_funcion: str = DEFAULT_FUNCION) -> int:
        """Create a new conversation and return its id."""
        resp = self._http.post(self._url("/interfaz/conversaciones"), json={
            "titulo": "SDK",
            "codigo_funcion": self._codes.to_internal("function", codigo_funcion),
        })
        self._raise_for_status(resp)
        return resp.json()["id_conversacion"]

    def _fetch_code_map(self) -> dict:
        """Fetch the public-code map (internal → English) from the backend. Used by
        the code translator; the map is cached after the first call."""
        resp = self._http.get(
            self._url("/catalogo/public-codes"),
            params={"domains": "status,doc_type,function"},
        )
        self._raise_for_status(resp)
        return resp.json().get("domains", {})

    # ── API pública ──────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        min_similitud: float = 0.0,
        codigo_entidad: Optional[str] = None,
        id_espacio: Optional[int] = None,
    ) -> SearchResult:
        """Hybrid semantic search (vector + lexical + rerank).

        Returns:
            :class:`SearchResult` with the matching documents and their relevant chunks.
        """
        payload = {
            "q": query,
            "limit": limit,
            "min_similitud": min_similitud,
        }
        if codigo_entidad:
            payload["codigo_entidad"] = codigo_entidad
        if id_espacio:
            payload["id_espacio"] = id_espacio

        resp = self._http.post(self._url("/documentos/buscar-semantico"), json=payload)
        self._raise_for_status(resp)
        data = resp.json()

        docs = []
        for d in data.get("resultados", []):
            chunks = [
                Chunk(
                    texto=c.get("texto", ""),
                    similitud=c.get("similitud"),
                    score_rerank=c.get("score_rerank"),
                    # La API expone el nº de página como `nro_pagina` (no `pagina`).
                    pagina=c.get("nro_pagina"),
                    extra={k: v for k, v in c.items() if k not in {"texto", "similitud", "score_rerank", "nro_pagina"}},
                )
                for c in d.get("chunks", [])
            ]
            docs.append(Document(
                codigo=d["codigo_documento"],
                nombre=d["nombre_documento"],
                resumen=d.get("resumen_documento"),
                url=d.get("url"),
                rrf_score=d.get("rrf_score"),
                similitud_max=d.get("similitud_max"),
                chunks=chunks,
            ))

        return SearchResult(
            query=data["q"],
            total_documentos=data["total_documentos"],
            total_chunks=data["total_chunks"],
            duracion_ms=data.get("duracion_ms"),
            documents=docs,
        )

    def ask(
        self,
        question: str,
        *,
        conversation_id: Optional[int] = None,
        codigo_funcion: str = DEFAULT_FUNCION,
        stream: bool = False,
    ) -> Union[AskResponse, Iterator[AskChunk]]:
        """Ask the RAG for a full or streaming answer.

        Args:
            question: The natural-language question.
            conversation_id: Reuse an existing conversation. If None, a new one is created.
            codigo_funcion: Interface function that sets the LLM model when creating a
                new conversation. Default ``CHAT-USER``. Ignored when ``conversation_id``
                is given.
            stream: If True, returns an iterator of :class:`AskChunk`.

        Returns:
            :class:`AskResponse` (stream=False) or ``Iterator[AskChunk]`` (stream=True).
        """
        conv_id = conversation_id or self._get_or_create_conversation(codigo_funcion)

        if stream:
            return self._ask_stream(question, conv_id)
        return self._ask_sync(question, conv_id)

    def _ask_stream(self, question: str, conv_id: int) -> Iterator[AskChunk]:
        url = self._url(f"/interfaz/conversaciones/{conv_id}/mensajes/stream")
        # En streaming NO aplicamos read-timeout: la generación del LLM puede tardar
        # más que el timeout normal entre tokens, y abortaría el SSE a mitad de
        # respuesta (httpx.ReadTimeout). Mantenemos solo el connect-timeout. Espejo
        # del SDK TS, que cancela su timer al recibir los headers de respuesta.
        with self._http.stream(
            "POST", url, json={"contenido": question},
            timeout=httpx.Timeout(None, connect=10.0),
        ) as resp:
            self._raise_for_status(resp)
            recibio_done = False
            lineas_malformadas = 0
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue  # comentarios SSE (': ping' heartbeat) y líneas vacías
                try:
                    payload = json.loads(line[6:])
                except json.JSONDecodeError:
                    # El backend solo emite JSON en líneas 'data:' — una línea
                    # malformada es un evento perdido (corte intra-evento, h.217).
                    lineas_malformadas += 1
                    continue
                if "error" in payload:
                    raise RAGflyError(payload["error"])
                if payload.get("done"):
                    if lineas_malformadas:
                        raise RAGflyError(
                            f"El stream llegó al 'done' pero {lineas_malformadas} "
                            "evento(s) 'data:' venían malformados — la respuesta "
                            "puede tener huecos."
                        )
                    recibio_done = True
                    return
                if "text" in payload:
                    yield AskChunk(delta=payload["text"])
            # El stream cerró sin el evento `done` final: respuesta truncada
            # (corte de red, timeout del proxy). No devolver una respuesta
            # parcial como si fuera completa — propagar como error.
            if not recibio_done:
                raise RAGflyError(
                    "El stream de respuesta se cortó antes de terminar "
                    "(sin evento 'done'); la respuesta puede estar incompleta."
                )

    def _ask_sync(self, question: str, conv_id: int) -> AskResponse:
        buffer = []
        msg_id = None
        for chunk in self._ask_stream(question, conv_id):
            buffer.append(chunk.delta)
        # El done payload lleva id_mensaje_assistant pero lo emitimos antes de salir
        # del generator — capturamos el último evento done fuera del yield.
        return AskResponse(
            answer="".join(buffer),
            conversation_id=conv_id,
            message_id=msg_id,
        )

    def list_documents(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        estado: Optional[str] = None,
    ) -> dict:
        """List documents in the corpus with pagination.

        Args:
            status: Filter by processing state, in English — e.g. ``VECTORIZED``,
                ``SCANNED``, ``CHUNKED``, ``LOADED``. Use ``VECTORIZED`` to list only
                documents that are searchable.
            estado: Deprecated Spanish alias of ``status`` (kept for compatibility).
        """
        # The REST API (GET /documentos/paginado) speaks internal codes; translate the
        # English public state on the way in and the returned codes on the way out.
        status = status or estado
        params: dict = {"page": page, "limit": page_size}
        if status:
            params["codigo_estado_doc"] = self._codes.to_internal("status", status)
        resp = self._http.get(self._url("/documentos/paginado"), params=params)
        self._raise_for_status(resp)
        return self._translate_documents(resp.json())

    def _translate_documents(self, data: dict) -> dict:
        """Translate internal catalog codes to their English public alias in a
        documents response (state + document type of every row)."""
        if not isinstance(data, dict):
            return data
        rows = data.get("items") or data.get("documentos") or data.get("resultados") or []
        for doc in rows:
            if not isinstance(doc, dict):
                continue
            if doc.get("codigo_estado_doc"):
                doc["codigo_estado_doc"] = self._codes.to_english("status", doc["codigo_estado_doc"])
            if doc.get("codigo_tipo_documento"):
                doc["codigo_tipo_documento"] = self._codes.to_english("doc_type", doc["codigo_tipo_documento"])
        return data

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
