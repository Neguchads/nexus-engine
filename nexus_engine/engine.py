"""Adaptive fixture execution; real hosts use the manual handoff interface."""
from .contracts import Rejected, digest, route, validate, validate_response


def run(plan, *, db=None, run_id=None, force_durable=False):
    plan,order = validate(plan)
    if plan["host"] != "fixture":
        raise Rejected("external providers require approved manual handoff")
    from .fixture import execute
    if route(plan) == "lite" and not force_durable:
        n=order[0]
        request={"host":"fixture","request_id":digest(plan),"input":n["input"],
                 "dependencies":{},"max_tokens":n["max_tokens"]}
        answer=validate_response(request,execute(request))
        return {"mode":"lite","outputs":{n["id"]:answer["output"]},"reserved_or_reported":answer["usage"]}
    if db is None or run_id is None:
        raise Rejected("durable mode requires db and run ID")
    from .store import Store
    store=Store(db)
    store.start(run_id,plan)
    while (request:=store.next(run_id)) is not None:
        store.submit(run_id,execute(request))
    return {"mode":"durable",**store.status(run_id)}
