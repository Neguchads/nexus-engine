"""Explicit dependency projection; no speculative summarization."""
from .contracts import Rejected, encode


def project(node, outputs):
    policy=node.get("context")
    if policy is None:
        return outputs
    selected={}
    for dep,keys in policy["select"].items():
        value=outputs[dep]
        if not isinstance(value,dict) or any(k not in value for k in keys):
            raise Rejected("requested context fields missing")
        selected[dep]={k:value[k] for k in keys}
    if len(encode(selected).encode())>policy["max_bytes"]:
        raise Rejected("selected context exceeds byte budget")
    return selected


def report(node, outputs):
    selected=project(node,outputs)
    # Full context may exceed the request limit; measure without applying it.
    import json
    full=json.dumps(outputs,sort_keys=True,separators=(",",":"),allow_nan=False)
    small=json.dumps(selected,sort_keys=True,separators=(",",":"),allow_nan=False)
    return {"full_bytes":len(full.encode()),"selected_bytes":len(small.encode()),
            "selected_dependencies":sorted(selected)}
