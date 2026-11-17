#!/usr/bin/env python3
"""Write the curated deterministic golden .ucas files (CLI + MCP + JSON)."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))

G = {
"01_add_bench_b0": "c optimize nofile bench budget 0\n```c\nint add(int a,int b){return a+b;}\n```\n",
"02_add_bench_b1": "c optimize nofile bench budget 1\n```c\nint add(int a,int b){return a+b;}\n```\n",
"03_add_bench_b3": "c optimize nofile bench budget 3\n```c\nint add(int a,int b){return a+b;}\n```\n",
"04_add_bench_b100": "c optimize nofile bench budget 100\n```c\nint add(int a,int b){return a+b;}\n```\n",
"05_div7_check_bench": "c optimize nofile check bench budget 0\n```c\nunsigned div7(unsigned x){return x/7;}\n```\n",
"06_div7_bench_check": "c optimize nofile bench check budget 0\n```c\nunsigned div7(unsigned x){return x/7;}\n```\n",
"07_add_zen4_bench": "c optimize nofile target zen4 bench budget 0\n```c\nint add(int a,int b){return a+b;}\n```\n",
"08_add_skylake_bench": "c optimize nofile target skylake bench budget 0\n```c\nint add(int a,int b){return a+b;}\n```\n",
"09_add_skl_bench": "c optimize nofile target skl bench budget 0\n```c\nint add(int a,int b){return a+b;}\n```\n",
"10_add_gt1030_bench": "c optimize nofile target gt1030 bench budget 0\n```c\nint add(int a,int b){return a+b;}\n```\n",
"11_add_bogus_bench": "c optimize nofile target bogus bench budget 0\n```c\nint add(int a,int b){return a+b;}\n```\n",
"12_floats_bench": ("c optimize nofile bench budget 0\n```c\n"
    "float fadd(float a,float b){return a+b;}\n"
    "float ffma(float a,float b,float c){return a*b+c;}\n"
    "double fdiv(double a,double b){return a/b;}\n"
    "float fscale(float x){return x*3.14159265f;}\n```\n"),
"13_sum_bench": "c optimize nofile bench budget 0\n```c\nint sum(int n){int s=0;for(int i=0;i<n;i++)s+=i;return s;}\n```\n",
"14_strlen_bench": "c optimize nofile bench budget 0\n```c\nint mylen(const char*s){int n=0;while(s[n])n++;return n;}\n```\n",
"15_empty_bench": "c optimize nofile bench budget 0\n```c\n```\n",
"16_badc_bench": "c optimize nofile bench budget 0\n```c\nint broken(int x){ return x @ 3; }\n```\n",
"17_bright_bench": "c optimize nofile bench budget 1\n```c\nvoid bright(unsigned char*d,const unsigned char*s,int n){for(int i=0;i<n;i++)d[i]=s[i]+1;}\n```\n",
"18_bench_twice": "c optimize nofile bench bench check check budget 0\n```c\nint add(int a,int b){return a+b;}\n```\n",
"19_nowrap_plain": "c optimize nofile budget 0\n```c\nint add(int a,int b){return a+b;}\n```\n",
"20_ctargets": "c targets\n",
}
for n, t in G.items():
    with open(os.path.join(HERE, n + ".ucas"), "w") as f:
        f.write(t)

# MCP JSONL golden (default env => gcc harness failure => deterministic)
mcp = [
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}',
 '{"jsonrpc":"2.0","method":"notifications/initialized"}',
 '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"c","arguments":{"op":"c_optimize","args":{"code":"int add(int a,int b){return a+b;}","nofile":true,"bench":true,"budget":0}}}}',
 '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"c","arguments":{"op":"c_optimize","args":{"code":"unsigned div7(unsigned x){return x/7;}","nofile":true,"check":true,"bench":true,"target":"zen4","budget":1}}}}',
 '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"c","arguments":{"op":"c_optimize","args":{"code":"int add(int a,int b){return a+b;}","nofile":true,"bench":true,"target":"gt1030","budget":0}}}}',
 '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"c","arguments":{"op":"c_optimize","args":{"code":"float fadd(float a,float b){return a+b;}","nofile":true,"bench":true,"budget":0}}}}',
]
with open(os.path.join(HERE, "mcp_bench.jsonl"), "w") as f:
    f.write("\n".join(mcp) + "\n")

# --json mode golden (default env)
js = [
 '{"id":1,"cmd":"c_optimize","args":{"code":"int add(int a,int b){return a+b;}","nofile":true,"bench":true,"budget":0}}',
 '{"id":2,"cmd":"c_optimize","args":{"code":"unsigned div7(unsigned x){return x/7;}","nofile":true,"check":true,"bench":true,"budget":1}}',
 '{"id":3,"cmd":"c_optimize","args":{"code":"int add(int a,int b){return a+b;}","nofile":true,"bench":true,"target":"bogus","budget":0}}',
]
with open(os.path.join(HERE, "json_bench.jsonl"), "w") as f:
    f.write("\n".join(js) + "\n")

print("wrote", len(G), "cli + 2 protocol goldens")
