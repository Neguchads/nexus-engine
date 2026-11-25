"""Deterministic arithmetic fixture, not an AI adapter."""
from .contracts import Rejected, response


def execute(request):
    if request["host"] != "fixture":
        raise Rejected("fixture cannot act as another provider")
    data = request["input"]
    values = data.get("values")
    if (set(data) != {"values"} or not isinstance(values, list) or len(values) > 1000
            or any(type(x) is not int or abs(x) > 1_000_000 for x in values)):
        raise Rejected("fixture requires bounded integer values")
    deps = list(request["dependencies"].values())
    if any(type(x) is not int for x in deps):
        raise Rejected("fixture dependencies must be integers")
    return response(request, sum(values) + sum(deps), 1)
