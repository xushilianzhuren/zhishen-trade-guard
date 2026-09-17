#!/usr/bin/env python3
import json,urllib.request,base64,time,os
print("probe start",flush=True)
GT=os.environ.get("GITHUB_TOKEN","")
print("GT len",len(GT),flush=True)
def push(fn,txt):
    if not GT: print("no GT",flush=True); return
    hh={"Authorization":"token "+GT,"User-Agent":"g","Accept":"application/vnd.github+json"}
    sha=None
    try:
        r=urllib.request.urlopen(urllib.request.Request(f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/contents/{fn}",headers=hh),timeout=15); sha=json.loads(r.read())["sha"]
    except Exception as e: print("sha-err",type(e).__name__,flush=True)
    b={"message":"probe","content":base64.b64encode(txt.encode()).decode(),"branch":"main"}
    if sha: b["sha"]=sha
    try:
        urllib.request.urlopen(urllib.request.Request(f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/contents/{fn}",data=json.dumps(b).encode(),headers=hh,method="PUT"),timeout=20).read(); print("pushed",fn,flush=True)
    except Exception as e: print("put-err",type(e).__name__,flush=True)
push("probe.txt",f"alive {time.strftime('%F %T')}")
print("probe done",flush=True)
