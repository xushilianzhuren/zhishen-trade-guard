#!/usr/bin/env python3
import json,time,urllib.request,urllib.error,hmac,hashlib,base64,datetime,subprocess
R=[]
def mark(m): R.append(f"{time.strftime('%H:%M:%S')} {m}")
KEY="d406e4f4-9918-46d5-a7de-6d660a7449cf"
SEC="567DD9C4EF2C5D7CA35CFA2060C513E6"
PAS="Aaa798718!"
def ts_iso():
    t=time.time()
    r=json.loads(urllib.request.urlopen(urllib.request.Request("https://www.okx.com/api/v5/public/time",headers={"User-Agent":"Mozilla/5.0"}),timeout=10).read())
    ms=r["data"][0]["ts"]
    mark(f"ts_iso {time.time()-t:.1f}s")
    return datetime.datetime.fromtimestamp(int(ms)/1000,datetime.UTC).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]+'Z'
def okx(method,path,body=""):
    ts=ts_iso()
    sig=base64.b64encode(hmac.new(SEC.encode(),f"{ts}{method}{path}{body}".encode(),hashlib.sha256).digest()).decode()
    h={"User-Agent":"Mozilla/5.0","OK-ACCESS-KEY":KEY,"OK-ACCESS-SIGN":sig,"OK-ACCESS-TIMESTAMP":ts,"OK-ACCESS-PASSPHRASE":PAS}
    t=time.time()
    try:
        out=json.loads(urllib.request.urlopen(urllib.request.Request("https://www.okx.com"+path,data=body.encode() if body else None,headers=h,method=method),timeout=15).read())
        mark(f"{method} {path} {time.time()-t:.1f}s -> {json.dumps(out)[:120]}")
        return out
    except Exception as e:
        mark(f"{method} {path} FAILED {type(e).__name__} {time.time()-t:.1f}s {str(e)[:120]}")
        return None
mark("probe2 start")
okx("GET","/api/v5/account/balance")
mark("probe2 end")
open("debug.log","w").write("\n".join(R))
subprocess.run(["git","config","user.name","probe"])
subprocess.run(["git","config","user.email","p@p"])
subprocess.run(["git","add","debug.log"])
subprocess.run(["git","commit","-m","probe2 debug"])
p=subprocess.run(["git","push"],capture_output=True,text=True,timeout=60)
R.append("push rc="+str(p.returncode)+" "+p.stderr[-200:])
open("debug.log","w").write("\n".join(R))
subprocess.run(["git","add","debug.log"]); subprocess.run(["git","commit","-m","probe2 debug2"]); subprocess.run(["git","push"])
print("\n".join(R))
