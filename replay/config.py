# dt-replay-demo/replay/config.py
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from pathlib import Path
import yaml

@dataclass
class BrokerCfg:
    host: str = "localhost"
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    qos: int = 0
    retain: bool = False

@dataclass
class StreamCfg:
    id: str
    csv: str
    topic: str
    time_col: str
    time_fmt: Optional[str] = None
    tz: Optional[str] = None
    schema: Dict[str, Any] = None
    drop_na_time: bool = True
    entity_id_col: Optional[str] = None
    keep_cols: Optional[List[str]] = None
    drop_cols: Optional[List[str]] = None
    filter: Optional[str] = None

@dataclass
class AppCfg:
    speed: float = 60.0
    start: Optional[str] = None
    end: Optional[str] = None
    broker: BrokerCfg = None
    streams: List[StreamCfg] = None

def load_config(path: str) -> AppCfg:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {p}")
    raw = yaml.safe_load(p.read_text())

    broker = BrokerCfg(**(raw.get("broker") or {}))
    streams = [StreamCfg(**s) for s in (raw.get("streams") or [])]
    return AppCfg(
        speed=float(raw.get("speed", 60.0)),
        start=raw.get("start"),
        end=raw.get("end"),
        broker=broker,
        streams=streams,
    )
