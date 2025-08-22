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
    
    event_count = 0
    try:
        async with Client(cfg.broker.host, cfg.broker.port, **auth) as client:
            async for ts, stream_id, payload in merged_events(cfg):
                event_count += 1
                topic = next(s.topic for s in cfg.streams if s.id == stream_id)
                msg = {"ts": ts.isoformat(), "stream": stream_id, "data": payload}
                event_time = payload.get('created_at') or ts.strftime('%Y-%m-%d %H:%M:%S')
                log.info(f"[PUBLISH #{event_count}] {stream_id} → {topic} @ {event_time}")
                await client.publish(topic, json.dumps(msg), qos=cfg.broker.qos, retain=cfg.broker.retain)
                
                # Log progress every 100 events
                if event_count % 100 == 0:
                    log.info(f"[PROGRESS] Published {event_count} events, latest: {event_time}")
                    
    except Exception as e:
        log.error(f"[ERROR] Publisher stopped after {event_count} events: {e}")
        raise
    finally:
        log.info(f"[FINAL] Published total of {event_count} events")
