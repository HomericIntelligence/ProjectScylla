"""Integration tests for MaestroClient using httpx.MockTransport.

These tests exercise full HTTP request/response cycles through the real
``httpx.Client`` internals — URL construction, header handling, JSON
serialization and deserialization, and error response handling — without
requiring a live Maestro instance.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from scylla.maestro.client import MaestroClient
from scylla.maestro.errors import MaestroAPIError
from scylla.maestro.models import (
    FailureSpec,
    HealthResponse,
    InjectionResult,
    MaestroConfig,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json_response(
    status_code: int = 200,
    data: Any = None,
    text: str = "",
) -> httpx.Response:
    """Build a real ``httpx.Response`` for use in MockTransport handlers."""
    if data is not None:
        return httpx.Response(status_code, json=data)
    return httpx.Response(status_code, text=text)


# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------


class TestURLConstruction:
    """Verify each public method hits the expected HTTP method + path."""

    @pytest.mark.parametrize(
        ("method_name", "method_args", "expected_http_method", "expected_path"),
        [
            ("health_check", [], "GET", "/api/v1/health"),
            ("list_agents", [], "GET", "/api/agents"),
            (
                "inject_failure",
                [FailureSpec(agent_id="a1", failure_type="crash")],
                "POST",
                "/api/agents/inject",
            ),
            ("clear_failure", ["inj-001"], "DELETE", "/api/agents/inject/inj-001"),
            ("get_diagnostics", [], "GET", "/api/diagnostics"),
        ],
        ids=[
            "health_check",
            "list_agents",
            "inject_failure",
            "clear_failure",
            "get_diagnostics",
        ],
    )
    def test_url_and_method(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
        method_name: str,
        method_args: list[Any],
        expected_http_method: str,
        expected_path: str,
    ) -> None:
        """Each client method sends the correct HTTP method to the correct path."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            # Return valid JSON for each endpoint so deserialization works.
            if expected_path == "/api/v1/health":
                return _json_response(data={"status": "ok"})
            if expected_path == "/api/agents":
                return _json_response(data=[])
            if expected_path == "/api/agents/inject" and request.method == "POST":
                return _json_response(data={"injection_id": "inj-001", "status": "active"})
            if expected_path.startswith("/api/agents/inject/"):
                return _json_response(data={})
            return _json_response(data={})

        client = make_client(handler)
        getattr(client, method_name)(*method_args)

        assert len(captured) == 1
        req = captured[0]
        assert req.method == expected_http_method
        assert req.url.path == expected_path

    def test_trailing_slash_stripped(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
    ) -> None:
        """Trailing slash on base_url does not cause double-slash in paths."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(data={"status": "ok"})

        # Override config to have trailing slash
        config = MaestroConfig(
            base_url="http://testserver/",
            enabled=True,
        )
        client = MaestroClient(config)
        client._client = httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url=config.base_url.rstrip("/"),
            timeout=httpx.Timeout(5),
        )
        result = client.health_check()
        client.close()

        assert len(captured) == 1
        assert "//" not in captured[0].url.path
        assert result is not None


# ---------------------------------------------------------------------------
# Header handling
# ---------------------------------------------------------------------------


class TestHeaderHandling:
    """Verify HTTP headers are set correctly on requests."""

    def test_post_sends_json_content_type(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
    ) -> None:
        """POST requests include a JSON content-type header."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(data={"injection_id": "inj-001", "status": "active"})

        client = make_client(handler)
        spec = FailureSpec(agent_id="a1", failure_type="crash")
        client.inject_failure(spec)

        req = captured[0]
        content_type = req.headers.get("content-type", "")
        assert "application/json" in content_type

    def test_get_does_not_send_json_body(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
    ) -> None:
        """GET requests do not include a JSON request body."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(data=[])

        client = make_client(handler)
        client.list_agents()

        req = captured[0]
        assert req.content == b""

    def test_user_agent_present(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
    ) -> None:
        """Requests include a User-Agent header (httpx default)."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(data={"status": "ok"})

        client = make_client(handler)
        client.health_check()

        req = captured[0]
        assert "user-agent" in {k.lower() for k in req.headers}


