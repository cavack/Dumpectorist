# ruff: noqa
from __future__ import annotations
import csv, io, json, math, statistics, time, urllib.error, urllib.parse, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
UTC=timezone.utc
START=datetime(2026,4,22,tzinfo=UTC); END=datetime(2026,7,21,tzinfo=UTC); BAR_MS=4*60*60*1000
CFG={"capital_start":100.0,"risk_per_trade":0.15,"max_leverage":3.0,"signal_threshold":82.0,"max_expected_target_hours":18,"min_sell_trade_ratio":0.52,"max_book_churn_pct":58.0,"min_cross_exchange_confirmations":2,"max_candidates":30,"min_quote_volume_usdt":5_000_000.0,"min_pump_pct_24h":0.14,"target_price_pct":0.10,"stop_price_pct":0.04,"taker_fee_each_side":0.0006,"slippage_each_side":0.0005,"funding_cost_per_8h":0.0001,"max_open_positions":2}
WATCHLIST=("DOGEUSDT","1000PEPEUSDT","1000SHIBUSDT","1000BONKUSDT","1000FLOKIUSDT","WIFUSDT","POPCATUSDT","TURBOUSDT","BRETTUSDT","CATUSDT","GOATUSDT","ACTUSDT","PNUTUSDT","FARTCOINUSDT","MOODENGUSDT","MEMEUSDT","BOMEUSDT","PEOPLEUSDT","1000SATSUSDT","ANIMEUSDT","WOOUSDT","REDUSDT","NIGHTUSDT","PENGUUSDT","NOTUSDT")
UA="DumpectoristResearchBacktest/1.1 (+https://github.com/cavack/Dumpectorist)"
@dataclass(frozen=True)
class Bar:
 ts:int; open:float; high:float; low:float; close:float; volume:float; quote:float; buy_quote:float
 @property
 def sell_ratio(self): return max(0,min(1,1-self.buy_quote/self.quote)) if self.quote>0 else .5
@dataclass(frozen=True)
class Signal:
 symbol:str; signal_i:int; entry_i:int; support:float; pump:float; volume_ratio:float; sell_ratio:float; expected_hours:float; score:float; confirms:int; sources:tuple[str,...]
@dataclass
class Trade:
 symbol:str; signal_ts:int; entry_ts:int; exit_ts:int; entry:float; exit:float; target:float; stop:float; outcome:str; hold_hours:int; score:float; confirms:int; sources:list[str]; pump:float; sell_ratio:float
 margin:float=0; notional:float=0; gross_roe:float=0; fee_roe:float=0; slippage_roe:float=0; funding_roe:float=0; net_roe:float=0; pnl:float=0; equity_before:float=0; equity_after:float=0
def ms(x): return int(x.timestamp()*1000)
def iso(x): return datetime.fromtimestamp(x/1000,tz=UTC).isoformat()
def num(x):
 v=float(x)
 if not math.isfinite(v): raise ValueError(x)
 return v
def get_bytes(url,retries=2):
 last=None
 for n in range(retries):
  try:
   req=urllib.request.Request(url,headers={"User-Agent":UA})
   with urllib.request.urlopen(req,timeout=25) as r: return r.read()
  except urllib.error.HTTPError as e:
   if e.code==404:return None
   last=e
  except Exception as e:last=e
  if n+1<retries:time.sleep(1+n)
 raise RuntimeError(f"download failed {url}: {last}")
def get_json(url,retries=2):
 raw=get_bytes(url,retries)
 if raw is None:raise RuntimeError(f"not found {url}")
 return json.loads(raw)
def parse_zip(raw):
 if raw is None:return []
 z=zipfile.ZipFile(io.BytesIO(raw)); rows=[]
 for name in z.namelist():
  with z.open(name) as f:
   text=io.TextIOWrapper(f,encoding="utf-8"); reader=csv.reader(text)
   for r in reader:
    if not r or not r[0].isdigit():continue
    rows.append(Bar(int(r[0]),num(r[1]),num(r[2]),num(r[3]),num(r[4]),num(r[5]),num(r[7]),num(r[10])))
 return rows
