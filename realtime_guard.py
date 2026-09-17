#!/usr/bin/env python3
"""实时现货守护v1.0（2026-09-17建·跑在GitHub Actions runner·10秒级轮询）
策略（主人钦定）:
  1. 移动止损: 任一现货持仓从本轮峰值回撤>=5% -> 市价全卖 + Server酱弹微信
  2. ZEC 60日线离场: 现价 < 60日均线 -> 市价全卖 + 弹微信
  3. 卖出后留USDT，不自动回买（买点仍走日线策略人工/后续自动化）
状态: state.json(峰值表)随交易变更，workflow收尾提交回仓库
"""
import json,time,urllib.request,urllib.error,hmac,hashlib,base64,datetime,os,sys

KEY="d406e4f4-9918-46d5-a7de-6d660a7449cf"
SEC="567DD9C4EF2C5D7CA35CFA2060C513E6"
PAS="Aaa798718!"
SCT=os.environ.get("SCTKEY","")
LOOP_SECONDS=20500          # ~5.7h，6h job上限内
POLL=10                     # 秒级轮询
DRAWDOWN=0.05               # 移动止损5%
MIN_USD=1.0                 # 忽略 dust

STATE_F="state.json"

def _req(url,data=None,headers=None,timeout=15):
    req=urllib.request.Request(url,data=data,headers=headers or {},method="POST" if data else "GET")
    return urllib.request.urlopen(req,timeout=timeout)

def ts_iso():
    r=_req("https://www.okx.com/api/v5/public/time",headers={"User-Agent":"Mozilla/5.0"})
    ms=json.loads(r.read())["data"][0]["ts"]
    return datetime.datetime.fromtimestamp(int(ms)/1000,datetime.UTC).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]+'Z'

def okx(method,path,body=""):
    ts=ts_iso()
    sig=base64.b64encode(hmac.new(SEC.encode(),f"{ts}{method}{path}{body}".encode(),hashlib.sha256).digest()).decode()
    h={"User-Agent":"Mozilla/5.0","OK-ACCESS-KEY":KEY,"OK-ACCESS-SIGN":sig,"OK-ACCESS-TIMESTAMP":ts,"OK-ACCESS-PASSPHRASE":PAS}
    if body: h["Content-Type"]="application/json"
    try:
        return json.loads(_req("https://www.okx.com"+path,body.encode() if body else None,h).read())
    except urllib.error.HTTPError as e:
        return {"err":f"{e.code} {e.read().decode()[:200]}"}

def notify(title,txt):
    if not SCT: return
    try:
        _req(f"https://sctapi.ftqq.com/{SCT}.send",
             urllib.parse.urlencode({"title":title,"desp":txt}).encode(),
             {"Content-Type":"application/x-www-form-urlencoded"}).read()
    except Exception as e:
        log(f"notify-fail {e}")

def log(msg):
    print(f"{datetime.datetime.now(datetime.UTC).isoformat()} {msg}",flush=True)

def load_state():
    try:
        return json.loads(open(STATE_F).read())
    except Exception:
        return {"peak":{}}

def save_state(s):
    open(STATE_F,"w").write(json.dumps(s,ensure_ascii=False))

def price(inst):
    d=okx("GET",f"/api/v5/market/ticker?instId={inst}")
    return float(d["data"][0]["last"]) if d.get("data") else None

def sma60(inst="ZEC-USDT"):
    try:
        d=okx("GET",f"/api/v5/market/candles?instId={inst}&bar=1D&limit=60")
        rows=d.get("data") or []
        if len(rows)<60: return None
        return sum(float(r[4]) for r in rows)/60
    except Exception:
        return None

def holdings():
    d=okx("GET","/api/v5/account/balance")
    out={}
    for det in (d.get("data") or [{}])[0].get("details",[]):
        ccy=det["ccy"]; eq=float(det["eqUsd"])
        if ccy!="USDT" and eq>MIN_USD:
            out[ccy]={"eq":eq,"avail":float(det.get("availBal") or 0)}
    return out

def sell_all(ccy,avail,px,reason):
    inst=f"{ccy}-USDT"
    r=okx("POST","/api/v5/trade/order",json.dumps({"instId":inst,"tdMode":"cash","side":"sell","ordType":"market","sz":f"{avail:.8f}".rstrip('0').rstrip('.')}))
    ok=bool(r.get("data")) and not r.get("err")
    log(f"SELL {ccy} reason={reason} ok={ok} resp={json.dumps(r)[:200]}")
    with open("state.jsonl","a") as f:
        f.write(json.dumps({"ts":datetime.datetime.now(datetime.UTC).isoformat(),"action":"sell","ccy":ccy,"px":px,"reason":reason,"resp":json.dumps(r)[:300]})+"\n")
    notify(f"🚨已卖出{ccy}",f"原因: {reason}\n现价: {px}\n结果: {'✅成交' if ok else '❌失败 '+json.dumps(r)[:150]}")

def main():
    st=load_state(); peak=st.get("peak",{})
    last_sma=None; sma_t=0
    log(f"realtime guard start, loop {LOOP_SECONDS}s poll {POLL}s")
    t0=time.time(); n=0
    while time.time()-t0 < LOOP_SECONDS:
        n+=1
        try:
            hs=holdings()
            now=time.time()
            if now-sma_t>3600:
                last_sma=sma60(); sma_t=now
                log(f"SMA60 ZEC = {last_sma}")
            for ccy,h in hs.items():
                if h["avail"]<=0: continue
                px=price(f"{ccy}-USDT")
                if not px: continue
                pk=max(peak.get(ccy,0),px)
                peak[ccy]=pk
                dd=(pk-px)/pk if pk>0 else 0
                log(f"#{n} {ccy} px={px} peak={pk} dd={dd:.2%} val={h['eq']:.2f}U")
                if dd>=DRAWDOWN:
                    sell_all(ccy,h["avail"],px,f"移动止损 峰值{pk}回撤{dd:.1%}")
                    peak[ccy]=0
                elif ccy=="ZEC" and last_sma and px<last_sma:
                    sell_all(ccy,h["avail"],px,f"跌破60日线 {last_sma:.3f}")
                    peak[ccy]=0
        except Exception as e:
            log(f"loop-err {type(e).__name__} {e}")
        if n%30==0:
            save_state({"peak":peak})
        time.sleep(POLL)
    save_state({"peak":peak})
    log("loop end")

if __name__=="__main__":
    main()
