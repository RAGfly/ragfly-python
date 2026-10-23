# Changelog

## 0.7.0 — 2026-10-23

- New `unset_active_workspace()`: releases the workspace focus of a flexible key (`DELETE /v1/session/active-workspace`), the same as `set_active_workspace(None)`. A fixed-workspace key cannot release its workspace. Requires a RAGfly Cloud that serves that route.

## 0.6.0 — 2026-10-12

Vocabulary update: the credential's entity is now a **workspace** and a working space is now a **collection**. There are no aliases: the old names are removed.

- Renamed: `set_active_entity` -> `set_active_workspace(workspace_code)`; `list_spaces` -> `list_collections`; `get_space` -> `get_collection`; `refresh_space` -> `refresh_collection`; `promote_space` -> `save_collection`; `compose_spaces` -> `compose_collections`; `read_space` -> `read_collection`.
- Renamed parameters: `entity_code` -> `workspace_code`; `space_id` -> `collection_id` (also on `search`, `search_filtered`, `run_skill`); `space_id_a` / `space_id_b` -> `collection_id_a` / `collection_id_b`; `space_type` -> `collection_type` (`TEMPORARY` by default, `SAVED` for a saved collection; formerly `AREA` / `SPACE`); `entity_description` / `entity_system_prompt` -> `workspace_description` / `workspace_system_prompt`.
- REST routes called: `POST /v1/session/active-workspace`, `/v1/collections`, `/v1/collections/{id}`, `/v1/collections/compose`, `/v1/collections/{id}/read`, `/v1/collections/{id}/refresh` and `/v1/collections/{id}/save`.
- Responses keep the server's field names: `active_workspace`, `available_workspaces`, `collections[]`, `collection_id`, `scope` `WORKSPACE`.
- Requires a RAGfly Cloud that serves the new `/v1` vocabulary.

## 0.5.0 — 2026-10-08

- New `set_active_area(area_code)` (pass `None` to release the area focus and keep the entity), `list_areas()` and `list_locations()` with `entity_code`, `parent_code`, `query`, `limit` and `cursor` paging.
- `location_code` narrows `list_documents`, `search`, `search_filtered` and `ask` to one visible folder subtree, for that request only.

## 0.4.0 — 2026-10-07

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