def archive_url(symbol,kind,stamp): return f"https://data.binance.vision/data/futures/um/{kind}/klines/{symbol}/4h/{symbol}-4h-{stamp}.zip"
def load_archive_symbol(symbol):
 probe_stamp="2026-07-20"; probe=get_bytes(archive_url(symbol,"daily",probe_stamp),1)
 if probe is None:return symbol,[],"no_2026-07-20_archive"
 bars=parse_zip(probe); monthly=[]
 for stamp in ("2026-04","2026-05","2026-06"):
  raw=get_bytes(archive_url(symbol,"monthly",stamp),2)
  if raw:monthly.extend(parse_zip(raw))
 july=get_bytes(archive_url(symbol,"monthly","2026-07"),1)
 if july: monthly.extend(parse_zip(july))
 else:
  d=date(2026,7,1)
  while d<=date(2026,7,19):
   raw=get_bytes(archive_url(symbol,"daily",d.isoformat()),1)
   if raw:monthly.extend(parse_zip(raw))
   d+=timedelta(days=1)
 monthly.extend(bars); start=ms(START-timedelta(days=8)); end=ms(END); unique={b.ts:b for b in monthly if start<=b.ts<end}
 return symbol,[unique[k] for k in sorted(unique)],"ok"
def fetch_bybit(symbol,start,end):
 q=urllib.parse.urlencode({"category":"linear","symbol":symbol,"interval":"240","start":start,"end":end-1,"limit":1000}); d=get_json("https://api.bybit.com/v5/market/kline?"+q,2)
 if str(d.get("retCode"))!="0":raise RuntimeError(d.get("retMsg"))
 return {int(r[0]):num(r[4]) for r in d.get("result",{}).get("list",[]) if start<=int(r[0])<end}