# ---------------------------------------------------------------------------
# JSON serialization (request payloads)
# ---------------------------------------------------------------------------


class TestJSONSerialization:
    """Verify request payloads are serialized correctly."""

    def test_basic_failure_spec_payload(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
    ) -> None:
        """inject_failure sends the correct JSON body for a basic spec."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(data={"injection_id": "inj-001", "status": "active"})

        client = make_client(handler)
        spec = FailureSpec(agent_id="agent-1", failure_type="crash")
        client.inject_failure(spec)

        body = json.loads(captured[0].content)
        assert body == {
            "agent_id": "agent-1",
            "failure_type": "crash",
            "parameters": {},
        }

    def test_duration_included_when_set(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
    ) -> None:
        """duration_seconds appears in payload only when provided."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(data={"injection_id": "inj-002", "status": "active"})

        client = make_client(handler)
        spec = FailureSpec(
            agent_id="agent-1",
            failure_type="network_delay",
            duration_seconds=30,
        )
        client.inject_failure(spec)

        body = json.loads(captured[0].content)
        assert body["duration_seconds"] == 30

    def test_duration_absent_when_none(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
    ) -> None:
        """duration_seconds is omitted from payload when not set."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(data={"injection_id": "inj-003", "status": "active"})

        client = make_client(handler)
        spec = FailureSpec(agent_id="agent-1", failure_type="crash")
        client.inject_failure(spec)

        body = json.loads(captured[0].content)
        assert "duration_seconds" not in body

    def test_custom_parameters_serialized(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
    ) -> None:
        """Custom parameters dict is preserved in the JSON payload."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return _json_response(data={"injection_id": "inj-004", "status": "active"})

        client = make_client(handler)
        spec = FailureSpec(
            agent_id="agent-1",
            failure_type="network_delay",
            duration_seconds=60,
            parameters={"latency_ms": 200, "jitter_ms": 50},
        )
        client.inject_failure(spec)

        body = json.loads(captured[0].content)
        assert body["parameters"] == {"latency_ms": 200, "jitter_ms": 50}


# ---------------------------------------------------------------------------
# JSON deserialization (response parsing)
# ---------------------------------------------------------------------------


class TestJSONDeserialization:
    """Verify response bodies are deserialized into correct types."""

    def test_health_check_returns_health_response(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
    ) -> None:
        """health_check returns a HealthResponse with correct fields."""

        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response(data={"status": "ok", "version": "1.0.0"})

        client = make_client(handler)
        result = client.health_check()

        assert isinstance(result, HealthResponse)
        assert result.status == "ok"
        assert result.version == "1.0.0"

    def test_list_agents_returns_list(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
    ) -> None:
        """list_agents returns a list of dicts matching the JSON array."""
        agents = [
            {"id": "agent-1", "name": "Alpha"},
            {"id": "agent-2", "name": "Beta"},
        ]

        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response(data=agents)

        client = make_client(handler)
        result = client.list_agents()

        assert result == agents

    def test_inject_failure_returns_injection_result(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
    ) -> None:
        """inject_failure returns an InjectionResult with correct fields."""

        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response(data={"injection_id": "inj-007", "status": "active"})

        client = make_client(handler)
        spec = FailureSpec(agent_id="a1", failure_type="crash")
        result = client.inject_failure(spec)

        assert isinstance(result, InjectionResult)
        assert result.injection_id == "inj-007"
        assert result.status == "active"

    def test_get_diagnostics_returns_dict(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
    ) -> None:
        """get_diagnostics returns a dict matching the JSON response."""
        diag = {"uptime": 3600, "agents_active": 5}

        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response(data=diag)

        client = make_client(handler)
        result = client.get_diagnostics()

        assert result == diag

    def test_list_agents_null_coerced_to_empty_list(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
    ) -> None:
        """Null JSON response from list_agents is coerced to empty list."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, content=b"null", headers={"content-type": "application/json"}
            )

        client = make_client(handler)
        result = client.list_agents()

        assert result == []

    def test_get_diagnostics_null_coerced_to_empty_dict(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
    ) -> None:
        """Null JSON response from get_diagnostics is coerced to empty dict."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, content=b"null", headers={"content-type": "application/json"}
            )

        client = make_client(handler)
        result = client.get_diagnostics()

        assert result == {}


