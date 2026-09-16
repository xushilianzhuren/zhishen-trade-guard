#!/usr/bin/env python3
"""智神交易守护v1.0:ZEC止损线+60日线+WLD观察线·报警走Server酱"""
import urllib.request,json,time,os
SK=os.environ.get("SCTKEY","")
def g(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=12).read())
def candles(inst,bar,n):
    return [float(c[4]) for c in g(f"https://www.okx.com/api/v5/market/candles?instId={inst}&bar={bar}&limit={n}")["data"]][::-1]
def ma(s,n): return sum(s[-n:])/n
alerts=[]
px=candles("ZEC-USDT","1H",2)[-1]
d60=ma(candles("ZEC-USDT","1D",60),60)
if px<d60: alerts.append(f"ZEC {px:.1f}跌破60日线{d60:.1f}→离场信号")
px_wld=candles("WLD-USDT","1H",2)[-1]
if px_wld<0.350: alerts.append(f"WLD {px_wld:.4f}跌破0.350(已清仓·观察)")
if px_wld>0.400: alerts.append(f"WLD {px_wld:.4f}涨破0.400")
zc=px/1251.88-1
if abs(zc)>0.08: alerts.append(f"ZEC持仓波动{zc*100:+.1f}%(成本1251.88)")
state={"ts":time.strftime("%F %T"),"zec":px,"wld":px_wld,"ma60":round(d60,1),"zc_pct":round(zc*100,2),"alerts":alerts}
with open("state.jsonl","a") as f: f.write(json.dumps(state)+"\n")
print(json.dumps(state,ensure_ascii=False))
if alerts and SK:
    body=json.dumps({"title":"智神交易报警","desp":"\n\n".join(alerts)}).encode()
    urllib.request.urlopen(urllib.request.Request(f"https://sctapi.ftqq.com/{SK}.send",data=body),timeout=10)
