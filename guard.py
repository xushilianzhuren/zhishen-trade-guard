#!/usr/bin/env python3
"""智神交易守护v3.0(2026-09-17):纯公开行情·10秒轮询·Actions稳定版
教训(v2卡死根因):Actions runner IP不在OKX白名单→签名调用401/被tarpit,公开行情无此问题
职责:监控+报警(Server酱)。下单由沙箱(白名单IP)执行。
策略:①ZEC从本轮峰值回撤>=5%→报警 ②ZEC跌破60日线→报警 ③WLD观察线 ④每轮写state
"""
import urllib.request,json,time,os
SK=os.environ.get("SCTKEY","")
POLL=10
RUN_SECONDS=540   # 9分钟
DRAWDOWN=0.05
PEAK_F="peaks.json"
ZEC_COST=1251.88
UA={"User-Agent":"Mozilla/5.0"}

def g(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=12).read())

def notify(title,desp):
    if not SK: return
    body=json.dumps({"title":title,"desp":desp}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(f"https://sctapi.ftqq.com/{SK}.send",data=body),timeout=10)
    except Exception as e: print("notify-fail",e,flush=True)

def load_peaks():
    try: return json.loads(open(PEAK_F).read())
    except Exception: return {}

def sma60():
    try:
        rows=g("https://www.okx.com/api/v5/market/candles?instId=ZEC-USDT&bar=1D&limit=60")["data"]
        return sum(float(r[4]) for r in rows)/60 if len(rows)>=60 else None
    except Exception: return None

def main():
    peaks=load_peaks()
    last_sma=sma60(); sma_t=time.time()
    t0=time.time(); n=0; alerts=[]
    print(f"v3 start loop={RUN_SECONDS}s poll={POLL}s sma60={last_sma}",flush=True)
    while time.time()-t0<RUN_SECONDS:
        n+=1
        try:
            if time.time()-sma_t>3600:
                last_sma=sma60(); sma_t=time.time()
            px=float(g("https://www.okx.com/api/v5/market/ticker?instId=ZEC-USDT")["data"][0]["last"])
            pk=max(peaks.get("ZEC",0),px); peaks["ZEC"]=pk
            dd=(pk-px)/pk if pk>0 else 0
            if n%6==0: print(f"ZEC px={px} peak={pk} dd={dd:.2%} sma60={last_sma and round(last_sma,1)}",flush=True)
            if dd>=DRAWDOWN and f"trail{int(pk)}" not in alerts:
                alerts.append(f"trail{int(pk)}")
                notify("🚨ZEC移动止损触发",f"峰值{pk:.1f}→现价{px:.1f} 回撤{dd:.1%}\n请确认条件单是否已成交")
            elif last_sma and px<last_sma and "sma" not in alerts:
                alerts.append("sma")
                notify("🚨ZEC跌破60日线",f"现价{px:.1f} < 60日线{last_sma:.1f}\n请确认条件单是否已成交")
            if n%30==0:
                pw=float(g("https://www.okx.com/api/v5/market/ticker?instId=WLD-USDT")["data"][0]["last"])
                w=None
                if pw<0.350: w=f"WLD {pw:.4f}<0.350"
                elif pw>0.400: w=f"WLD {pw:.4f}>0.400"
                if w and w not in alerts: alerts.append(w); notify("智神WLD观察",w)
            if n%30==0:
                open(PEAK_F,"w").write(json.dumps(peaks))
        except Exception as e:
            print(f"loop-err {type(e).__name__} {e}",flush=True)
        time.sleep(POLL)
    open(PEAK_F,"w").write(json.dumps(peaks))
    px=float(g("https://www.okx.com/api/v5/market/ticker?instId=ZEC-USDT")["data"][0]["last"])
    with open("state.jsonl","a") as f:
        f.write(json.dumps({"ts":time.strftime("%F %T"),"zec":px,"ma60":last_sma and round(last_sma,1),"zc_pct":round((px/ZEC_COST-1)*100,2),"alerts":alerts})+"\n")
    print(f"loop end polls={n} alerts={alerts}",flush=True)

if __name__=="__main__":
    main()
