# dashboard/app.py
import os, json, time, threading, queue
import pandas as pd
import streamlit as st
import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "dt/#")
MAX_ROWS = 2000  # cap to avoid unbounded growth

st.set_page_config(page_title="Lab Twin Dashboard", layout="wide")
st.title("Lab Digital Twin — Live Events")
st.caption(f"Broker: {MQTT_HOST}:{MQTT_PORT}  •  Topic: {MQTT_TOPIC}")

# Initialise state exactly once
if "q" not in st.session_state:
    st.session_state.q = queue.Queue()
    st.session_state.rows = []

    # paho-mqtt v2 callback API (avoids deprecation warning)
    # If you’re on an older paho, drop the callback_api_version kwarg.
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)

    def on_connect(client, userdata, flags, reason_code, properties):
        # v2 signature: reason_code replaces rc
        client.subscribe(MQTT_TOPIC)

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            payload = {"payload": msg.payload.decode("utf-8", errors="ignore")}
        st.session_state.q.put({
            "recv_ts": time.time(),
            "topic": msg.topic,
            **(payload if isinstance(payload, dict) else {"payload": payload}),
        })

    client.on_connect = on_connect
    client.on_message = on_message

    def run_mqtt():
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_forever()

    threading.Thread(target=run_mqtt, daemon=True).start()

# Drain any queued messages into our table
while not st.session_state.q.empty():
    st.session_state.rows.append(st.session_state.q.get())
    if len(st.session_state.rows) > MAX_ROWS:
        st.session_state.rows = st.session_state.rows[-MAX_ROWS:]

# Display
df = pd.DataFrame(st.session_state.rows)
if not df.empty:
    df["recv_time"] = pd.to_datetime(df["recv_ts"], unit="s")
    st.dataframe(df.sort_values("recv_ts", ascending=False), use_container_width=True, height=600)
else:
    st.info("Waiting for events…")

# Lightweight auto-refresh (~1s)
# New API in modern Streamlit:
st.query_params["t"] = str(time.time())
time.sleep(1)
st.rerun()
