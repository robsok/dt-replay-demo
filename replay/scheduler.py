import asyncio, heapq, json, time
import pandas as pd
from dateutil import parser
import datetime
import pytz
from typing import AsyncIterator, Tuple, Dict, Any, Optional
from .config import AppCfg, StreamCfg

def _parse_ts(s: str, fmt: Optional[str], tzname: Optional[str]) -> pd.Timestamp:
    if fmt:
        ts = pd.to_datetime(s, format=fmt, errors="coerce")
    else:
        # ISO8601/epoch tolerant
        try:
            ts = pd.to_datetime(s, utc=True, errors="coerce")
        except Exception:
            ts = pd.to_datetime(parser.parse(s))
    if tzname and ts.tzinfo is None:
        ts = ts.tz_localize(tzname)
    return ts.tz_convert("UTC") if ts.tzinfo else ts.tz_localize("UTC")

def _load_stream(s: StreamCfg) -> pd.DataFrame:
    df = pd.read_csv(s.csv)
    schema = s.schema or {}
    if "rename" in schema:
        df = df.rename(columns=schema["rename"])
    # types
    for col, t in (schema.get("types") or {}).items():
        if t == "float":
            df[col] = pd.to_numeric(df[col], errors="coerce")
        elif t == "int":
            df[col] = pd.to_numeric(df[col], downcast="integer", errors="coerce")
        elif t == "str":
            df[col] = df[col].astype("string")
    # timestamp
    df["_ts"] = df[s.time_col].apply(lambda x: _parse_ts(str(x), s.time_fmt, s.tz))
    if s.drop_na_time:
        df = df.dropna(subset=["_ts"])
    return df.sort_values("_ts").reset_index(drop=True)

def _clip(df: pd.DataFrame, start: Optional[pd.Timestamp], end: Optional[pd.Timestamp]) -> pd.DataFrame:
    if start is not None:
        df = df[df["_ts"] >= start]
    if end is not None:
        df = df[df["_ts"] <= end]
    return df

async def merged_events(cfg: AppCfg) -> AsyncIterator[Tuple[pd.Timestamp,str,Dict[str,Any]]]:
    frames = []
    for s in cfg.streams:
        df = _load_stream(s)
        frames.append((s, df))
    # clip to global window
    start = pd.to_datetime(cfg.start).tz_localize("UTC") if cfg.start else None
    end   = pd.to_datetime(cfg.end).tz_localize("UTC")   if cfg.end   else None
    heaps = []
    for s, df in frames:
        df = _clip(df, start, end)
        it = df.iterrows()
        try:
            idx, row = next(it)
            heapq.heappush(heaps, (row["_ts"], s, it, row))
        except StopIteration:
            pass

    if not heaps:
        return

    sim_start_ts = heaps[0][0]  # earliest event timestamp
    wall_start = time.perf_counter()
    speed = max(0.0001, float(cfg.speed))  # avoid zero

    while heaps:
        ts, s, it, row = heapq.heappop(heaps)

        # pacing: wait until wall-clock catches up to sim time at configured speed
        sim_delta = (ts - sim_start_ts).total_seconds()
        target_wall = wall_start + sim_delta / speed
        now = time.perf_counter()
        if target_wall > now:
            await asyncio.sleep(target_wall - now)

        # emit event (exclude internal column)
        payload = {k: (None if k == "_ts" else v) for k, v in row.items() if k != "_ts"}
        yield ts, s.id, payload

        # push next from this stream
        try:
            idx, row2 = next(it)
            heapq.heappush(heaps, (row2["_ts"], s, it, row2))
        except StopIteration:
            pass

async def merged_events(cfg: AppCfg):
    ...
    sim_start = datetime.datetime.now()
    last_log = sim_start

    while heap:
        ev = heapq.heappop(heap)
        now = datetime.datetime.now()

        # every ~5 seconds, log simulated time
        if (now - last_log).total_seconds() > 5:
            print(f"[DEBUG] Sim time={ev['time']}, wall={now}")
            last_log = now

        yield ev