import json

# Each op -> (tool, list_of_valid_arg_dicts, malformed_arg)
# 5+ valid calls and 1 malformed call per op.

OPS = {
 # ---- abstract_algebra ----
 "abexact": ("abstract_algebra", [
   {"g1":"Z","g2":"Z/4","g3":"Z/2","f":"[[2]]","g":"[[1]]"},
   {"g1":"Z/2","g2":"Z/6","g3":"Z/3","f":"[[3]]","g":"[[2]]"},
   {"g1":"Z","g2":"Z","g3":"Z","f":"[[2]]","g":"[[3]]"},
   {"g1":"Z/4","g2":"Z/4","g3":"Z/2","f":"[[1]]","g":"[[1]]"},
   {"g1":"Z x Z","g2":"Z/2 + Z/2","g3":"Z/2","f":"[[1,0],[0,1]]","g":"[[1,1]]"},
 ], {"g1":"Z","g2":"Z/4","g3":"Z/2","f":123}),
 "absub": ("abstract_algebra", [
   {"group":"Z/4 + Z/6","generators":[[2,0],[0,3]]},
   {"group":"Z/12","generators":[[4]]},
   {"group":"Z/2 + Z/2","generators":[[1,0],[0,1]]},
   {"group":"Z","generators":[[2]]},
   {"group":"Z/6","generators":[[2],[3]]},
 ], {"group":"Z/12","generators":"bad"}),
 "pmsnf": ("abstract_algebra", [
   {"matrix":"[[x, 0], [0, x^2]]","modulus":7},
   {"matrix":"[[x-1, 0], [0, x-1]]","modulus":7},
   {"matrix":"[[1, 2], [3, 4]]","modulus":5},
   {"matrix":"[[x, 1], [0, x]]"},
   {"matrix":"[[x^2-1, 0], [0, x+1]]","modulus":7},
 ], {"matrix":123,"modulus":5}),

 # ---- homological ----
 "space": ("homological", [
   {"space":"S^2"},{"space":"T^2"},{"space":"RP^2"},{"space":"CP^2"},{"space":"K"},
 ], {"space":"sphere"}),
 "homology": ("homological", [
   {"space":"S^2"},{"space":"T^2","coefficients":"Z/2"},{"space":"RP^2","generators":True},
   {"space":"CP^2"},{"space":"K","coefficients":"Z/3"},
 ], {"space":"T^2","coefficients":123}),
 "cohomology": ("homological", [
   {"space":"S^2"},{"space":"T^2","coefficients":"Z/2"},{"space":"RP^2","generators":True},
   {"space":"CP^2"},{"space":"K"},
 ], {"space":"K","coefficients":False}),
 "les": ("homological", [
   {"space":"S^2","modulus":2},{"space":"T^2","modulus":3},{"space":"RP^2","modulus":2},
   {"space":"CP^2","modulus":5},{"space":"K","modulus":2},
 ], {"space":"S^2","modulus":"two"}),
 "bockstein": ("homological", [
   {"space":"RP^2","p":2,"pages":3},{"space":"S^2","p":2,"pages":2},{"space":"T^2","p":3,"pages":2},
   {"space":"CP^2","p":2,"pages":3},{"space":"L(3,1)","p":3,"pages":2},
 ], {"space":"RP^2","p":"two"}),
 "bockstein_trace": ("homological", [
   {"space":"RP^2","p":2,"degree":2,"element":"[1]"},
   {"space":"RP^2","p":2,"degree":1,"element":"[1]"},
   {"space":"T^2","p":2,"degree":1,"element":"[1,0]"},
   {"space":"CP^2","p":2,"degree":2,"element":"[1]"},
   {"space":"S^2","p":2,"degree":2,"element":"[1]"},
 ], {"space":"RP^2","p":2,"degree":2,"element":123}),
 "prop01": ("homological", [
   {"space":"RP^2","p":2,"pages":3},{"space":"T^2","p":2,"pages":2},{"space":"CP^2","p":2,"pages":3},
   {"space":"L(3,1)","p":3,"pages":2},{"space":"K","p":2,"pages":2},
 ], {"space":"RP^2","p":0}),

 # ---- elliptic_ff ----
 "ec_binary": ("elliptic_ff", [
   {"curve":"K-163"},{"curve":"B-163"},{"curve":"K-233"},
   {"curve":"[1, 1] over GF(2^4) poly 3 1"},{"curve":"[0, 1] over GF(2^8) poly 11 2"},
 ], {"curve":123}),
 "ec_cm": ("elliptic_ff", [
   {"D":"-3","bits":32},{"D":"-3","bits":64},{"D":"-3","bits":96},
   {"D":"-11","bits":64},{"D":"-19","bits":64},
 ], {"D":"abc"}),
 "ec_decompress": ("elliptic_ff", [
   {"curve":"secp256k1","hex":"0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"},
   {"curve":"secp256k1","hex":"0379be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"},
   {"curve":"P-256","hex":"036b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296"},
 ], {"curve":"secp256k1","hex":"zz"}),
 "ec_dlog": ("elliptic_ff", [
   {"curve":"y^2 = x^3 + 2x + 3 mod 97","P":"(73, 83)","Q":"(73, 83)"},
   {"curve":"y^2 = x^3 + 2x + 3 mod 97","P":"(73, 83)","Q":"(80, 10)"},
   {"curve":"y^2 = x^3 + 2x + 3 mod 97","P":"(73, 83)","Q":"(29, 54)"},
   {"curve":"y^2 = x^3 + 2x + 3 mod 97","P":"(73, 83)","Q":"(3, 91)"},
   {"curve":"y^2 = x^3 + 2x + 3 mod 97","P":"(73, 83)","Q":"(96, 0)"},
 ], {"curve":"secp256k1","P":123}),
 "ec_isogeny": ("elliptic_ff", [
   {"curve":"y^2 = x^3 + 2x + 3 mod 97","l":"2"},
   {"curve":"y^2 = x^3 + 2x + 3 mod 97","l":"3"},
   {"curve":"secp256k1","l":"2"},
   {"curve":"P-256","l":"2"},
 ], {"curve":"secp256k1","l":123}),
 "ec_pairing": ("elliptic_ff", [
   {"curve":"bn254"},{"curve":"BLS12-381"},{"curve":"bn254","kind":"weil"},
   {"curve":"bn254","kind":"tate"},{"curve":"BLS12-381","kind":"tate"},
 ], {"curve":"P-256"}),
 "ec_volcano": ("elliptic_ff", [
   {"curve":"y^2 = x^3 + 2x + 3 mod 97","l":2},
   {"curve":"y^2 = x^3 + 2x + 3 mod 97","l":3},
   {"curve":"secp256k1","l":2},
   {"curve":"P-256","l":2},
 ], {"curve":"secp256k1","l":"two"}),
 "ec_weak": ("elliptic_ff", [
   {"kind":"anomalous","bits":64},{"kind":"supersingular","bits":80},{"kind":"anomalous","bits":32},
   {"kind":"supersingular","bits":64},{"kind":"anomalous","bits":128},
 ], {"kind":"bogus","bits":64}),
 "ecdh": ("elliptic_ff", [
   {"curve":"secp256k1","a":"3","b":"5"},
   {"curve":"P-256","a":"7","b":"11"},
   {"curve":"secp256k1","a":"1","b":"2"},
   {"curve":"P-256","a":"4","b":"9"},
 ], {"curve":"secp256k1","a":123}),
 "ecdsa_sign": ("elliptic_ff", [
   {"curve":"secp256k1","key":"1","msg":"hello"},
   {"curve":"P-256","key":"42","msg":"test"},
   {"curve":"secp256k1","key":"2","msg":"abcdef"},
   {"curve":"P-256","key":"12345","msg":"message"},
 ], {"curve":"secp256k1","key":123}),
 "ecdsa_verify": ("elliptic_ff", [
   {"curve":"secp256k1","pub":"G","r":"1","s":"1","msg":"hello"},
   {"curve":"P-256","pub":"G","r":"1","s":"1","msg":"test"},
   {"curve":"secp256k1","pub":"G","r":"1234567890","s":"9876543210","msg":"abcdef"},
 ], {"curve":"secp256k1","pub":123}),
 "ecm": ("elliptic_ff", [
   {"n":"8051"},{"n":"10403"},{"n":"999999937"},{"n":"1000000007"},{"n":"3215031751"},
 ], {"n":123}),
 "ecpp": ("elliptic_ff", [
   {"n":"104729"},{"n":"1000003"},{"n":"15485863"},{"n":"32452843"},{"n":"49979687"},
 ], {"n":"composite"}),
 "ed25519_sign": ("elliptic_ff", [
   {"secret":"9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60","msghex":"72"},
   {"secret":"4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb","msghex":"72"},
   {"secret":"9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60","msghex":"616263"},
   {"secret":"0000000000000000000000000000000000000000000000000000000000000001","msghex":"00"},
 ], {"secret":123}),
 "ed25519_verify": ("elliptic_ff", [
   {"pub":"d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
    "sig":"e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b","msghex":"72"},
   {"pub":"d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
    "sig":"00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000","msghex":"00"},
 ], {"pub":123}),
 "hilbert": ("elliptic_ff", [
   {"D":"-3"},{"D":"-4"},{"D":"-7"},{"D":"-15"},{"D":"-23"},
 ], {"D":123}),
 "modpoly": ("elliptic_ff", [
   {"l":2},{"l":3},{"l":2,"p":"97"},{"l":5},{"l":3,"p":"101"},
 ], {"l":"two"}),
 "x25519": ("elliptic_ff", [
   {"k":"00"*31+"01","u":"00"*31+"09"},
   {"k":"00"*31+"02","u":"00"*31+"09"},
   {"k":"00"*31+"03","u":"00"*31+"09"},
   {"k":"00"*31+"04","u":"00"*31+"09"},
   {"k":"00"*31+"05"},
 ], {"k":123}),
 "x448": ("elliptic_ff", [
   {"k":"00"*55+"01"},
   {"k":"00"*55+"02","u":"00"*55+"09"},
   {"k":"00"*55+"03","u":"00"*55+"09"},
   {"k":"00"*55+"04","u":"00"*55+"09"},
   {"k":"00"*55+"05"},
 ], {"k":123}),

 # ---- analyze ----
 "banks": ("analyze", [
   {"accesses":["0","1","2","3"]},
   {"accesses":["0","1","2","3"],"size":32},
   {"accesses":["0","1","2","3"],"elem":4},
   {"accesses":["5","5","5","5"]},
   {"accesses":["0","2","4","6"],"size":16},
 ], {"accesses":["i","i+1"]}),
 "dword": ("analyze", [
   {"f":"x: f32"},{"f":"x: f32","tol":1e-6},{"f":"x*x: f32"},{"f":"sin(x): f32"},{"f":"x+1: f32","ulp":1},
 ], {"f":123}),
 "foldproof": ("analyze", [
   {"f":"x: f32"},{"f":"x*x: f32"},{"f":"sin(x): f32"},{"f":"x+1: f32"},{"f":"1/x: f32"},
 ], {"f":123}),
 "intatomic": ("analyze", [
   {"f":"x: f32"},{"f":"x: f32","count":4},{"f":"x: f32","tol":1e-6},{"f":"x+1: f32"},{"f":"x*x: f32","global":True},
 ], {"f":123}),
 "mma": ("analyze", [
   {},{"shape":"m16n8k16"},{"shape":"m16n8k8"},{"accumulator":"f32"},{"validate":True},
 ], {"shape":"bogus"}),
 "adamfit": ("analyze", [
   {"f":"x^2+1","in":[0,1]},
   {"f":"x^3-3x","in":[-2,2]},
   {"f":"sin(x)","in":[-3,3]},
   {"f":"exp(x)","in":[0,1]},
   {"f":"x^4+x^2+1","in":[-1,1]},
 ], {"f":"x^2+1","in":"bad"}),
 "more": ("analyze", [
   {},{"n":1},{"n":5},{"n":10},{"n":2},
 ], {"n":"five"}),
 "rop": ("analyze", [
   {"f":"x: f32"},{"f":"x+1: f32"},{"f":"x*x: f32"},{"f":"max(x,y): f32"},{"f":"x: i32"},
 ], {"f":123}),

 # ---- session ----
 "help": ("session", [{},{},{},{},{}], "oops"),

 # ---- calculus ----
 "scheme": ("calculus", [
   {"f":"x^2"},{"f":"x^3 - 3x"},{"f":"exp(x)"},{"f":"sin(x)"},{"f":"1/(1+x)"},
 ], {"f":123}),
 "continuous": ("calculus", [
   {"f":"x^2"},{"f":"1/x"},{"f":"sin(x)"},{"f":"floor(x)"},{"f":"x^3 - 3x"},
 ], {"f":123}),

 # ---- complex ----
 "trig": ("complex", [
   {"f":"sin(x)+cos(x)"},{"f":"sin(x)^2+cos(x)^2"},{"f":"tan(x)"},{"f":"sin(2*x)","mode":"expand"},{"f":"cos(x)-cos(y)"},
 ], {"f":123}),

 # ---- properties ----
 "injective": ("properties", [
   {"f":"x^3"},{"f":"x^2"},{"f":"exp(x)"},{"f":"2*x+1"},{"f":"sin(x)"},
 ], {"f":123}),
 "surjective": ("properties", [
   {"f":"x^3"},{"f":"x^2"},{"f":"exp(x)"},{"f":"x^3","onto":"[0,1]"},{"f":"sin(x)"},
 ], {"f":123}),
 "bijective": ("properties", [
   {"f":"x^3"},{"f":"x^2"},{"f":"exp(x)"},{"f":"2*x+1"},{"f":"tan(x)"},
 ], {"f":123}),
 # ---- transforms ----
 "dtft": ("transforms", [
   {"values":[1,2,3,4]},{"values":[1,1,1,1]},{"values":[0,1,0,-1]},
   {"f":"(1/2)^n","values":[1,0.5,0.25]},{"values":[1,-1,1,-1]},
 ], {"values":"bad"}),
}

if __name__ == "__main__":
    print("ops:", len(OPS))
    for op,(tool,valids,mal) in OPS.items():
        print(f"  {op:<18} {tool:<17} valid={len(valids)} malformed={type(mal).__name__}")
