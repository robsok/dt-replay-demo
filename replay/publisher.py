import asyncio, json
from aiomqtt import Client, MqttError
from typing import Dict, Any
from .config import AppCfg
from .scheduler import merged_events
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

async def run_publish(cfg: AppCfg):
    auth = {}
    if cfg.broker.username:
        auth = {"username": cfg.broker.username, "password": cfg.broker.password}
    async with Client(cfg.broker.host, cfg.broker.port, **auth) as client:
        async for ts, stream_id, payload in merged_events(cfg):
            topic = next(s.topic for s in cfg.streams if s.id == stream_id)
            msg = {"ts": ts.isoformat(), "stream": stream_id, "data": payload}
            log.info(f"[PUBLISH] {stream_id} → {topic} @ {payload.get('time')} (payload={payload})")
            await client.publish(topic, json.dumps(msg), qos=cfg.broker.qos, retain=cfg.broker.retain)
