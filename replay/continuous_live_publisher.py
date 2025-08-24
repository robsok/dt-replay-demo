"""
Continuous live publisher that streams data with no gaps - just a steady stream.
"""
import asyncio
import json
import pandas as pd
from datetime import datetime, timezone, timedelta
from aiomqtt import Client
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

async def run_continuous_live_publish(interval_seconds=2.0):
    """Stream CSV data continuously with fixed intervals."""
    
    # Configuration matching streams.yaml
    data_files = {
        "weights": {"csv": "data/weights.csv", "time_col": "created_at"},
        "density_volume": {"csv": "data/density_volume.csv", "time_col": "created_at"}, 
        "properties": {"csv": "data/properties.csv", "time_col": "created_at"},
        "packs": {"csv": "data/packs.csv", "time_col": "created_at"},
        "photos": {"csv": "data/photos.csv", "time_col": "created_at"},
        "events": {"csv": "data/events.csv", "time_col": "created_at"}
    }
    
    # Load all events (no timestamp parsing needed)
    all_events = []
    
    for stream_name, config in data_files.items():
        csv_file = config["csv"]
        
        if Path(csv_file).exists():
            try:
                df = pd.read_csv(csv_file)
                log.info(f"Loaded {len(df)} rows from {csv_file}")
                
                # Add all rows
                for _, row in df.iterrows():
                    # Convert row to dict, excluding NaN values
                    data = {k: v for k, v in row.to_dict().items() if pd.notna(v)}
                    all_events.append((stream_name, data))
                        
            except Exception as e:
                log.warning(f"Could not load {csv_file}: {e}")
    
    if not all_events:
        log.error("No events found in CSV files")
        return
    
    # Shuffle to mix measurement types
    import random
    random.shuffle(all_events)
    
    log.info(f"Total events to publish: {len(all_events)} (shuffled)")
    log.info(f"Publishing every {interval_seconds}s")
    
    # MQTT connection
    try:
        async with Client("localhost", 1883) as client:
            event_count = 0
            start_time = datetime.now(timezone.utc)
            
            for stream_name, data in all_events:
                event_count += 1
                
                # Calculate current timestamp (no gaps)
                current_time = start_time + timedelta(seconds=event_count * interval_seconds)
                
                # Create message with current timestamp
                topic = f"lab/{stream_name}"
                msg = {
                    "ts": current_time.isoformat(),
                    "stream": stream_name,
                    "data": data
                }
                
                # Publish message
                await client.publish(topic, json.dumps(msg))
                
                log.info(f"[LIVE #{event_count}] {stream_name} → {topic} @ {current_time.strftime('%H:%M:%S')}")
                
                # Progress logging
                if event_count % 100 == 0:
                    log.info(f"[PROGRESS] Published {event_count}/{len(all_events)} events")
                
                # Fixed interval - no gaps!
                await asyncio.sleep(interval_seconds)
            
            log.info(f"[COMPLETE] Published all {event_count} events")
            
    except Exception as e:
        log.error(f"MQTT error: {e}")

if __name__ == "__main__":
    asyncio.run(run_continuous_live_publish())