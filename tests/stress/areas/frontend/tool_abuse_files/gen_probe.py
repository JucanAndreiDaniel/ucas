import json

def req(i, method, params=None):
    d = {"jsonrpc":"2.0","id":i,"method":method}
    if params is not None:
        d["params"] = params
    return json.dumps(d)

def call(i, name, args=None):
    return req(i,"tools/call", {"name":name, "arguments": args if args is not None else {}})

lines = [
    req(0,"initialize",{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}),
    req(1,"notifications/initialized"),
    # tool-name abuse
    call(2,"tools/list",{}),
    call(3,"initialize",{}),
    call(4,"tools/call",{"name":"tools/list","arguments":{}}),
    call(5,"session",{"op":"schema"}),
    call(6,"session",{"op":"schema"}),
    call(7,"analyze",{"op":"tools/list"}),
    call(8,"c",{"op":"tools/list"}),
    call(9,"plot",{"op":"tools/list"}),
    call(10,"",{}),
    call(11,"   ",{}),
    # file paths via c
    call(12,"c",{"op":"c_optimize","args":{"file":"/etc/hostname","nofile":True}}),
    # file paths via animate
    call(13,"plot",{"op":"animate","args":{"code":"%x = 1\n","inputs":[{"file":"/etc/hostname"}],"nofile":True}}),
]
open("probe1.jsonl","w").write("\n".join(lines)+"\n")
print("wrote", len(lines), "lines")
