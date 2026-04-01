"""
ClawOS metricd System Tests
============================
Validates OTel span building, token counting, budget logic.
Runs without live Ollama.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

passed = 0
failed = 0


def ok(label):
    global passed; passed += 1
    print(f"  ✓  {label}")

def fail(label, reason=""):
    global failed; failed += 1
    msg = f"  ✗  {label}"
    if reason: msg += f"  [{reason}]"
    print(msg)


def test_token_usage_model():
    try:
        from clawos_core.models import TokenUsage
        span = TokenUsage(span_type="llm", model="qwen2.5:7b",
                          input_tokens=100, output_tokens=50)
        assert span.total_tokens == 150
        d = span.to_dict()
        assert d["span_type"] == "llm"
        ok("TokenUsage model and total_tokens correct")
    except Exception as e:
        fail("TokenUsage model", str(e))


def test_otel_span_builders():
    try:
        from services.metricd.otel import build_llm_span, build_tool_span
        llm = build_llm_span("qwen2.5:7b", 200, 80, 1200.5, "ws1", "task1", "C")
        assert llm.span_type == "llm"
        assert llm.total_tokens == 280
        tool = build_tool_span("fs.read", "/workspace/test.txt", "ALLOW", 12.0, "ws1")
        assert tool.span_type == "tool"
        assert tool.tool_decision == "ALLOW"
        ok("OTel LLM and tool span builders correct")
    except Exception as e:
        fail("OTel span builders", str(e))


def test_budget_add_and_get():
    try:
        from services.metricd import budget as b
        import time
        ws = f"test_ws_{int(time.time())}"
        b.add_tokens(ws, 1000)
        b.add_tokens(ws, 500)
        total = b.get_today(ws)
        assert total >= 1500, f"Expected >=1500 tokens, got {total}"
        ok(f"Budget add_tokens + get_today correct ({total} tokens)")
    except Exception as e:
        fail("Budget tracking", str(e))


def test_budget_over_limit():
    try:
        from services.metricd import budget as b
        import time
        ws = f"test_budget_limit_{int(time.time())}"
        b.add_tokens(ws, 200_000)
        over = b.is_over_budget(ws, daily_limit=100_000)
        assert over is True
        ok("Budget is_over_budget() triggers correctly")
    except Exception as e:
        fail("Budget over-limit detection", str(e))


def test_metrics_service_importable():
    try:
        from services.metricd.service import get_metrics
        m = get_metrics()
        assert hasattr(m, "record_llm")
        assert hasattr(m, "record_tool")
        assert hasattr(m, "is_over_budget")
        ok("MetricsService importable and has all methods")
    except Exception as e:
        fail("MetricsService importable", str(e))


def test_exporter_importable():
    try:
        from services.metricd.exporter import export_local, export_otlp
        ok("metricd exporter importable")
    except Exception as e:
        fail("metricd exporter importable", str(e))


def test_metricd_constants():
    try:
        from clawos_core.constants import PORT_METRICD, DEFAULT_DAILY_TOKEN_BUDGET, OTEL_JSONL
        assert PORT_METRICD == 7076
        assert DEFAULT_DAILY_TOKEN_BUDGET == 100_000
        ok(f"metricd constants correct (port={PORT_METRICD}, budget={DEFAULT_DAILY_TOKEN_BUDGET})")
    except Exception as e:
        fail("metricd constants", str(e))


if __name__ == "__main__":
    print("\n  ClawOS — metricd Tests\n  " + "─" * 40)
    test_token_usage_model()
    test_otel_span_builders()
    test_budget_add_and_get()
    test_budget_over_limit()
    test_metrics_service_importable()
    test_exporter_importable()
    test_metricd_constants()
    print(f"\n  {passed} passed  {failed} failed\n")
    sys.exit(0 if failed == 0 else 1)
