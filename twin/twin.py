import json, queue, threading, time
from datetime import datetime
from typing import Dict

import simpy
from paho.mqtt.client import Client as MqttClient
from models import OrderState

MQTT_HOST = "localhost"
MQTT_PORT = 1883
TOPIC = "orders/events/#"

# thread-safe buffer for incoming events
inbox: "queue.Queue[dict]" = queue.Queue()

def parse_time(s: str) -> datetime:
    # assume ISO8601 with Z
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")

def mqtt_thread():
    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            inbox.put(payload)
        except Exception as e:
            print(f"[MQTT] bad payload: {e}")

    client = MqttClient()
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.subscribe(TOPIC)
    client.on_message = on_message
    client.loop_forever()

def twin_process(env: simpy.Environment, state: Dict[str, OrderState]):
    # simple polling loop that integrates external events into SimPy
    while True:
        try:
            payload = inbox.get_nowait()
        except queue.Empty:
            # advance simulated time a bit; adjust cadence as desired
            yield env.timeout(0.1)
            continue

        order_id = payload["order_id"]
        event = payload["event"]
        ts = parse_time(payload["event_time"])

        if order_id not in state:
            state[order_id] = OrderState(order_id=order_id)

        st = state[order_id]
        st.update(event, ts)

        print(f"[{env.now:7.2f}] {order_id} -> {event} @ {ts.isoformat()}")

        if event == "Delivered":
            lt = st.lead_time_minutes()
            sla = st.sla_breached()
            print(f"   Lead time (min): {lt:.1f} | SLA breached: {sla}")

        # advance a tiny simulated tick per event consumed
        yield env.timeout(0.01)

def main():
    # start MQTT listener thread
    t = threading.Thread(target=mqtt_thread, daemon=True)
    t.start()
    print("[Twin] MQTT listener started.")

    env = simpy.Environment()
    state: Dict[str, OrderState] = {}
    env.process(twin_process(env, state))
    env.run()  # runs until you Ctrl+C

if __name__ == "__main__":
    main()
