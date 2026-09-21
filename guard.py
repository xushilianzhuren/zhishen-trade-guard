#!/usr/bin/env python3
"""智神交易守护v4.0(2026-09-21):纯公开行情·10秒轮询·Actions稳定版
教训(v2卡死根因):Actions runner IP不在OKX白名单→签名调用401/被tarpit,公开行情无此问题
职责:监控+报警(Server酱)。下单由香港机(白名单IP)执行。
v4.0变更(主人钦定"只要能赚钱就能干·不死板·规则不合适就改"):
  ①监控对象从ZEC锚死改为COINS配置驱动——持仓变即改此表(09-21建仓NEAR)
  ②删除WLD观察线(已清仓·主人令"不要死板")
  ③ZEC降为纯观察(无成本·只报60日线跌破)·NEAR带成本监控
策略:①持仓币从峰值回撤>=5%→报警(对齐条件单0.95止损带) ②持仓币跌破60日线→报警 ③观察币破60日线→报警 ④每轮写state
"""
import urllib.request,json,time,os
SK=os.environ.get("SCTKEY","")
POLL=10
RUN_SECONDS=540   # 9分钟
DRAWDOWN=0.05
PEAK_F="peaks.json"
UA={"User-Agent":"Mozilla/5.0"}
# === 持仓配置表(唯一真相源·持仓变更即改这里并commit) ===
COINS={
  "NEAR":{"cost":4.359,"watch":True},    # 09-21建仓4.47006@4.359·止损单触发4.141
  "ZEC":{"cost":None,"watch":True},      # 09-20已清仓·纯观察
}

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

def sma60(inst):
    try:
        rows=g(f"https://www.okx.com/api/v5/market/candles?instId={inst}&bar=1D&limit=60")["data"]
        return sum(float(r[4]) for r in rows)/60 if len(rows)>=60 else None
    except Exception: return None

def main():
    peaks=load_peaks()
    smas={c:sma60(c+"-USDT") for c in COINS}
    sma_t=time.time()
    t0=time.time(); n=0; alerts=[]
    print(f"v4 start loop={RUN_SECONDS}s poll={POLL}s sma60={smas}",flush=True)
    while time.time()-t0<RUN_SECONDS:
        n+=1
        try:
            if time.time()-sma_t>3600:
                smas={c:sma60(c+"-USDT") for c in COINS}; sma_t=time.time()
            state={}
            for c,cfg in COINS.items():
                px=float(g(f"https://www.okx.com/api/v5/market/ticker?instId={c}-USDT")["data"][0]["last"])
                pk=max(peaks.get(c,0),px); peaks[c]=pk
                dd=(pk-px)/pk if pk>0 else 0
                sma=smas.get(c)
                state[c]=px
                if n%6==0: print(f"{c} px={px} peak={pk} dd={dd:.2%} sma60={sma and round(sma,1)}",flush=True)
                if cfg["cost"]:
                    if dd>=DRAWDOWN and f"trail{c}{int(pk)}" not in alerts:
                        alerts.append(f"trail{c}{int(pk)}")
                        notify(f"🚨{c}移动止损触发",f"峰值{pk:.4g}→现价{px:.4g} 回撤{dd:.1%}\n请确认条件单是否已成交")
                    elif sma and px<sma and f"sma{c}" not in alerts:
                        alerts.append(f"sma{c}")
                        notify(f"🚨{c}跌破60日线",f"现价{px:.4g} < 60日线{sma:.4g}\n请确认条件单/离场动作")
                elif sma and px<sma and f"obsv{c}" not in alerts:
                    alerts.append(f"obsv{c}")
                    notify(f"👀{c}观察:破60日线",f"现价{px:.4g} < 60日线{sma:.4g}(无持仓·观察线)")
            if n%30==0:
                open(PEAK_F,"w").write(json.dumps(peaks))
        except Exception as e:
            print(f"loop-err {type(e).__name__} {e}",flush=True)
        time.sleep(POLL)
    open(PEAK_F,"w").write(json.dumps(peaks))
    row={"ts":time.strftime("%F %T")}
    for c in COINS:
        try:
            px=float(g(f"https://www.okx.com/api/v5/market/ticker?instId={c}-USDT")["data"][0]["last"])
            row[c.lower()]=px
            cost=COINS[c]["cost"]
            if cost: row[c.lower()+"_pct"]=round((px/cost-1)*100,2)
            row[c.lower()+"_ma60"]=smas.get(c) and round(smas[c],1)
        except Exception: pass
    row["alerts"]=alerts
    with open("state.jsonl","a") as f:
        f.write(json.dumps(row)+"\n")
    print(f"loop end polls={n} alerts={alerts}",flush=True)

if __name__=="__main__":
    main()