def fetch_mexc(symbol,start,end):
 c=symbol[:-4]+"_USDT"; q=urllib.parse.urlencode({"interval":"Hour4","start":start//1000,"end":(end-1)//1000}); d=get_json(f"https://contract.mexc.com/api/v1/contract/kline/{c}?{q}",2)
 if not d.get("success"):raise RuntimeError(d.get("message") or d.get("code"))
 p=d.get("data") or {}; out={}
 for t,x in zip(p.get("time") or [],p.get("close") or [],strict=False):
  ts=int(t)*1000
  if start<=ts<end:out[ts]=num(x)
 return out
def ema(a,n):
 if not a:return []
 k=2/(n+1); out=[a[0]]
 for x in a[1:]:out.append(k*x+(1-k)*out[-1])
 return out
def tranges(b):
 out=[]
 for i,x in enumerate(b):
  p=b[i-1].close if i else x.close; out.append(max(x.high-x.low,abs(x.high-p),abs(x.low-p)))
 return out
def rmean(a,e,n):
 x=a[max(0,e-n):e];return statistics.fmean(x) if x else 0
def rsum(a,e,n):return sum(a[max(0,e-n):e])
def rmin(a,e,n):
 x=a[max(0,e-n):e];return min(x) if x else math.inf
def confirm(c,ts):
 k=sorted(x for x in c if x<=ts)
 if len(k)<8:return False
 now=c[k[-1]];past=c[k[-4]];return now<past and now<ema([c[x] for x in k[-6:]],5)[-1]
def scan(symbol,bars,bench=None,enforce=True):
 if len(bars)<60:return []
 close=[x.close for x in bars];low=[x.low for x in bars];qv=[x.quote for x in bars];sr=[x.sell_ratio for x in bars];e5=ema(close,5);e18=ema(close,18);tr=tranges(bars);out=[];cool=-1;bench=bench or {}
 for i in range(42,len(bars)-2):
  if i<=cool:continue
  pi=max(range(i-18,i-2),key=lambda j:bars[j].high);pre=min(x.low for x in bars[max(0,pi-6):pi+1]);pump=bars[pi].high/pre-1
  if pump<CFG["min_pump_pct_24h"]:continue
  pq=rsum(qv,pi+1,6);prev=rsum(qv,max(0,pi-5),6);vr=pq/prev if prev>0 else 99
  if pq<CFG["min_quote_volume_usdt"]:continue
  bi=i-1;support=rmin(low,bi,6);br=bars[bi]
  if not(br.close<support*.998 and br.close<e5[bi]):continue
  rc=bars[i]
  if not(rc.high>=support*.995 and rc.close<support and rc.close<=rc.open):continue
  sell=rmean(sr,i+1,2)
  if sell<CFG["min_sell_trade_ratio"]:continue
  atr=rmean(tr,i+1,14)/rc.close;expected=CFG["target_price_pct"]/max(atr,1e-6)*4
  if expected>CFG["max_expected_target_hours"]:continue
  sources=["BINANCE_ARCHIVE"]+[n for n,c in bench.items() if confirm(c,rc.ts)];conf=len(sources)
  if enforce and conf<CFG["min_cross_exchange_confirmations"]:continue
  daily=rc.close<rmin(low,i,18);trend=rc.close<e18[i] and e5[i]<e18[i];depth=max(0,support/rc.close-1)
  score=min(30,20+max(0,pump-.14)*100)+min(12,6+max(0,vr-1)*4)+min(15,8+depth*250)+20+min(10,5+max(0,sell-.52)*50)+(8 if daily else 3)+(5 if trend else 0)+min(10,5*(conf-1))
  threshold=CFG["signal_threshold"]-(5 if not enforce else 0)
  if score<threshold:continue
  out.append(Signal(symbol,i,i+1,support,pump,vr,sell,expected,score,conf,tuple(sources)));cool=i+math.ceil(CFG["max_expected_target_hours"]/4)
 return out
def simulate(s,b):
 eb=b[s.entry_i];entry=eb.open*(1-CFG["slippage_each_side"]);target=entry*(1-CFG["target_price_pct"]);stop=entry*(1+CFG["stop_price_pct"]);last=min(len(b)-1,s.entry_i+math.ceil(CFG["max_expected_target_hours"]/4)-1);outcome="TIMEOUT";xi=last;xp=b[last].close*(1+CFG["slippage_each_side"])
 for j in range(s.entry_i,last+1):
  if b[j].high>=stop:outcome="STOP";xi=j;xp=stop*(1+CFG["slippage_each_side"]);break
  if b[j].low<=target:outcome="TARGET";xi=j;xp=target*(1+CFG["slippage_each_side"]);break
 slip=2*CFG["slippage_each_side"]*CFG["max_leverage"];gross=(entry-xp)/entry*CFG["max_leverage"]+slip;fee=2*CFG["taker_fee_each_side"]*CFG["max_leverage"];hours=(xi-s.entry_i+1)*4;fund=-math.ceil(hours/8)*CFG["funding_cost_per_8h"]*CFG["max_leverage"]
 return Trade(s.symbol,b[s.signal_i].ts,eb.ts,b[xi].ts,entry,xp,target,stop,outcome,hours,s.score,s.confirms,list(s.sources),s.pump,s.sell_ratio,gross_roe=gross,fee_roe=fee,slippage_roe=slip,funding_roe=fund,net_roe=gross-fee-slip+fund)
def portfolio(a):
 a=sorted(a,key=lambda x:(x.entry_ts,x.symbol));equity=CFG["capital_start"];open_=[];done=[];curve=[(ms(START),equity)];skip=0
 for t in a:
  keep=[]
  for x in open_:
   if x.exit_ts<=t.entry_ts:equity+=x.pnl;x.equity_after=equity;done.append(x);curve.append((x.exit_ts,equity))
   else:keep.append(x)
  open_=keep
  if len(open_)>=CFG["max_open_positions"]:skip+=1;continue
  t.equity_before=equity;t.margin=equity*CFG["risk_per_trade"];t.notional=t.margin*CFG["max_leverage"];t.pnl=t.margin*t.net_roe;open_.append(t)
 for t in sorted(open_,key=lambda x:x.exit_ts):equity+=t.pnl;t.equity_after=equity;done.append(t);curve.append((t.exit_ts,equity))
 return sorted(done,key=lambda x:(x.exit_ts,x.symbol)),sorted(curve),skip
def metrics(t,c):
 end=c[-1][1];w=[x for x in t if x.pnl>0];l=[x for x in t if x.pnl<0];gp=sum(x.pnl for x in w);gl=abs(sum(x.pnl for x in l));peak=0;dd=0;ps={}
 for _,e in c:peak=max(peak,e);dd=max(dd,1-e/peak if peak else 0)
 for x in t:
  d=ps.setdefault(x.symbol,{"trades":0,"wins":0,"pnl":0.0});d["trades"]+=1;d["wins"]+=int(x.pnl>0);d["pnl"]+=x.pnl
 for d in ps.values():d["win_rate_pct"]=100*d["wins"]/d["trades"]
 return {"capital_start":CFG["capital_start"],"capital_end":end,"net_return_pct":100*(end/CFG["capital_start"]-1),"trade_count":len(t),"wins":len(w),"losses":len(l),"win_rate_pct":100*len(w)/len(t) if t else 0,"profit_factor":gp/gl if gl else (999 if gp else 0),"max_drawdown_pct":100*dd,"average_hold_hours":statistics.fmean(x.hold_hours for x in t) if t else 0,"targets":sum(x.outcome=="TARGET" for x in t),"stops":sum(x.outcome=="STOP" for x in t),"timeouts":sum(x.outcome=="TIMEOUT" for x in t),"per_symbol":ps}
def run():
 loaded={};diag={}
 with ThreadPoolExecutor(max_workers=6) as pool:
  futures={pool.submit(load_archive_symbol,s):s for s in WATCHLIST}
  for f in as_completed(futures):
   s,b,status=f.result();diag[s]={"archive_status":status,"bars":len(b)}
   if b:loaded[s]=b
 ranked=[]
 for s,b in loaded.items():
  last=[x for x in b if x.ts<ms(END)][-6:]
  if len(last)==6 and last[-1].close<1 and sum(x.quote for x in last)>=CFG["min_quote_volume_usdt"]:ranked.append((sum(x.quote for x in last),s))
 ranked.sort(reverse=True);universe=[s for _,s in ranked[:CFG["max_candidates"]]];candidates=[];warm=ms(START-timedelta(days=8));end=ms(END);start=ms(START)
 for rank,s in enumerate(universe,1):
  b=loaded[s];pre=scan(s,b,enforce=False);bench={};errs={}
  if pre:
   for n,fn in (("BYBIT",fetch_bybit),("MEXC",fetch_mexc)):
    try:
     x=fn(s,warm,end)
     if x:bench[n]=x
     else:errs[n]="no bars"
    except Exception as e:errs[n]=f"{type(e).__name__}: {e}"
  sig=scan(s,b,bench,True);tr=[simulate(x,b) for x in sig if b[x.entry_i].ts>=start];candidates.extend(tr);diag[s].update({"rank":rank,"pre_signals":len(pre),"benchmarks":sorted(bench),"benchmark_errors":errs,"signals":len(sig),"candidate_trades":len(tr)})
 trades,curve,skip=portfolio(candidates);result={"run":{"name":"WaterfallHunter/Dumpectorist 90-day approximate optimized backtest","generated_at":datetime.now(tz=UTC).isoformat(),"period_start":START.isoformat(),"period_end_exclusive":END.isoformat(),"timeframe":"4h","primary_source":"data.binance.vision USD-M futures archives"},"config":CFG,"watchlist":list(WATCHLIST),"universe":universe,"metrics":metrics(trades,curve),"trades":[{**asdict(x),"signal_time":iso(x.signal_ts),"entry_time":iso(x.entry_ts),"exit_time":iso(x.exit_ts)} for x in trades],"equity_curve":[{"time":iso(t),"equity":e} for t,e in curve],"skipped_max_open_positions":skip,"symbol_diagnostics":diag,"limitations":["OHLCV/trade-flow approximation; historical order-book churn/spoofing unavailable.","Fixed current-style watchlist creates survivorship/listing bias.","Binance archive history is a benchmark proxy; LBank execution depth and historical funding are not reconstructed.","Bybit/MEXC confirmations are best effort and symbol availability differs.","News/social/on-chain intelligence is not historically replayed.","Rules are fixed before observing the run; no post-result optimization."],"validation":{"no_lookahead":"closed bars only; entry at next 4h open","intrabar":"conservative stop-first","book_churn_gate":"not evaluated"}}
 Path("research_backtest_result.json").write_text(json.dumps(result,indent=2,sort_keys=True),encoding="utf-8");return result
def main():
 r=run();print("RESEARCH_BACKTEST_RESULT_BEGIN");print(json.dumps(r,sort_keys=True));print("RESEARCH_BACKTEST_RESULT_END")
if __name__=="__main__":main()
