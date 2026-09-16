import httpx

from ragfly import RAGfly


def test_agent_context_maps_contract():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/agent/context"
        return httpx.Response(200, json={
            "function_profile": "support_chat",
            "system_prompt": "LAYERS",
            "system_prompt_hash": "abc",
            "layers": [{"code": "PRODUCT", "name": "Product", "sha256": "p"}],
            "identity": {"group": "CAB LTDA"},
            "tools": [],
            "limits": {"max_iterations": 8},
        })

    with RAGfly(api_key="rf_test", base_url="https://example.test", transport=httpx.MockTransport(handler)) as client:
        context = client.agent_context(function_profile="support_chat")

    assert context.function_profile == "support_chat"
    assert context.layers[0].code == "PRODUCT"
    assert context.identity["group"] == "CAB LTDA"


def test_search_and_ask_map_the_english_contract():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/documents/search":
            return httpx.Response(200, json={
                "documents": [{"code": "D1", "name": "Contract", "rrf_score": 0.4, "max_similarity": 0.8,
                               "fs": {"is_cloud_only": False}, "chunks": [{"text": "clause", "page": 2, "extra": {"similarity": 0.8}}]}],
                "total_documents": 1, "total_chunks": 1, "duration_ms": 12,
            })
        return httpx.Response(200, json={"conversation_id": 9, "answer": "Yes.", "citations": []})

    with RAGfly(api_key="rf_test", base_url="https://example.test", transport=httpx.MockTransport(handler)) as client:
        result = client.search("contract")
        answer = client.ask("Is it signed?")

    assert result.total_documents == 1
    assert result.documents[0].name == "Contract"
    assert result.documents[0].chunks[0].text == "clause"
    assert answer.answer == "Yes." and answer.conversation_id == 9
    assert answer.extra == {"citations": []}
