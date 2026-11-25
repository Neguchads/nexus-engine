"""Bounded data contracts; no executable configuration."""
import hashlib
import json
import re

HOSTS = frozenset(("fixture", "codex", "claude", "gemini", "copilot", "ollama"))
ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
LIMIT = 128 * 1024


class Rejected(ValueError):
    pass


def encode(value):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError, RecursionError) as exc:
        raise Rejected("invalid JSON") from exc
    if len(raw.encode()) > LIMIT:
        raise Rejected("JSON limit exceeded")
    return raw


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def identifier(value):
    return isinstance(value, str) and ID.fullmatch(value) is not None


def positive(value):
    return type(value) is int and 0 < value <= 1_000_000


def validate(plan):
    plan = json.loads(encode(plan))
    if not isinstance(plan, dict) or set(plan) != {"host", "budget", "resume", "nodes"}:
        raise Rejected("invalid plan fields")
    if not isinstance(plan["host"], str) or plan["host"] not in HOSTS:
        raise Rejected("unknown host")
    if not positive(plan["budget"]) or type(plan["resume"]) is not bool:
        raise Rejected("invalid budget or resume")
    nodes = plan["nodes"]
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 64:
        raise Rejected("invalid node count")
    known = set()
    for n in nodes:
        if not isinstance(n, dict) or set(n) != {"id", "depends_on", "input", "max_tokens"}:
            raise Rejected("invalid node fields")
        key, deps = n["id"], n["depends_on"]
        if not identifier(key) or key in known:
            raise Rejected("invalid or duplicate node")
        known.add(key)
        if (not isinstance(deps, list) or any(not identifier(d) for d in deps)
                or len(set(deps)) != len(deps) or key in deps):
            raise Rejected("invalid dependencies")
        if not isinstance(n["input"], dict) or not positive(n["max_tokens"]):
            raise Rejected("invalid input or reservation")
    if any(d not in known for n in nodes for d in n["depends_on"]):
        raise Rejected("unknown dependency")
    if sum(n["max_tokens"] for n in nodes) > plan["budget"]:
        raise Rejected("reservations exceed budget")
    order, done = [], set()
    while len(order) < len(nodes):
        ready = [n for n in nodes if n["id"] not in done and set(n["depends_on"]) <= done]
        if not ready:
            raise Rejected("dependency cycle")
        order.extend(ready)
        done.update(n["id"] for n in ready)
    return plan, order


def route(plan):
    plan, order = validate(plan)
    # External handoffs always require a durable reservation.
    return "lite" if plan["host"] == "fixture" and len(order) == 1 and not plan["resume"] else "durable"


def response(request, value, usage):
    return {"request_id": request["request_id"], "host": request["host"],
            "output": value, "usage": usage}


def validate_response(request, answer):
    answer = json.loads(encode(answer))
    if not isinstance(answer, dict) or set(answer) != {"request_id", "host", "output", "usage"}:
        raise Rejected("invalid response fields")
    if answer["request_id"] != request["request_id"] or answer["host"] != request["host"]:
        raise Rejected("response binding mismatch")
    usage = answer["usage"]
    if type(usage) is not int or not 0 <= usage <= request["max_tokens"]:
        raise Rejected("reported usage exceeds reservation")
    return answer
