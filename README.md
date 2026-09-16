# RAGfly Python SDK

Official Python client for [RAGfly](https://ragfly.ai). It speaks the English REST `/v1` contract.

> Using TypeScript/JavaScript? See the [TypeScript SDK](https://github.com/RAGfly/ragfly-typescript) (`npm install @ragfly/sdk`) — same surface.

## Install

```bash
pip install ragfly
```

## Quick start

```python
from ragfly import RAGfly

client = RAGfly(api_key="rf_...")

# RAG end to end
print(client.ask("What are the Q1 sales figures?").answer)

# Retrieval only
results = client.search("maintenance contracts", limit=5)
for doc in results.documents:
    print(doc.name, doc.max_similarity)
```

## Operations

Everything the RAGfly application lets your user do is available as an operation, with the same permissions and audit as the web app.

```python
ops = client.list_operations()["operations"]              # what this key can run
schema = client.get_operation("document_types.update")    # input_schema / output_schema

client.run_operation("document_types.update", {"code": "TDOC_...", "name": "Invoices"})

# write_confirm operations (deletes, reverts, resets) need confirm=True
preview = client.run_operation("document_types.delete", {"code": "TDOC_..."})
assert preview["executed"] is False
client.run_operation("document_types.delete", {"code": "TDOC_..."}, confirm=True)
```

Errors raise `RAGflyError` with `status_code`, the public `code` (`NOT_FOUND`, `VALIDATION_ERROR`, …) and `details`.

## API keys

Create an API key from [app.ragfly.ai](https://app.ragfly.ai) → API Keys. A key only works on `/v1`; creating or revoking keys needs a signed-in person.

## Methods

| Area | Methods |
|------|---------|
| Session and documents | `session`, `list_documents`, `get_document`, `document_edges`, `search` |
| Working spaces | `list_spaces`, `get_space`, `refresh_space`, `promote_space`, `compose_spaces`, `read_space` |
| Queue, catalog, skills | `queue`, `list_runs`, `catalog`, `get_function`, `list_skills`, `get_skill`, `run_skill` |
| Answers and agents | `ask`, `agent_context`, `run_agent_tool` |
| Organization | `get_organization`, `update_organization`, `draft_organization` |
| Usage, conversations, processes | `get_usage`, `list_conversations`, `delete_conversation`, `list_processes`, `get_process`, `update_process` |
| Operations | `list_operations`, `get_operation`, `run_operation` |

## Links

- Docs: https://api.ragfly.ai/docs
- Site: https://ragfly.ai
