#!/usr/bin/env python3
"""Fake MCP stdio server used to probe tools/mcp_client.py's error handling.

mcp_client.py spawns: Popen([<this script>, '--mcp', ...]).
The scenario is selected by the FAKE_SCENARIO environment variable, which the
client inherits.  Each scenario emits canned JSON-RPC lines (or misbehaves).
"""
import base64
import json
import os
import sys

SCEN = os.environ.get("FAKE_SCENARIO", "exit0")


def emit(obj):
    if isinstance(obj, str):
        sys.stdout.write(obj + "\n")
    else:
        sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def resp(i, result=None, error=None):
    d = {"jsonrpc": "2.0", "id": i}
    if error is not None:
        d["error"] = error
    else:
        d["result"] = result
    emit(d)


def init(i, ok=True):
    if ok:
        resp(i, {"serverInfo": {"name": "fake", "version": "0"},
                 "protocolVersion": "2025-06-18"})
    else:
        resp(i, error={"code": -32000, "message": "init refused"})


def tools(i, ok=True):
    if ok:
        resp(i, {"tools": [{"name": "analyze"}, {"name": "algebra"},
                           {"name": "properties"}, {"name": "plot"}]})
    else:
        resp(i, {})


def call(i, text="ok\n", image=None, is_error=False, structured=None):
    content = [{"type": "text", "text": text}]
    if image is not None:
        content.append({"type": "image", "data": image, "mimeType": "image/gif"})
    r = {"content": content, "isError": is_error,
         "structuredContent": structured or {}}
    resp(i, r)


def normal_tail(start, ambiguous=False):
    """Emit plausible replies for the calls mcp_client makes.

    ids: initialize=1, tools/list=2, factor=3, range=4, zeros=5, plot=6.
    An answered ambiguity repeats the zeros call, shifting plot to 7.
    """
    call(start, "factor x^6 - 1")
    call(start + 1, "range stuff")
    if ambiguous:
        resp(start + 2, {"content": [{"type": "text", "text": "?"}],
                         "isError": True,
                         "structuredContent": {"error": {
                             "code": "ambiguous", "key": "z",
                             "readings": [{"index": 0, "reading": "complex",
                                           "default": True}]}}})
        call(start + 3, "zeros answered")
        plot_id = start + 4
    else:
        call(start + 2, "zeros stuff")
        plot_id = start + 3
    call(plot_id, "plot stuff", image=base64.b64encode(b"GIF89a").decode())


def block_on_stdin():
    try:
        sys.stdin.read()
    except Exception:
        pass


