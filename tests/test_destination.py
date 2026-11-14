"""`destination` reads a published corpus: the SDK sends it as given and omits it when absent."""
import json

import httpx

from ragfly import RAGfly


def _client(calls, reply):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=reply)
    return RAGfly(api_key="rf_test", base_url="https://example.test", transport=httpx.MockTransport(handler))


def test_search_sends_destination():
    calls: list = []
    destino = {"module": "regulation", "country": "CL", "workspace_code": "W1", "area_code": "A1"}
    _client(calls, {"documents": []}).search("board meetings", destination=destino)
    assert calls[0].url.path == "/v1/documents/search"
    assert json.loads(calls[0].content)["destination"] == destino


def test_ask_sends_destination_only_when_given():
    calls: list = []
    sdk = _client(calls, {"answer": "A", "conversation_id": 1})
    sdk.ask("Which rule applies?", destination={"module": "regulation", "country": "CL"})
    sdk.ask("Which rule applies?")
    assert json.loads(calls[0].content)["destination"] == {"module": "regulation", "country": "CL"}
    assert "destination" not in json.loads(calls[1].content)
