"""Opt-in local Ollama adapter; no credential access, redirects or remote URL."""
import http.client
import json
import re
from .contracts import LIMIT, Rejected, encode, response, validate_response

MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}:[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")


def payload(request):
    if request["host"] != "ollama":
        raise Rejected("Ollama host required")
    data=request["input"]
    if set(data)!={"model","task"} or not isinstance(data["model"],str) or not MODEL.fullmatch(data["model"]):
        raise Rejected("explicit local model tag and task required")
    if "cloud" in data["model"].lower():
        raise Rejected("cloud-named models are not supported")
    if not isinstance(data["task"],str) or not data["task"].strip():
        raise Rejected("text task required")
    if request["max_tokens"]>8192:
        raise Rejected("experimental local adapter reservation limit is 8192")
    prompt=encode({"task":data["task"],"dependencies":request["dependencies"]})
    if len(prompt.encode())>16384:
        raise Rejected("local prompt size limit exceeded")
    # num_predict is a requested output cap, not a guarantee of total token use.
    return {"model":data["model"],"prompt":prompt,"stream":False,"format":"json",
            "options":{"num_predict":min(1024,request["max_tokens"]),"temperature":0}}


def execute(request):
    body=encode(payload(request)).encode()
    conn=http.client.HTTPConnection("127.0.0.1",11434,timeout=60)
    try:
        conn.request("POST","/api/generate",body=body,headers={"Content-Type":"application/json"})
        res=conn.getresponse()
        if res.status!=200:
            raise Rejected("local endpoint returned non-success status")
        raw=res.read(LIMIT+1)
        if len(raw)>LIMIT:
            raise Rejected("local response exceeds limit")
        result=json.loads(raw)
        if not isinstance(result,dict) or result.get("done") is not True or result.get("done_reason")!="stop":
            raise Rejected("incomplete model response")
        if result.get("model")!=request["input"]["model"]:
            raise Rejected("model tag mismatch")
        counts=[result.get(k) for k in ("prompt_eval_count","eval_count")]
        if any(type(x) is not int or x<0 for x in counts):
            raise Rejected("missing valid reported usage")
        output=result.get("response")
        if not isinstance(output,str):
            raise Rejected("missing model output")
        return validate_response(request,response(request,json.loads(output),sum(counts)))
    finally:
        conn.close()


def step(store,run_id):
    # Reservation precedes HTTP. Any error leaves an unresolved request.
    request=store.next(run_id,approved=True,expected_host="ollama")
    if request is not None:
        store.submit(run_id,execute(request))
    return store.status(run_id)
