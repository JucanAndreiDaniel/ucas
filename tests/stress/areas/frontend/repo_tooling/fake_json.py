#!/usr/bin/env python3
import json, os, sys
s = os.environ.get("FAKE_JSON_SCENARIO", "exit0")
def emit(o): print(json.dumps(o)); sys.stdout.flush()
if s == "exit0":
    sys.exit(0)
if s == "badjson":
    print("not json"); sys.exit(0)
if s == "wrongid":
    emit({"id":99,"ok":True,"result":{},"error":{}}); sys.exit(0)
if s == "error":
    emit({"id":1,"ok":False,"error":{"code":"failed","message":"boom"}}); sys.exit(0)
if s == "ambig":
    emit({"id":1,"ok":False,"error":{"code":"ambiguous","key":"z","message":"pick",
          "readings":[{"index":0,"reading":"complex","default":True}]}}); sys.exit(0)
if s == "nook":
    emit({"id":1,"result":{}}); sys.exit(0)
