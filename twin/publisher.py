import time, json
from datetime import datetime, timezone
import pandas as pd
from paho.mqtt.publish import single

BROKER_HOST = "localhost"
BROKER_PORT = 1883
SPEED = 60.0  # 60x faster than real time

CSV_PATH = "../data/events.csv"
TOPIC_BASE = "orders/events/"

def to_dt(s: str) -> datetime:
    # parse Zulu format
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

def main():
    df = pd.read_csv(CSV_PATH)
    df["event_dt"] = df["event_time"].map(to_dt)
    df = df.sort_values("event_dt")

    # establish the simulated clock relative to first event
    first_ts = df.iloc[0]["event_dt"]
    wall_start = time.time()

    for _, row in df.iterrows():
        target_ts = row["event_dt"]
        sim_elapsed = (target_ts - first_ts).total_seconds()
        wall_target = wall_start + sim_elapsed / SPEED

        # wait until it's time to publish this event (in real wall time)
        now = time.time()
        sleep_sec = wall_target - now
        if sleep_sec > 0:
            time.sleep(sleep_sec)

        topic = f"{TOPIC_BASE}{row['order_id']}"
        payload = {
            "event_time": row["event_time"],   # keep original timestamp
            "order_id": row["order_id"],
            "event": row["event"],
        }
        single(topic, payload=json.dumps(payload), hostname=BROKER_HOST, port=BROKER_PORT)
        print(f"[PUB] {row['order_id']} {row['event']} at {row['event_time']} -> {topic}")

if __name__ == "__main__":
    main()
