import json
import tempfile
import unittest
from pathlib import Path
from nexus_engine.codex_trace import parse_trace
from nexus_engine.contracts import Rejected
from nexus_engine.store import Store


def events(request_id="a"*48):
    return [
        {"type":"thread.started","thread_id":"thread-fixture"},
        {"type":"turn.started"},
        {"type":"item.completed","item":{"type":"agent_message","id":"item-1",
          "text":json.dumps({"request_id":request_id,"output":{"value":5}})}},
        {"type":"turn.completed","usage":{"input_tokens":20,"cached_input_tokens":5,
          "output_tokens":10,"reasoning_output_tokens":2,"cache_write_input_tokens":0}}]


def raw(es):
    return ("\n".join(json.dumps(e) for e in es)+"\n").encode()


class CodexTraceTests(unittest.TestCase):
    def test_count_subsets_not_twice(self):
        answer,evidence=parse_trace(raw(events()))
        self.assertEqual(answer["usage"],30)
        self.assertEqual(evidence["total_tokens"],30)
        self.assertEqual(answer["output"],{"value":5})

    def test_fail_closed(self):
        for es in (events()[:-1],events()+events(),events()[:2]+[{"type":"turn.failed"}],
                   events()[:2]+[{"type":"item.completed","item":{"type":"error"}}]+events()[2:]):
            with self.assertRaises(Rejected):parse_trace(raw(es))
        es=events();es[-1]["usage"]["input_tokens"]=True
        with self.assertRaises(Rejected):parse_trace(raw(es))
        es=events();es[2]["item"]["text"]='{"request_id":"'+("a"*48)+'","output":1,"output":2}'
        with self.assertRaises(Rejected):parse_trace(raw(es))

    def test_store_binding_and_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(Path(tmp)/"state.db")
            plan={"host":"codex","budget":40,"resume":True,
                  "nodes":[{"id":"review","depends_on":[],"input":{"task":"test"},"max_tokens":40}]}
            s.start("r",plan);r=s.preview("r");req=s.next("r",approved=True,approval_sha256=r["approval_sha256"])
            wrong,_=parse_trace(raw(events()))
            with self.assertRaises(Rejected):s.submit("r",wrong)
            answer,_=parse_trace(raw(events(req["request_id"])))
            s.submit("r",answer)
            self.assertEqual(s.status("r")["reserved_or_reported"],30)
            self.assertEqual(s.status("r")["outputs"],{"review":{"value":5}})