def main():
    s = SCEN
    if s == "exit0":
        return 0
    if s == "exit1":
        return 1
    if s == "badjson":
        emit("this is not json")
        return 0
    if s == "blankline":
        emit("")
        return 0
    if s == "no_id":
        for _ in range(3):
            emit({"jsonrpc": "2.0"})
        return 0
    if s == "id_noresult":
        resp(1)
        return 0
    if s == "init_error":
        init(1, ok=False)
        return 0
    if s == "init_noserverinfo":
        resp(1, {"protocolVersion": "2025-06-18"})
        return 0
    if s == "init_noprotoversion":
        resp(1, {"serverInfo": {"name": "fake", "version": "0"}})
        return 0
    if s == "tools_no_tools":
        init(1)
        tools(2, ok=False)
        return 0
    if s == "tools_bad_entry":
        init(1)
        resp(2, {"tools": [{"nosuch": "x"}]})
        return 0
    if s == "call_no_content":
        init(1)
        tools(2)
        resp(3, {"isError": False})
        return 0
    if s == "call_content_empty":
        init(1)
        tools(2)
        resp(3, {"content": []})
        return 0
    if s == "call_text_missing":
        init(1)
        tools(2)
        resp(3, {"content": [{"type": "text"}]})
        return 0
    if s == "ambig_no_readings":
        init(1)
        tools(2)
        call(3, "factor")
        call(4, "range")
        resp(5, {"content": [{"type": "text", "text": "?"}],
                 "isError": True,
                 "structuredContent": {"error": {
                     "code": "ambiguous", "key": "z"}}})
        return 0
    if s == "ambig_nodefault":
        init(1)
        tools(2)
        call(3, "factor")
        call(4, "range")
        resp(5, {"content": [{"type": "text", "text": "?"}],
                 "isError": True,
                 "structuredContent": {"error": {
                     "code": "ambiguous", "key": "z",
                     "readings": [{"index": 0, "reading": "complex",
                                   "default": False}]}}})
        call(6, "zeros")
        call(7, "plot", image=base64.b64encode(b"GIF89a").decode())
        return 0
    if s == "plot_badb64":
        init(1)
        tools(2)
        call(3, "factor")
        call(4, "range")
        call(5, "zeros")
        call(6, "plot", image="a")  # invalid base64 length
        return 0
    if s == "plot_no_image":
        init(1)
        tools(2)
        call(3, "factor")
        call(4, "range")
        call(5, "zeros")
        call(6, "plot")
        return 0
    if s == "plot_image_nodata":
        init(1)
        tools(2)
        call(3, "factor")
        call(4, "range")
        call(5, "zeros")
        resp(6, {"content": [{"type": "image", "mimeType": "image/gif"}]})
        return 0
    if s == "plot_image_nomime":
        init(1)
        tools(2)
        call(3, "factor")
        call(4, "range")
        call(5, "zeros")
        resp(6, {"content": [{"type": "image",
                              "data": base64.b64encode(b"GIF89a").decode()}]})
        return 0
    if s == "hang_wrongid":
        emit({"jsonrpc": "2.0", "id": 999, "result": {}})
        block_on_stdin()
        return 0
    if s == "hang_after_init":
        init(1)
        block_on_stdin()
        return 0
    if s == "normal":
        init(1)
        tools(2)
        normal_tail(3)
        return 0
    if s == "dup_id":
        init(1)
        resp(1, {"duplicate": True})   # a second, bogus reply with id 1
        tools(2)
        normal_tail(3)
        return 0
    if s == "string_id":
        emit({"jsonrpc": "2.0", "id": "1", "result": {
            "serverInfo": {"name": "fake", "version": "0"},
            "protocolVersion": "2025-06-18"}})
        return 0
    if s == "unicode":
        init(1)
        tools(2)
        call(3, "factor \u221ax6 \u2014 caf\u00e9")
        call(4, "range \u2192 0..3")
        call(5, "zeros \u00b1i")
        call(6, "plot", image=base64.b64encode(b"GIF89a").decode())
        return 0
    if s == "empty_tools":
        init(1)
        resp(2, {"tools": []})
        normal_tail(3)
        return 0
    if s == "iserror_with_error":
        init(1)
        tools(2)
        resp(3, {"content": [{"type": "text", "text": "failed text"}],
                 "isError": True,
                 "structuredContent": {"error": {"code": "failed",
                                                 "message": "oops"}}})
        call(4, "range")
        call(5, "zeros")
        call(6, "plot", image=base64.b64encode(b"GIF89a").decode())
        return 0
    if s == "huge_line":
        init(1)
        tools(2)
        call(3, "X" * 10000)
        call(4, "range")
        call(5, "zeros")
        call(6, "plot", image=base64.b64encode(b"GIF89a").decode())
        return 0
    if s == "crlf":
        # Same as normal but with CRLF line endings.
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": 1, "result": {
            "serverInfo": {"name": "fake", "version": "0"},
            "protocolVersion": "2025-06-18"}}) + "\r\n")
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": 2, "result": {
            "tools": [{"name": "analyze"}]}}) + "\r\n")
        for i, t in [(3, "factor"), (4, "range"), (5, "zeros")]:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": i, "result": {
                "content": [{"type": "text", "text": t}], "isError": False,
                "structuredContent": {}}}) + "\r\n")
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": 6, "result": {
            "content": [{"type": "text", "text": "plot"},
                        {"type": "image", "mimeType": "image/gif",
                         "data": base64.b64encode(b"GIF89a").decode()}],
            "isError": False, "structuredContent": {}}}) + "\r\n")
        sys.stdout.flush()
        return 0
    if s == "normal_ambig":
        init(1)
        tools(2)
        normal_tail(3, ambiguous=True)
        return 0
    if s == "init_null":
        resp(1, None)
        return 0
    if s == "tools_null":
        init(1)
        resp(2, None)
        return 0
    if s == "call_null":
        init(1)
        tools(2)
        resp(3, None)
        return 0
    # unknown scenario
    emit({"unknown_scenario": s})
    return 0


if __name__ == "__main__":
    sys.exit(main())
