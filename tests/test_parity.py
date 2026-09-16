"""Shared parity cases: the same calls produce the same /v1 requests in every SDK.

`tests/parity_cases.json` is a copy of the canonical file in the RAGfly backend
(`backend/baselines/agent_surface/sdk_parity_cases.json`); the TypeScript SDK runs
the identical file.
"""
import json
from pathlib import Path

import httpx
import pytest

from ragfly import RAGfly, RAGflyError

CASES = json.loads((Path(__file__).parent / "parity_cases.json").read_text())


def _client(handler):
    return RAGfly(api_key="rf_test", base_url="https://example.test", transport=httpx.MockTransport(handler))


def _reply(case):
    if case["method"] == "agent_context":
        return {"function_profile": "support_chat", "system_prompt": "P", "system_prompt_hash": "h", "layers": []}
    return {}


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda case: case["method"])
def test_parity_case(case):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_reply(case))

    with _client(handler) as client:
        getattr(client, case["method"])(**case["args"])

    [request] = seen
    expected = case["request"]
    assert request.method == expected["method"]
    assert request.url.raw_path.decode().split("?")[0] == expected["path"]
    assert dict(request.url.params) == expected["query"]
    assert (json.loads(request.content) if request.content else None) == expected["body"]
    assert request.headers["Authorization"] == "Bearer rf_test"
    assert request.headers[CASES["client_header"]["name"]] == CASES["client_header"]["python"]


def test_every_public_method_has_a_parity_case():
    public = {name for name in dir(RAGfly) if not name.startswith("_") and callable(getattr(RAGfly, name))}
    covered = {case["method"] for case in CASES["cases"]}
    assert public - {"close"} == covered


def test_public_errors_are_raised_with_code_and_details():
    def handler(request):
        return httpx.Response(422, json={"code": "VALIDATION_ERROR", "message": "The request could not be validated.",
                                         "details": {"unknown_fields": ["nombre"]}})

    with _client(handler) as client, pytest.raises(RAGflyError) as error:
        client.run_operation("document_types.update", {"nombre": "x"})
    assert error.value.status_code == 422
    assert error.value.code == "VALIDATION_ERROR"
    assert error.value.details == {"unknown_fields": ["nombre"]}


def test_write_confirm_preview_is_returned_as_is():
    preview = {"code": "document_types.delete", "kind": "write_confirm", "executed": False,
               "confirm_required": True, "preview": {"input": {"code": "T"}}}

    def handler(request):
        assert json.loads(request.content) == {"input": {"code": "T"}, "confirm": False}
        return httpx.Response(200, json=preview)

    with _client(handler) as client:
        assert client.run_operation("document_types.delete", {"code": "T"}) == preview
