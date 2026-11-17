#!/usr/bin/env python3
"""Schema conformance checker for ucas JSON / MCP envelopes.

Validates the reply envelope against the documented tool result shape and the
cross-layer invariants.  Feed it *.out files (one JSON value per line) on argv,
or run with --all to check the *.out files in this script's own folder.

Usage:
    python3 schema_check.py FILE.out [FILE.out ...]
    python3 schema_check.py --all        # checks ./*.out next to this script
"""
import json, os, sys, glob

# ---- documented vocabularies (from the MCP tool schema) ----
ERROR_CODES = {
    "bad_json", "bad_request", "unknown_command", "parse_error", "domain_error",
    "unsupported", "failed", "ambiguous", "needs_input", "not_understood",
    "timeout", "internal",
}
NOTE_KINDS = {"rule", "info", "assumed", "default"}
PROOF_KINDS = {"symbolic", "exhaustive", "sat", "numeric", "search"}

# documented envelope fields and their json type checkers
def _is_bool(x): return isinstance(x, bool)
def _is_str(x): return isinstance(x, str)
def _is_int(x): return isinstance(x, int) and not isinstance(x, bool)
def _is_num(x): return isinstance(x, (int, float)) and not isinstance(x, bool)
def _is_obj(x): return isinstance(x, dict)
def _is_arr(x): return isinstance(x, list)

ENVELOPE_FIELDS = {
    "id":         lambda x: True,          # any, echoed
    "ok":         _is_bool,
    "cmd":        lambda x: x is None or _is_str(x),
    "ucas":       _is_str,
    "structured": _is_bool,
    "result":     _is_obj,
    "results":    _is_arr,
    "notes":      _is_arr,
    "conditions": _is_arr,
    "checks":     _is_arr,
    "proof":      _is_obj,
    "files":      _is_arr,
    "text":       _is_str,
    "error":      _is_obj,
}
REQUIRED_ENVELOPE = {"ok", "cmd"}


class Report:
    def __init__(self):
        self.checked = 0
        self.issues = []

    def add(self, sev, where, msg):
        self.issues.append((sev, where, msg))

    def dump(self):
        for sev, where, msg in self.issues:
            print(f"[{sev}] {where}: {msg}")
        print(f"-- checked {self.checked} replies; {len(self.issues)} issues --")
        return len(self.issues)


