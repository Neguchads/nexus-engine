"""Strict object merge; conflicts are not silently overwritten."""
from .contracts import Rejected, encode


def merge_objects(inputs):
    merged={}
    for node in sorted(inputs):
        value=inputs[node]
        if not isinstance(value,dict):
            raise Rejected("merge inputs must be JSON objects")
        for key,item in value.items():
            if key in merged and encode(merged[key])!=encode(item):
                raise Rejected("merge conflict at key "+key[:80])
            merged[key]=item
    encode(merged)
    return merged
