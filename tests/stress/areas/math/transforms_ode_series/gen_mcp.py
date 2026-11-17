import json, sys

def emit(path, server, calls, flat=False):
    lines = []
    lines.append({"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}})
    lines.append({"jsonrpc":"2.0","method":"notifications/initialized"})
    for i,(tool,op,args) in enumerate(calls, 1):
        params = {"name":tool,"arguments":{"op":op,"args":args}}
        lines.append({"jsonrpc":"2.0","id":i,"method":"tools/call","params":params})
    with open(path,"w") as f:
        for ln in lines:
            f.write(json.dumps(ln, separators=(",",":"))+"\n")

# Each tuple is (MCP tool name, op, args)
TRANSFORMS = [
 ("transforms","laplace",{"f":"x^3 - 3x"}),
 ("transforms","laplace",{"f":"sin(2x)"}),
 ("transforms","laplace",{"f":"exp(-2x)*cos(3x)"}),
 ("transforms","laplace",{"f":"1", "period":2}),
 ("transforms","ilaplace",{"f":"1/(s^2+9)"}),
 ("transforms","ilaplace",{"f":"1/(s-1)^3"}),
 ("transforms","ilaplace",{"f":"e^(-3s)/(s^2+1)"}),
 ("transforms","ztrans",{"f":"2^n"}),
 ("transforms","ztrans",{"f":"n^2"}),
 ("transforms","iztrans",{"f":"z/(z-2)"}),
 ("transforms","iztrans",{"f":"1/(1-z^-1)^2"}),
 ("transforms","fourier",{"f":"exp(-x^2)"}),
 ("transforms","fourier",{"f":"1/(x^2+4)"}),
 ("transforms","ifourier",{"f":"exp(-abs(w))"}),
 ("transforms","genfunc",{"a":"n+1"}),
 ("transforms","egf",{"a":"2^n"}),
 ("transforms","tf",{"f":"1/(s^2+3s+2)"}),
 ("transforms","tf",{"f":"s/(s^2+1)"}),
 ("transforms","dft",{"values":[1,2,3,4]}),
 ("transforms","idft",{"values":[4,-2,0,-2]}),
 ("transforms","infinite_sum",{"index":"n","from":1,"f":"1/n^2"}),
 ("transforms","infinite_sum",{"index":"n","from":1,"f":"(-1)^n/n"}),
 ("transforms","infinite_product",{"index":"n","from":1,"f":"1+1/n^2"}),
 ("transforms","converge",{"a":"1/n"}),
 ("transforms","converge",{"a":"n!/n^n"}),
 ("transforms","radius",{"a":"x^n/n"}),
 ("transforms","radius",{"a":"x^n/n!"}),
 ("transforms","powerseries",{"f":"exp(x)"}),
 ("transforms","asymptotic",{"sum":"sum(k,1,n,1/k)"}),
]

CALCULUS = [
 ("calculus","diff",{"f":"x^3 - 3x"}),
 ("calculus","diff",{"f":"x^4 + x^2*y + y^3","vars":["x","y"]}),
 ("calculus","grad",{"f":"x^2*y*z","at":[1,2,3]}),
 ("calculus","laplacian",{"f":"x^2 + y^2 + z^2"}),
 ("calculus","hessian",{"f":"x^2*y + y^2","at":[1,2]}),
 ("calculus","jacobian",{"fs":["x^2+y","x*y"],"wrt":["x","y"]}),
 ("calculus","wronskian",{"fs":["exp(x)","exp(2x)"]}),
 ("calculus","limit",{"f":"sin(x)/x","var":"x","to":0}),
 ("calculus","limit",{"f":"1/x","var":"x","to":0,"side":"+"}),
 ("calculus","limit",{"f":"1/x","var":"x","to":0,"side":"-"}),
 ("calculus","limit",{"f":"sin(1/x)","var":"x","to":0}),
 ("calculus","taylor",{"f":"sin(x)","var":"x","at":0,"order":7}),
 ("calculus","taylor",{"f":"log(x)","var":"x","at":1,"order":4}),
 ("calculus","implicit",{"equation":"x^2+y^2=1","for":"y","wrt":"x"}),
 ("calculus","integrate",{"f":"x^2","var":"x","from":0,"to":1}),
 ("calculus","integrate",{"f":"1/x^2","var":"x","from":-1,"to":1}),
 ("calculus","integrate",{"f":"1/z","around":"|z|=1","assume":{"z":"complex"}}),
 ("calculus","antiderivative",{"f":"sin(x)","var":"x"}),
 ("calculus","closed",{"f":"sum(i,1,n,i)"}),
 ("calculus","closed",{"f":"sum(i,0,n,2^i)"}),
]

ODE = [
 ("transforms","laplace_solve",{"equations":"y'=y, y(0)=1"}),
 ("transforms","laplace_solve",{"equations":"y'' + y = 0, y(0)=1, y'(0)=0"}),
 ("transforms","laplace_solve",{"equations":"y'' - 3y' + 2y = 0, y(0)=1, y'(0)=0"}),
 ("transforms","laplace_solve",{"equations":"y' + 2y = exp(-t), y(0)=0"}),
 ("transforms","zsolve",{"equations":"x[n+1] = 2x[n], x[0]=1"}),
 ("transforms","zsolve",{"equations":"x[k+2] = x[k+1] + x[k], x[0]=0, x[1]=1"}),
 ("transforms","fourier_series",{"f":"x","var":"x","on":[-1,1],"period":2}),
 ("transforms","genfunc",{"a":"Fibonacci"}),
 ("transforms","infinite_sum",{"index":"n","from":1,"f":"1/(n*(n+1))"}),
 ("transforms","radius",{"a":"x^n/n^2"}),
]

emit(sys.argv[1]+"mcp_transforms.jsonl", "transforms", TRANSFORMS)
emit(sys.argv[1]+"mcp_calculus.jsonl", "calculus", CALCULUS)
emit(sys.argv[1]+"mcp_ode_series.jsonl", "transforms", ODE)