def check_envelope(env, r, where):
    """Validate one ucas envelope (JSON reply or MCP structuredContent)."""
    r.checked += 1
    if not isinstance(env, dict):
        r.add("WRONG", where, f"envelope is {type(env).__name__}, expected object")
        return
    # required fields
    for k in REQUIRED_ENVELOPE:
        if k not in env:
            r.add("MISSING", where, f"required field '{k}' missing")
    # unknown fields
    for k in env:
        if k not in ENVELOPE_FIELDS:
            r.add("EXTRA", where, f"undocumented top-level field '{k}'")
    # field types
    for k, v in env.items():
        chk = ENVELOPE_FIELDS.get(k)
        if chk and not chk(v):
            r.add("WRONG", where, f"field '{k}' has wrong type {type(v).__name__}")
    # ok / error consistency
    ok = env.get("ok")
    has_err = "error" in env
    if ok is True and has_err:
        r.add("INVARIANT", where, "ok:true together with an error object")
    if ok is False and not has_err:
        r.add("INVARIANT", where, "ok:false but no error object")
    # structured / result consistency.  Per the schema doc, "unstructured
    # commands give {text}": structured:false may still carry a result that is
    # exactly {"text": <string>}.  structured:true must carry an object result.
    if env.get("structured") is True and "result" not in env:
        r.add("INVARIANT", where, "structured:true but no result")
    if "result" in env and env.get("structured") is False:
        res = env["result"]
        if not (isinstance(res, dict) and set(res.keys()) == {"text"} and _is_str(res["text"])):
            r.add("INVARIANT", where,
                  f"structured:false result is not just {{text}}: keys={list(res) if isinstance(res,dict) else type(res).__name__}")
    # conditions: array of strings
    for i, c in enumerate(env.get("conditions", []) or []):
        if not _is_str(c):
            r.add("WRONG", where, f"conditions[{i}] is {type(c).__name__}, expected string")
    # notes
    for i, n in enumerate(env.get("notes", []) or []):
        if not _is_obj(n):
            r.add("WRONG", where, f"notes[{i}] is {type(n).__name__}, expected object")
            continue
        for k in n:
            if k not in ("kind", "text"):
                r.add("EXTRA", where, f"notes[{i}] has undocumented field '{k}'")
        kd = n.get("kind")
        if kd is not None and kd not in NOTE_KINDS:
            r.add("VOCAB", where, f"notes[{i}].kind={kd!r} not in documented set {sorted(NOTE_KINDS)}")
        if "text" in n and not _is_str(n["text"]):
            r.add("WRONG", where, f"notes[{i}].text not a string")
    # checks
    for i, c in enumerate(env.get("checks", []) or []):
        if not _is_obj(c):
            r.add("WRONG", where, f"checks[{i}] not object"); continue
        for k in c:
            if k not in ("kind", "points", "max_diff", "passed", "text"):
                r.add("EXTRA", where, f"checks[{i}] has undocumented field '{k}'")
        if "kind" in c and not _is_str(c["kind"]):
            r.add("WRONG", where, f"checks[{i}].kind not a string")
        if "points" in c and not _is_int(c["points"]):
            r.add("WRONG", where, f"checks[{i}].points not an integer")
        if "max_diff" in c and not _is_num(c["max_diff"]):
            r.add("WRONG", where, f"checks[{i}].max_diff not a number")
        if "passed" in c and not _is_bool(c["passed"]):
            r.add("WRONG", where, f"checks[{i}].passed not a boolean")
        if "text" in c and not _is_str(c["text"]):
            r.add("WRONG", where, f"checks[{i}].text not a string")
    # proof
    if "proof" in env:
        p = env["proof"]
        for k in p:
            if k not in ("kind", "text"):
                r.add("EXTRA", where, f"proof has undocumented field '{k}'")
        kd = p.get("kind")
        if kd is not None and kd not in PROOF_KINDS:
            r.add("VOCAB", where, f"proof.kind={kd!r} not in documented set {sorted(PROOF_KINDS)}")
        if "text" in p and not _is_str(p["text"]):
            r.add("WRONG", where, "proof.text not a string")
    # files
    for i, fobj in enumerate(env.get("files", []) or []):
        if not _is_obj(fobj):
            r.add("WRONG", where, f"files[{i}] not object"); continue
        for k in fobj:
            if k not in ("name", "mime", "bytes", "path", "base64"):
                r.add("EXTRA", where, f"files[{i}] has undocumented field '{k}'")
        for k in ("name", "mime", "path", "base64"):
            if k in fobj and not _is_str(fobj[k]):
                r.add("WRONG", where, f"files[{i}].{k} not a string")
        if "bytes" in fobj and not _is_int(fobj["bytes"]):
            r.add("WRONG", where, f"files[{i}].bytes not an integer")
    # error
    if has_err:
        e = env["error"]
        for k in e:
            if k not in ("code", "message", "pos", "key", "readings", "how"):
                r.add("EXTRA", where, f"error has undocumented field '{k}'")
        if "code" not in e:
            r.add("MISSING", where, "error.code missing")
        elif e["code"] not in ERROR_CODES:
            r.add("VOCAB", where, f"error.code={e['code']!r} not in documented set {sorted(ERROR_CODES)}")
        if "message" not in e:
            r.add("MISSING", where, "error.message missing")
        elif not _is_str(e["message"]):
            r.add("WRONG", where, "error.message not a string")
        if "pos" in e:
            pos = e["pos"]
            if not _is_obj(pos):
                r.add("WRONG", where, "error.pos not an object")
            else:
                for k in pos:
                    if k not in ("line", "col"):
                        r.add("EXTRA", where, f"error.pos has undocumented field '{k}'")
                for k in ("line", "col"):
                    if k in pos and not _is_int(pos[k]):
                        r.add("WRONG", where, f"error.pos.{k} not an integer")
        if "key" in e and not _is_str(e["key"]):
            r.add("WRONG", where, "error.key not a string")
        if "how" in e and not _is_str(e["how"]):
            r.add("WRONG", where, "error.how not a string")
        for i, rd in enumerate(e.get("readings", []) or []):
            if not _is_obj(rd):
                r.add("WRONG", where, f"error.readings[{i}] not object"); continue
            for k in rd:
                if k not in ("index", "reading", "default", "how"):
                    r.add("EXTRA", where, f"error.readings[{i}] has undocumented field '{k}'")
            if "index" in rd and not _is_int(rd["index"]):
                r.add("WRONG", where, f"error.readings[{i}].index not an integer")
            if "reading" in rd and not _is_str(rd["reading"]):
                r.add("WRONG", where, f"error.readings[{i}].reading not a string")
            if "default" in rd and not _is_bool(rd["default"]):
                r.add("WRONG", where, f"error.readings[{i}].default not a boolean")
            if "how" in rd and not _is_str(rd["how"]):
                r.add("WRONG", where, f"error.readings[{i}].how not a string")


