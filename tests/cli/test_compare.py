# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for compare — side-by-side model comparison."""
import json
from unittest.mock import patch, MagicMock
from clawctl.commands.compare import (
    ModelResponse, CompareSession,
    _query_ollama, run_compare, run_compare_parallel,
)


class TestModelResponse:
    def test_defaults(self):
        r = ModelResponse(model="test:7b", response="hello")
        assert r.error == ""
        assert r.tokens_per_sec == 0.0

    def test_to_dict(self):
        r = ModelResponse(model="qwen:7b", response="hi", tokens_per_sec=42.3, total_tokens=100, duration_ms=2500)
        d = r.to_dict()
        assert d["model"] == "qwen:7b"
        assert d["tokens_per_sec"] == 42.3
        assert d["duration_ms"] == 2500


class TestCompareSession:
    def test_create(self):
        s = CompareSession(prompt="test prompt", models=["a", "b"])
        assert s.responses == []

    def test_to_dict(self):
        s = CompareSession(prompt="q", models=["m1"])
        s.responses.append(ModelResponse(model="m1", response="answer"))
        d = s.to_dict()
        assert d["prompt"] == "q"
        assert len(d["responses"]) == 1


class TestQueryOllama:
    def test_success(self):
        mock_data = {
            "response": "The answer is 42.",
            "eval_count": 50,
            "eval_duration": 500_000_000,  # 0.5s in nanoseconds
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_data).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _query_ollama("test:7b", "What is the answer?")
            assert result.model == "test:7b"
            assert result.response == "The answer is 42."
            assert result.total_tokens == 50
            # duration_ms may be 0 in mocked fast execution, that's ok
            assert result.duration_ms >= 0

    def test_connection_error(self):
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            result = _query_ollama("test:7b", "prompt")
            assert result.error != ""
            assert result.response == ""


class TestRunCompare:
    def test_sequential(self):
        CompareSession(prompt="test", models=["m1", "m2"])
        mock_resp = ModelResponse(model="m1", response="a1", total_tokens=10, duration_ms=100)
        mock_resp2 = ModelResponse(model="m2", response="a2", total_tokens=20, duration_ms=200)

        with patch("clawctl.commands.compare._query_ollama", side_effect=[mock_resp, mock_resp2]):
            result = run_compare("test", ["m1", "m2"])
            assert len(result.responses) == 2
            assert result.responses[0].model == "m1"
            assert result.responses[1].model == "m2"

    def test_parallel(self):
        mock_resp = ModelResponse(model="m1", response="a1", total_tokens=10, duration_ms=100)
        mock_resp2 = ModelResponse(model="m2", response="a2", total_tokens=20, duration_ms=200)

        with patch("clawctl.commands.compare._query_ollama", side_effect=[mock_resp, mock_resp2]):
            result = run_compare_parallel("test", ["m1", "m2"])
            assert len(result.responses) == 2
            models = [r.model for r in result.responses]
            assert "m1" in models
            assert "m2" in models