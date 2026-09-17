#!/usr/bin/env python3
"""智神交易守护v2.0实时版(2026-09-17):每次被cron唤醒后内嵌9.5分钟循环·10秒级轮询
策略: ①移动止损-5%(任一现货持仓从本轮峰值回撤)→市价全卖+Server酱
      ②ZEC跌破60日线→市价全卖+Server酱
      ③WLD观察线报警
卖出后留USDT不自动回买。workflow收尾自动commit state。
"""
import urllib.request,urllib.error,json,time,os,hmac,hashlib,base64,datetime
SK=os.environ.get("SCTKEY","")
KEY="d406e4f4-9918-46d5-a7de-6d660a7449cf"
SEC="567DD9C4EF2C5D7CA35CFA2060C513E6"
PAS="Aaa798718!"
RUN_SECONDS=555   # 9.25分钟,给commit留余量
POLL=10
DRAWDOWN=0.05
MIN_USD=1.0
PEAK_F="peaks.json"
ZEC_COST=1251.88

def ts_iso():
    r=json.loads(urllib.request.urlopen(urllib.request.Request("https://www.okx.com/api/v5/public/time",headers={"User-Agent":"Mozilla/5.0"}),timeout=10).read())
    ms=r["data"][0]["ts"]
    return datetime.datetime.fromtimestamp(int(ms)/1000,datetime.UTC).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]+'Z'

def okx(method,path,body=""):
    ts=ts_iso()
    sig=base64.b64encode(hmac.new(SEC.encode(),f"{ts}{method}{path}{body}".encode(),hashlib.sha256).digest()).decode()
    h={"User-Agent":"Mozilla/5.0","OK-ACCESS-KEY":KEY,"OK-ACCESS-SIGN":sig,"OK-ACCESS-TIMESTAMP":ts,"OK-ACCESS-PASSPHRASE":PAS}
    if body: h["Content-Type"]="application/json"
    try:
        return json.loads(urllib.request.urlopen(urllib.request.Request("https://www.okx.com"+path,data=body.encode() if body else None,headers=h,method=method),timeout=15).read())
    except urllib.error.HTTPError as e:
        return {"err":f"{e.code} {e.read().decode()[:200]}"}

def notify(title,desp):
    if not SK: return
    try:
        body=json.dumps({"title":title,"desp":desp}).encode()
        urllib.request.urlopen(urllib.request.Request(f"https://sctapi.ftqq.com/{SK}.send",data=body),timeout=10)
    except Exception as e: print("notify-fail",e,flush=True)

def log(m): print(f"{time.strftime('%H:%M:%S')} {m}",flush=True)

def g(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=12).read())

def sma60():
    try:
        rows=g("https://www.okx.com/api/v5/market/candles?instId=ZEC-USDT&bar=1D&limit=60")["data"]
        if len(rows)<60: return None
        return sum(float(r[4]) for r in rows)/60
    except Exception: return None

def holdings():
    d=okx("GET","/api/v5/account/balance")
    out={}
    for det in (d.get("data") or [{}])[0].get("details",[]):
        ccy=det["ccy"]; eq=float(det["eqUsd"])
        if ccy not in("USDT",) and eq>MIN_USD:
            out[ccy]={"eq":eq,"avail":float(det.get("availBal") or 0)}
    return out

def sell_all(ccy,avail,px,reason):
    inst=f"{ccy}-USDT"
    sz=f"{avail:.8f}".rstrip('0').rstrip('.')
    r=okx("POST","/api/v5/trade/order",json.dumps({"instId":inst,"tdMode":"cash","side":"sell","ordType":"market","sz":sz}))
    ok=bool(r.get("data")) and not r.get("err")
    log(f"SELL {ccy} {reason} ok={ok}")
    with open("state.jsonl","a") as f:
        f.write(json.dumps({"ts":time.strftime("%F %T"),"action":"sell","ccy":ccy,"px":px,"reason":reason,"ok":ok})+"\n")
    notify(f"🚨实时守护已卖出{ccy}",f"原因: {reason}\n现价: {px}\n结果: {'✅成交' if ok else '❌失败 '+json.dumps(r)[:150]}")

def load_peaks():
    try: return json.loads(open(PEAK_F).read())
    except Exception: return {}

def run():
    peaks=load_peaks()
    last_sma=sma60(); sma_t=time.time()
    log(f"guard v2 start loop={RUN_SECONDS}s poll={POLL}s sma60={last_sma}")
    t0=time.time(); n=0; alerts=[]
    while time.time()-t0<RUN_SECONDS:
        n+=1
        try:
            if time.time()-sma_t>3600:
                last_sma=sma60(); sma_t=time.time(); log(f"sma60={last_sma}")
            hs=holdings()
            for ccy,h in hs.items():
                if h["avail"]<=0: continue
                d=g(f"https://www.okx.com/api/v5/market/ticker?instId={ccy}-USDT")
                px=float(d["data"][0]["last"])
                pk=max(peaks.get(ccy,0),px); peaks[ccy]=pk
                dd=(pk-px)/pk if pk>0 else 0
                if n%6==0:  # 每分钟记一行防日志过大
                    log(f"{ccy} px={px} peak={pk} dd={dd:.2%} val={h['eq']:.2f}U")
                if dd>=DRAWDOWN:
                    sell_all(ccy,h["avail"],px,f"移动止损 峰{pk:.4f}回撤{dd:.1%}")
                    alerts.append(f"{ccy}移动止损{dd:.1%}已卖出"); peaks[ccy]=0
                elif ccy=="ZEC" and last_sma and px<last_sma:
                    sell_all(ccy,h["avail"],px,f"跌破60日线{last_sma:.2f}")
                    alerts.append(f"ZEC跌破60日线已卖出"); peaks[ccy]=0
            if n%30==0:
                pw=float(g("https://www.okx.com/api/v5/market/ticker?instId=WLD-USDT")["data"][0]["last"])
                wmsg=None
                if pw<0.350: wmsg=f"WLD {pw:.4f}跌破0.350(观察)"
                elif pw>0.400: wmsg=f"WLD {pw:.4f}涨破0.400"
                if wmsg and wmsg not in alerts: alerts.append(wmsg)
        except Exception as e:
            log(f"loop-err {type(e).__name__} {e}")
        if n%30==0:
            open(PEAK_F,"w").write(json.dumps(peaks))
        time.sleep(POLL)
    open(PEAK_F,"w").write(json.dumps(peaks))
    with open("state.jsonl","a") as f:
        f.write(json.dumps({"ts":time.strftime("%F %T"),"action":"loop_end","polls":n,"alerts":alerts})+"\n")
    if alerts: notify("智神交易报警", "\n\n".join(alerts))
    log(f"loop end polls={n}")

if __name__=="__main__":
    run()