def check_json_file(path, r):
    """Plain --json lines: each line IS the envelope."""
    base = os.path.basename(path)
    for i, line in enumerate(open(path), 1):
        if not line.strip():
            continue
        try:
            env = json.loads(line)
        except Exception as e:
            r.add("CRASH", f"{base}:{i}", f"invalid JSON: {e}")
            continue
        check_envelope(env, r, f"{base}:{i}")


def check_mcp_file(path, r):
    """--mcp lines: JSON-RPC; tool results carry structuredContent + isError."""
    base = os.path.basename(path)
    for i, line in enumerate(open(path), 1):
        if not line.strip():
            continue
        try:
            rpc = json.loads(line)
        except Exception as e:
            r.add("CRASH", f"{base}:{i}", f"invalid JSON: {e}")
            continue
        rid = rpc.get("id")
        if "result" not in rpc:
            # JSON-RPC protocol-level error, not a tool envelope
            continue
        res = rpc["result"]
        if "structuredContent" not in res:
            continue  # initialize / ping / list, not a tool call
        sc = res["structuredContent"]
        where = f"{base}:{i} id={rid!r}"
        check_envelope(sc, r, where)
        # id echoed inside structuredContent
        if sc.get("id") != rid:
            r.add("ECHO", where, f"structuredContent.id={sc.get('id')!r} != rpc id={rid!r}")
        # isError exactly when error present
        ie = res.get("isError")
        if not _is_bool(ie):
            r.add("WRONG", where, f"isError={ie!r} not a boolean")
        else:
            if ie != ("error" in sc):
                r.add("INVARIANT", where,
                      f"isError={ie} but error present={'error' in sc}")
        if ie is True and ("error" not in sc):
            r.add("INVARIANT", where, "isError:true with no error in structuredContent")
        if ie is False and ("error" in sc):
            r.add("INVARIANT", where, "isError:false with an error in structuredContent")
        # content array shape (MCP allows text / image / resource / audio blocks)
        content = res.get("content")
        if not _is_arr(content):
            r.add("WRONG", where, "result.content is not an array")
        else:
            for j, c in enumerate(content):
                if not _is_obj(c) or "type" not in c:
                    r.add("WRONG", where, f"content[{j}] is not a content block")
                    continue
                ct = c["type"]
                if ct == "text" and not _is_str(c.get("text")):
                    r.add("WRONG", where, f"content[{j}] text block has no string text")
                elif ct == "image" and not (_is_str(c.get("data")) and _is_str(c.get("mimeType"))):
                    r.add("WRONG", where, f"content[{j}] image block missing data/mimeType")
                elif ct not in ("text", "image", "resource", "audio"):
                    r.add("WRONG", where, f"content[{j}] has unexpected type {ct!r}")


def main():
    argv = sys.argv[1:]
    if argv == ["--all"]:
        here = os.path.dirname(os.path.abspath(__file__))
        files = sorted(glob.glob(os.path.join(here, "*.out")))
    else:
        files = argv
    if not files:
        print(__doc__); return 2
    r = Report()
    for f in files:
        # Detect the frontend from the content, not the filename: --mcp lines
        # carry a "jsonrpc" key, --json lines are bare envelopes.
        mode = "json"
        with open(f) as fh:
            for line in fh:
                if line.strip():
                    try:
                        if "jsonrpc" in json.loads(line):
                            mode = "mcp"
                    except Exception:
                        pass
                    break
        if mode == "mcp":
            check_mcp_file(f, r)
        else:
            check_json_file(f, r)
    return 0 if r.dump() == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