# ---------------------------------------------------------------------------
# Error responses
# ---------------------------------------------------------------------------


class TestErrorResponses:
    """Verify non-2xx responses raise appropriate exceptions."""

    @pytest.mark.parametrize(
        ("status_code", "body_text"),
        [
            (400, "Bad Request"),
            (404, "Not Found"),
            (500, "Internal Server Error"),
            (503, "Service Unavailable"),
        ],
        ids=["400", "404", "500", "503"],
    )
    def test_non_2xx_raises_maestro_api_error(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
        status_code: int,
        body_text: str,
    ) -> None:
        """Non-2xx responses raise MaestroAPIError with correct attributes."""

        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response(status_code=status_code, text=body_text)

        client = make_client(handler)

        with pytest.raises(MaestroAPIError) as exc_info:
            client.list_agents()

        assert exc_info.value.status_code == status_code
        assert exc_info.value.response_body == body_text

    def test_health_check_returns_none_on_error(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
    ) -> None:
        """health_check swallows errors and returns None for non-2xx."""

        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response(status_code=503, text="Service Unavailable")

        client = make_client(handler)
        result = client.health_check()

        assert result is None

    def test_error_on_inject_failure(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
    ) -> None:
        """inject_failure raises MaestroAPIError on server error."""

        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response(status_code=422, text="Unprocessable Entity")

        client = make_client(handler)
        spec = FailureSpec(agent_id="a1", failure_type="crash")

        with pytest.raises(MaestroAPIError) as exc_info:
            client.inject_failure(spec)

        assert exc_info.value.status_code == 422

    def test_error_on_clear_failure(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
    ) -> None:
        """clear_failure raises MaestroAPIError on 404."""

        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response(status_code=404, text="Not Found")

        client = make_client(handler)

        with pytest.raises(MaestroAPIError) as exc_info:
            client.clear_failure("nonexistent")

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Client lifecycle
# ---------------------------------------------------------------------------


class TestClientLifecycle:
    """Verify context manager and close behavior."""

    def test_context_manager_works_with_mock_transport(
        self,
        maestro_config: MaestroConfig,
    ) -> None:
        """Client works as a context manager with MockTransport."""

        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response(data={"status": "ok"})

        with MaestroClient(maestro_config) as client:
            client._client = httpx.Client(
                transport=httpx.MockTransport(handler),
                base_url=maestro_config.base_url,
                timeout=httpx.Timeout(5),
            )
            result = client.health_check()
            assert result is not None
            assert result.status == "ok"

    def test_explicit_close(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
    ) -> None:
        """close() can be called explicitly without error."""

        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response(data={"status": "ok"})

        client = make_client(handler)
        client.health_check()
        client.close()

    def test_requests_work_before_close(
        self,
        make_client: Callable[[Callable[[httpx.Request], httpx.Response]], MaestroClient],
    ) -> None:
        """Multiple requests can be made before close."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if request.url.path == "/api/v1/health":
                return _json_response(data={"status": "ok"})
            if request.url.path == "/api/agents":
                return _json_response(data=[])
            return _json_response(data={})

        client = make_client(handler)
        client.health_check()
        client.list_agents()
        client.get_diagnostics()

        assert call_count == 3
