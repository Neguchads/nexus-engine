"""Read a reviewed Codex CLI JSONL result, never invoke the provider.

A trace is operator-supplied evidence, not authenticated billing or proof of isolation.
"""
import hashlib
import re
from pathlib import Path
from .contracts import LIMIT,Rejected,decode,encode

TRACE_LIMIT=4*1024*1024


def parse_trace(raw):
    if not isinstance(raw,bytes) or not raw or len(raw)>TRACE_LIMIT:
        raise Rejected("trace byte limit")
    lines=[line for line in raw.splitlines() if line.strip()]
    if len(lines)>4096 or any(len(line)>LIMIT for line in lines):
        raise Rejected("trace event limit")
    events=[decode(line) for line in lines]
    if not events or any(not isinstance(e,dict) or not isinstance(e.get("type"),str) for e in events):
        raise Rejected("invalid Codex event")
    kinds=[e["type"] for e in events]
    if (kinds[0]!="thread.started" or kinds[-1]!="turn.completed"
            or kinds.count("thread.started")!=1 or kinds.count("turn.started")!=1
            or kinds.count("turn.completed")!=1 or kinds[1]!="turn.started"
            or "turn.failed" in kinds or "error" in kinds):
        raise Rejected("one successful, complete Codex turn required")
    messages=[]
    for event in events[2:-1]:
        if event["type"] not in ("item.started","item.updated","item.completed"):
            raise Rejected("unknown Codex event in turn")
        item=event.get("item")
        if not isinstance(item,dict) or item.get("type")=="error":
            raise Rejected("invalid or failed Codex item")
        if event["type"]=="item.completed" and item.get("type")=="agent_message":
            messages.append(item.get("text"))
    if not messages or not isinstance(messages[-1],str):
        raise Rejected("missing final Codex agent message")
    result=decode(messages[-1])
    if (not isinstance(result,dict) or set(result)!={"request_id","output"}
            or not isinstance(result["request_id"],str)
            or not re.fullmatch("[0-9a-f]{48}",result["request_id"])):
        raise Rejected("final JSON must bind the Nexus request ID")
    usage=events[-1].get("usage")
    if not isinstance(usage,dict):
        raise Rejected("missing Codex usage")
    counts={}
    for key in ("input_tokens","output_tokens","cached_input_tokens","reasoning_output_tokens","cache_write_input_tokens"):
        value=usage.get(key,0) if key in ("cache_write_input_tokens",) else usage.get(key)
        if type(value) is not int or value<0:
            raise Rejected("invalid Codex usage counter")
        counts[key]=value
    if (counts["cached_input_tokens"]>counts["input_tokens"]
            or counts["reasoning_output_tokens"]>counts["output_tokens"]):
        raise Rejected("inconsistent Codex usage")
    total=counts["input_tokens"]+counts["output_tokens"]
    if total<=0:
        raise Rejected("no measured token usage")
    answer={"host":"codex","request_id":result["request_id"],"output":result["output"],"usage":total}
    encode(answer)
    return answer,{"sha256":hashlib.sha256(raw).hexdigest(),"events":len(events),
                   "reported_usage":counts,"total_tokens":total,
                   "scope":"operator-provided CLI trace; not provider attestation"}


def read_trace(path):
    with Path(path).open("rb") as f:
        return parse_trace(f.read(TRACE_LIMIT+1))
