import json

import httpx

from ragfly import RAGfly


def test_agent_context_maps_contract():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/agent/context"
        assert request.url.params["function_profile"] == "chat_soporte"
        return httpx.Response(200, json={
            "function_profile": "chat_soporte",
            "system_prompt": "CAPAS",
            "system_prompt_hash": "abc",
            "layers": [{"code": "PRODUCT", "name": "Producto", "sha256": "p"}],
            "identity": {"group": "CAB LTDA"},
            "tools": [],
            "limits": {"max_iterations": 8},
        })

    client = RAGfly(api_key="test", base_url="https://example.test")
    client._http.close()
    client._http = httpx.Client(transport=httpx.MockTransport(handler))

    context = client.agent_context(function_profile="chat_soporte")

    assert context.function_profile == "chat_soporte"
    assert context.layers[0].code == "PRODUCT"
    assert context.identity["group"] == "CAB LTDA"
    client.close()


def test_run_agent_tool_posts_arguments_without_scope_overrides():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"ok": True})

    client = RAGfly(api_key="test", base_url="https://example.test")
    client._http.close()
    client._http = httpx.Client(transport=httpx.MockTransport(handler))

    result = client.run_agent_tool(
        "leer_md",
        {"origen": "CONCEPTO", "codigo": "RAGFLY_ROOT"},
        function_profile="chat_soporte",
    )

    request = captured["request"]
    assert result == {"ok": True}
    assert request.url.path == "/agent/tools/leer_md"
    assert request.url.params["function_profile"] == "chat_soporte"
    payload = json.loads(request.content)
    assert payload == {
        "arguments": {"origen": "CONCEPTO", "codigo": "RAGFLY_ROOT"},
    }
    assert "codigo_grupo" not in payload
    client.close()
