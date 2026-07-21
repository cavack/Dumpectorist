# ruff: noqa
from __future__ import annotations
import json, math, statistics, time, urllib.error, urllib.parse, urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
UTC=timezone.utc
START=datetime(2026,4,22,tzinfo=UTC); END=datetime(2026,7,21,tzinfo=UTC)
BAR_MS=4*60*60*1000
CFG={
 "capital_start":100.0,"risk_per_trade":0.15,"max_leverage":3.0,
 "signal_threshold":82.0,"max_expected_target_hours":18,
 "min_sell_trade_ratio":0.52,"max_book_churn_pct":58.0,
 "min_cross_exchange_confirmations":2,"max_candidates":30,
 "min_quote_volume_usdt":5_000_000.0,"min_pump_pct_24h":0.14,
 "target_price_pct":0.10,"stop_price_pct":0.04,
 "taker_fee_each_side":0.0006,"slippage_each_side":0.0005,
 "funding_cost_per_8h":0.0001,"max_open_positions":2,
}
BASES=("https://fapi.binance.com","https://fapi1.binance.com","https://fapi2.binance.com","https://fapi3.binance.com","https://fapi4.binance.com")
UA="DumpectoristResearchBacktest/1.0 (+https://github.com/cavack/Dumpectorist)"
@dataclass(frozen=True)
class Bar:
 ts:int; open:float; high:float; low:float; close:float; volume:float; quote:float; buy_quote:float
 @property
 def sell_ratio(self): return max(0.0,min(1.0,1-self.buy_quote/self.quote)) if self.quote>0 else .5
@dataclass(frozen=True)
class Signal:
 symbol:str; signal_i:int; entry_i:int; support:float; pump:float; volume_ratio:float; sell_ratio:float; expected_hours:float; score:float; confirms:int; sources:tuple[str,...]
@dataclass
class Trade:
 symbol:str; signal_ts:int; entry_ts:int; exit_ts:int; entry:float; exit:float; target:float; stop:float; outcome:str; hold_hours:int; score:float; confirms:int; sources:list[str]; pump:float; sell_ratio:float
 margin:float=0; notional:float=0; gross_roe:float=0; fee_roe:float=0; slippage_roe:float=0; funding_roe:float=0; net_roe:float=0; pnl:float=0; equity_before:float=0; equity_after:float=0
class HTTP:
 def __init__(self): self.base=None; self.requests=0; self.errors=[]
 def get(self,url,retries=3):
  last=None
  for n in range(retries):
   self.requests+=1
   try:
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=30) as r:
     if r.status!=200: raise RuntimeError(f"HTTP {r.status}")
     return json.loads(r.read())
   except Exception as e:
    last=e; self.errors.append(f"{url}: {type(e).__name__}: {e}")
    if n+1<retries: time.sleep(min(6,2**n))
  raise RuntimeError(f"request failed: {url}: {last}")
 def binance(self,path,params=None):
  q=urllib.parse.urlencode(params or {}); suffix=path+("?"+q if q else "")
  hosts=(self.base,) if self.base else BASES
  for host in hosts:
   if not host: continue
   try: data=self.get(host+suffix,2); self.base=host; return data
   except Exception: pass
  self.base=None
  for host in BASES:
   try: data=self.get(host+suffix,2); self.base=host; return data
   except Exception: pass
  raise RuntimeError(f"all Binance hosts failed: {suffix}")
def ms(dt): return int(dt.timestamp()*1000)
def iso(ts): return datetime.fromtimestamp(ts/1000,tz=UTC).isoformat()
def num(x):
 v=float(x)
 if not math.isfinite(v): raise ValueError(f"non-finite {x}")
 return v
def bbar(r): return Bar(int(r[0]),num(r[1]),num(r[2]),num(r[3]),num(r[4]),num(r[5]),num(r[7]),num(r[10]))
def fetch_binance(h,symbol,start,end):
 rows=h.binance("/fapi/v1/klines",{"symbol":symbol,"interval":"4h","startTime":start,"endTime":end-1,"limit":1000})
 return [bbar(r) for r in rows if start<=int(r[0])<end]
