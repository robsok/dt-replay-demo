from __future__ import annotations

import asyncio
import heapq
import time
from itertools import count
from typing import AsyncIterator, Tuple, Dict, Any, Optional

import pandas as pd
from dateutil import parser

from .config import AppCfg, StreamCfg


def _parse_ts(s: str, fmt: Optional[str], tzname: Optional[str]) -> pd.Timestamp:
    """
    Parse a timestamp string using an optional format and timezone, returning UTC.
    - If fmt is provided, use it (coerce errors to NaT).
    - Otherwise try tolerant parsing with pandas; fall back to dateutil.
    - Localize to tzname if naive, then convert to UTC.
    """
    if fmt:
        ts = pd.to_datetime(s, format=fmt, errors="coerce")
    else:
        try:
            # tolerant: supports epoch/ISO8601, keep tz if present
            ts = pd.to_datetime(s, utc=True, errors="coerce")
        except Exception:
            ts = pd.to_datetime(parser.parse(s))
    if tzname and ts.tzinfo is None:
        ts = ts.tz_localize(tzname)
    return ts.tz_convert("UTC") if ts.tzinfo else ts.tz_localize("UTC")


def _load_stream(s: StreamCfg) -> pd.DataFrame:
    """
    Load a CSV defined by StreamCfg, apply optional renames and per-column types from s.schema,
    add an internal UTC timestamp column '_ts', drop NaT rows if requested, and return sorted.
    """
    df = pd.read_csv(s.csv)

    schema = s.schema or {}

    # Optional column renames
    if "rename" in schema:
        df = df.rename(columns=schema["rename"])

    # Optional type coercions; only cast columns that actually exist
    for col, t in (schema.get("types") or {}).items():
        if t in ("float", "number", "float64"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            else:
                print(f"[scheduler] Warning: column '{col}' not in {s.csv}, cannot cast to float.")
        elif t in ("int", "int64", "integer"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], downcast="integer", errors="coerce")
            else:
                print(f"[scheduler] Warning: column '{col}' not in {s.csv}, cannot cast to int.")
        elif t in ("str", "string"):
            if col in df.columns:
                df[col] = df[col].astype("string")
            else:
                print(f"[scheduler] Warning: column '{col}' not in {s.csv}, skipping string cast.")
        else:
            # Unknown type label: skip with a gentle note
            if col not in df.columns:
                print(f"[scheduler] Note: column '{col}' not in {s.csv}; type '{t}' ignored.")

    # Ensure timestamp column exists
    if s.time_col not in df.columns:
        raise ValueError(
            f"[scheduler] time_col '{s.time_col}' not found in {s.csv}. "
            f"Available columns: {list(df.columns)}"
        )

    # Parse timestamps to UTC
    df["_ts"] = df[s.time_col].apply(lambda x: _parse_ts(str(x), s.time_fmt, s.tz))

    if s.drop_na_time:
        df = df.dropna(subset=["_ts"])

    return df.sort_values("_ts").reset_index(drop=True)


def _clip(df: pd.DataFrame, start: Optional[pd.Timestamp], end: Optional[pd.Timestamp]) -> pd.DataFrame:
    """Restrict events to [start, end] window (inclusive)."""
    if start is not None:
        df = df[df["_ts"] >= start]
    if end is not None:
        df = df[df["_ts"] <= end]
    return df


async def merged_events(cfg: AppCfg) -> AsyncIterator[Tuple[pd.Timestamp, str, Dict[str, Any]]]:
    """
    Merge multiple streams in timestamp order and yield (ts, stream_id, payload) at
    real-time pace scaled by cfg.speed. Uses a heap with deterministic tie-breaking.
    """
    frames: list[tuple[StreamCfg, pd.DataFrame]] = []
    for s in cfg.streams:
        df = _load_stream(s)
        frames.append((s, df))

    # Global window (UTC)
    start = pd.to_datetime(cfg.start).tz_localize("UTC") if cfg.start else None
    end = pd.to_datetime(cfg.end).tz_localize("UTC") if cfg.end else None

    # Min-heap of (ts, stream_id, tie, iterator, current_row)
    heaps: list[tuple[pd.Timestamp, str, int, Any, pd.Series]] = []
    tie = count()

    for s, df in frames:
        df = _clip(df, start, end)
        it = df.iterrows()
        try:
            _, row = next(it)
            heapq.heappush(heaps, (row["_ts"], s.id, next(tie), it, row))
        except StopIteration:
            pass

    if not heaps:
        print("[scheduler] No events to replay")
        return

    # Find earliest and latest timestamps across all streams
    sim_start_ts = heaps[0][0]  # earliest event timestamp
    
    # Find the latest timestamp by looking at the last event in each stream
    latest_ts = sim_start_ts
    for s, df in frames:
        df = _clip(df, start, end)
        if not df.empty:
            stream_latest = df["_ts"].max()
            if stream_latest > latest_ts:
                latest_ts = stream_latest
    
    print(f"[scheduler] Replaying events from {sim_start_ts} to {latest_ts}")
    print(f"[scheduler] Time span: {(latest_ts - sim_start_ts).total_seconds():.0f} seconds ({(latest_ts - sim_start_ts).days} days)")
    print(f"[scheduler] Speed: {cfg.speed}x (will take ~{(latest_ts - sim_start_ts).total_seconds() / cfg.speed:.1f} seconds)")

    # pacing controls
    wall_start = time.perf_counter()
    speed = max(0.0001, float(cfg.speed))  # avoid zero or negative
    prev_ts = sim_start_ts  # track previous event timestamp for gap detection

    while heaps:
        ts, stream_id, _, it, row = heapq.heappop(heaps)

        # wall-clock pacing to simulate real time at configured speed
        sim_delta = (ts - sim_start_ts).total_seconds()
        target_wall = wall_start + sim_delta / speed
        now = time.perf_counter()
        sleep_time = target_wall - now
        
        # Cap maximum wait time to 2 seconds to skip large gaps
        # Calculate actual gap between consecutive events
        event_gap = (ts - prev_ts).total_seconds()
        if sleep_time > 2:
            print(f"[scheduler] Large gap detected: {event_gap:.1f}s between events, capping wait at 2s")
            sleep_time = 2
            
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)
        
        # Update previous timestamp for next iteration
        prev_ts = ts

        # emit event (exclude internal column)
        payload = {k: (None if k == "_ts" else v) for k, v in row.items() if k != "_ts"}
        yield ts, stream_id, payload

        # push next from this stream
        try:
            _, row2 = next(it)
            heapq.heappush(heaps, (row2["_ts"], stream_id, next(tie), it, row2))
        except StopIteration:
            pass
    
    print("[scheduler] Done - all events replayed")
