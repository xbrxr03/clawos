"""
Span exporter — writes TokenUsage spans to local JSONL.
Optional OTLP remote export when configured.
"""
import json
import logging
from pathlib import Path
from clawos_core.constants import OTEL_JSONL
from clawos_core.models import TokenUsage

log = logging.getLogger("metricd")


def export_local(span: TokenUsage):
    """Append span as JSONL line to logs/otel.jsonl."""
    try:
        OTEL_JSONL.parent.mkdir(parents=True, exist_ok=True)
        with OTEL_JSONL.open("a") as f:
            f.write(json.dumps(span.to_dict()) + "\n")
    except Exception as e:
        log.warning(f"OTel JSONL export failed: {e}")


def export_otlp(span: TokenUsage, endpoint: str):
    """Send span to OTLP HTTP endpoint (Grafana / Datadog / etc.)."""
    import urllib.request
    payload = {
        "resourceSpans": [{
            "scopeSpans": [{
                "spans": [{
                    "name": f"{'chat' if span.span_type == 'llm' else 'tool'} {span.model or span.tool_name}",
                    "attributes": {
                        "gen_ai.system": span.provider,
                        "gen_ai.request.model": span.model,
                        "gen_ai.usage.input_tokens": span.input_tokens,
                        "gen_ai.usage.output_tokens": span.output_tokens,
                        "clawos.workspace_id": span.workspace_id,
                        "clawos.task_id": span.task_id,
                        "clawos.tier": span.tier,
                        "clawos.tool.name": span.tool_name,
                        "clawos.tool.decision": span.tool_decision,
                        "duration_ms": span.latency_ms,
                    }
                }]
            }]
        }]
    }
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            endpoint + "/v1/traces",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception as e:
        log.debug(f"OTLP export failed: {e}")