def fetch_bybit(h,symbol,start,end):
 q=urllib.parse.urlencode({"category":"linear","symbol":symbol,"interval":"240","start":start,"end":end-1,"limit":1000})
 d=h.get("https://api.bybit.com/v5/market/kline?"+q,2)
 if str(d.get("retCode"))!="0": raise RuntimeError(d.get("retMsg"))
 return {int(r[0]):num(r[4]) for r in d.get("result",{}).get("list",[]) if start<=int(r[0])<end}
def fetch_mexc(h,symbol,start,end):
 if not symbol.endswith("USDT"): return {}
 contract=symbol[:-4]+"_USDT"; q=urllib.parse.urlencode({"interval":"Hour4","start":start//1000,"end":(end-1)//1000})
 d=h.get(f"https://contract.mexc.com/api/v1/contract/kline/{contract}?{q}",2)
 if not d.get("success"): raise RuntimeError(d.get("message") or d.get("code"))
 p=d.get("data") or {}; out={}
 for t,c in zip(p.get("time") or [],p.get("close") or [],strict=False):
  ts=int(t)*1000
  if start<=ts<end: out[ts]=num(c)
 return out
def ema(vals,n):
 if not vals:return []
 a=2/(n+1); out=[vals[0]]
 for v in vals[1:]: out.append(a*v+(1-a)*out[-1])
 return out
def tranges(bars):
 out=[]
 for i,b in enumerate(bars):
  pc=bars[i-1].close if i else b.close
  out.append(max(b.high-b.low,abs(b.high-pc),abs(b.low-pc)))
 return out
def rmean(vals,end,n):
 x=vals[max(0,end-n):end]; return statistics.fmean(x) if x else 0
def rsum(vals,end,n): return sum(vals[max(0,end-n):end])
def rmin(vals,end,n):
 x=vals[max(0,end-n):end]; return min(x) if x else math.inf
def confirm(closes,ts):
 ks=sorted(k for k in closes if k<=ts)
 if len(ks)<8:return False
 now=closes[ks[-1]]; past=closes[ks[-4]]; recent=[closes[k] for k in ks[-6:]]
 return now<past and now<ema(recent,5)[-1]
def signals(symbol,bars,bench):
 if len(bars)<60:return []
 close=[b.close for b in bars]; low=[b.low for b in bars]; qv=[b.quote for b in bars]; sr=[b.sell_ratio for b in bars]
 e5=ema(close,5); e18=ema(close,18); tr=tranges(bars); out=[]; cooldown=-1
 for i in range(42,len(bars)-2):
  if i<=cooldown:continue
  pump_i=max(range(i-18,i-2),key=lambda j:bars[j].high)
  pre=min(b.low for b in bars[max(0,pump_i-6):pump_i+1]); pump=bars[pump_i].high/pre-1
  if pump<CFG["min_pump_pct_24h"]:continue
  pq=rsum(qv,pump_i+1,6); prev=rsum(qv,max(0,pump_i-5),6); vr=pq/prev if prev>0 else 99
  if pq<CFG["min_quote_volume_usdt"]:continue
  bi=i-1; support=rmin(low,bi,6); br=bars[bi]
  if not(br.close<support*.998 and br.close<e5[bi]):continue
  rc=bars[i]
  if not(rc.high>=support*.995 and rc.close<support and rc.close<=rc.open):continue
  sell=rmean(sr,i+1,2)
  if sell<CFG["min_sell_trade_ratio"]:continue
  atr=rmean(tr,i+1,14)/rc.close; exp=CFG["target_price_pct"]/max(atr,1e-6)*4
  if exp>CFG["max_expected_target_hours"]:continue
  sources=["BINANCE"]+[name for name,c in bench.items() if confirm(c,rc.ts)]; conf=len(sources)
  if conf<CFG["min_cross_exchange_confirmations"]:continue
  daily=rc.close<rmin(low,i,18); trend=rc.close<e18[i] and e5[i]<e18[i]; depth=max(0,support/rc.close-1)
  score=min(30,20+max(0,pump-.14)*100)+min(12,6+max(0,vr-1)*4)+min(15,8+depth*250)+20+min(10,5+max(0,sell-.52)*50)+(8 if daily else 3)+(5 if trend else 0)+min(10,5*(conf-1))
  if score<CFG["signal_threshold"]:continue
  out.append(Signal(symbol,i,i+1,support,pump,vr,sell,exp,score,conf,tuple(sources))); cooldown=i+math.ceil(CFG["max_expected_target_hours"]/4)
 return out
def simulate(sig,bars):
 eb=bars[sig.entry_i]; entry=eb.open*(1-CFG["slippage_each_side"]); target=entry*(1-CFG["target_price_pct"]); stop=entry*(1+CFG["stop_price_pct"])
 last=min(len(bars)-1,sig.entry_i+math.ceil(CFG["max_expected_target_hours"]/4)-1); outcome="TIMEOUT"; xi=last; exitp=bars[last].close*(1+CFG["slippage_each_side"])
 for j in range(sig.entry_i,last+1):
  hs=bars[j].high>=stop; ht=bars[j].low<=target
  if hs: outcome="STOP"; xi=j; exitp=stop*(1+CFG["slippage_each_side"]); break
  if ht: outcome="TARGET"; xi=j; exitp=target*(1+CFG["slippage_each_side"]); break
 price=(entry-exitp)/entry; slip=2*CFG["slippage_each_side"]*CFG["max_leverage"]
 gross=price*CFG["max_leverage"]+slip; fee=2*CFG["taker_fee_each_side"]*CFG["max_leverage"]
 hours=(xi-sig.entry_i+1)*4; fund=-math.ceil(hours/8)*CFG["funding_cost_per_8h"]*CFG["max_leverage"]
 net=gross-fee-slip+fund
 return Trade(sig.symbol,bars[sig.signal_i].ts,eb.ts,bars[xi].ts,entry,exitp,target,stop,outcome,hours,sig.score,sig.confirms,list(sig.sources),sig.pump,sig.sell_ratio,gross_roe=gross,fee_roe=fee,slippage_roe=slip,funding_roe=fund,net_roe=net)
def portfolio(candidates):
 candidates=sorted(candidates,key=lambda t:(t.entry_ts,t.symbol)); equity=CFG["capital_start"]; open_=[]; done=[]; curve=[(ms(START),equity)]; skipped=0
 for t in candidates:
  keep=[]
  for x in open_:
   if x.exit_ts<=t.entry_ts: equity+=x.pnl; x.equity_after=equity; done.append(x); curve.append((x.exit_ts,equity))
   else: keep.append(x)
  open_=keep
  if len(open_)>=CFG["max_open_positions"]: skipped+=1; continue
  t.equity_before=equity; t.margin=equity*CFG["risk_per_trade"]; t.notional=t.margin*CFG["max_leverage"]; t.pnl=t.margin*t.net_roe; open_.append(t)
 for t in sorted(open_,key=lambda x:x.exit_ts): equity+=t.pnl; t.equity_after=equity; done.append(t); curve.append((t.exit_ts,equity))
 return sorted(done,key=lambda t:(t.exit_ts,t.symbol)),sorted(curve),skipped
def metrics(trades,curve):
 end=curve[-1][1]; wins=[t for t in trades if t.pnl>0]; losses=[t for t in trades if t.pnl<0]; gp=sum(t.pnl for t in wins); gl=abs(sum(t.pnl for t in losses)); peak=0; dd=0
 for _,e in curve: peak=max(peak,e); dd=max(dd,1-e/peak if peak else 0)
 ps={}
 for t in trades:
  x=ps.setdefault(t.symbol,{"trades":0,"wins":0,"pnl":0.0}); x["trades"]+=1; x["wins"]+=int(t.pnl>0); x["pnl"]+=t.pnl
 for x in ps.values(): x["win_rate_pct"]=100*x["wins"]/x["trades"]
 return {"capital_start":CFG["capital_start"],"capital_end":end,"net_return_pct":100*(end/CFG["capital_start"]-1),"trade_count":len(trades),"wins":len(wins),"losses":len(losses),"win_rate_pct":100*len(wins)/len(trades) if trades else 0,"profit_factor":gp/gl if gl else (999 if gp else 0),"max_drawdown_pct":100*dd,"average_hold_hours":statistics.fmean(t.hold_hours for t in trades) if trades else 0,"targets":sum(t.outcome=="TARGET" for t in trades),"stops":sum(t.outcome=="STOP" for t in trades),"timeouts":sum(t.outcome=="TIMEOUT" for t in trades),"per_symbol":ps}
def universe(h):
 info=h.binance("/fapi/v1/exchangeInfo"); tick=h.binance("/fapi/v1/ticker/24hr"); tm={x["symbol"]:x for x in tick if isinstance(x,dict) and x.get("symbol")}; ok=[]
 for m in info.get("symbols",[]):
  if m.get("status")!="TRADING" or m.get("contractType")!="PERPETUAL" or m.get("quoteAsset")!="USDT":continue
  t=tm.get(m.get("symbol"));
  if not t:continue
  p=num(t.get("lastPrice",0)); q=num(t.get("quoteVolume",0))
  if 0<p<1 and q>=CFG["min_quote_volume_usdt"]: ok.append((q,m["symbol"]))
 ok.sort(reverse=True); return [s for _,s in ok[:CFG["max_candidates"]]],len(ok)
def run():
 h=HTTP(); warm=ms(START-timedelta(days=8)); end=ms(END); eval_start=ms(START); uni,eligible=universe(h); candidates=[]; diag={}
 for rank,symbol in enumerate(uni,1):
  try: bars=fetch_binance(h,symbol,warm,end)
  except Exception as e: diag[symbol]={"status":"binance_error","error":f"{type(e).__name__}: {e}"}; continue
  bench={}; errs={}
  for name,fn in (("BYBIT",fetch_bybit),("MEXC",fetch_mexc)):
   try:
    x=fn(h,symbol,warm,end)
    if x: bench[name]=x
    else: errs[name]="no bars or contract"
   except Exception as e: errs[name]=f"{type(e).__name__}: {e}"
  sig=signals(symbol,bars,bench); tr=[simulate(x,bars) for x in sig if bars[x.entry_i].ts>=eval_start]; candidates.extend(tr)
  diag[symbol]={"status":"ok","rank":rank,"bars":len(bars),"benchmarks":sorted(bench),"benchmark_errors":errs,"signals":len(sig),"candidate_trades":len(tr)}
 trades,curve,skipped=portfolio(candidates); result={"run":{"name":"WaterfallHunter/Dumpectorist 90-day approximate optimized backtest","generated_at":datetime.now(tz=UTC).isoformat(),"period_start":START.isoformat(),"period_end_exclusive":END.isoformat(),"timeframe":"4h","binance_base":h.base,"http_requests":h.requests},"config":CFG,"metrics":metrics(trades,curve),"universe":uni,"eligible_universe_count":eligible,"trades":[{**asdict(t),"signal_time":iso(t.signal_ts),"entry_time":iso(t.entry_ts),"exit_time":iso(t.exit_ts)} for t in trades],"equity_curve":[{"time":iso(t),"equity":e} for t,e in curve],"skipped_max_open_positions":skipped,"symbol_diagnostics":diag,"limitations":["OHLCV/trade-flow approximation; historical order-book churn/spoofing unavailable.","Current active-contract universe creates survivorship/listing bias.","Binance history is a benchmark proxy; LBank execution depth and historical funding are not reconstructed.","Bybit/MEXC confirmations are best effort and symbol availability differs.","News/social/on-chain intelligence is not historically replayed.","Rules are fixed before observing the run; no post-result optimization."],"validation":{"no_lookahead":"closed bars only; entry at next 4h open","intrabar":"conservative stop-first","book_churn_gate":"not evaluated"}}
 Path("research_backtest_result.json").write_text(json.dumps(result,indent=2,sort_keys=True),encoding="utf-8"); return result
def main():
 r=run(); print("RESEARCH_BACKTEST_RESULT_BEGIN"); print(json.dumps(r,sort_keys=True)); print("RESEARCH_BACKTEST_RESULT_END")
if __name__=="__main__": main()
