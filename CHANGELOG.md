# Changelog

## Unreleased

- `ask(..., mode="help")` answers questions about RAGfly itself (how to use or integrate it), without links to web screens. `mode` is only sent when given.
- `search(..., space_id=...)` limits a search to one working space.
- New `search_filtered(query, filter=...)`, `list_document_types()` and `list_characteristics()` for the structured `filter` of `/v1/documents/search`.

## 0.3.0

- Talks only to the English REST `/v1` contract. An API key no longer reaches internal routes, so 0.2.0 stops working with API keys.
- One method per `/v1` route, plus `list_operations`, `get_operation` and `run_operation` for every operation of the RAGfly application.
- English models: `Document(code, name, summary, …)`, `Chunk(text, page, extra)`, `SearchResult(total_documents, …)`, `AskResponse(answer, conversation_id, extra)`.
- `RAGflyError` carries the public `code` and `details`.
- Removed: `ask(stream=True)` (`/v1/ask` returns the full answer), the client-side code translator and the Spanish `estado` alias.
- Every request sends `X-RAGfly-Client: sdk-python`.
