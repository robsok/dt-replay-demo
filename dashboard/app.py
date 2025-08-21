import json, threading, queue, time
import streamlit as st
from paho.mqtt import client as mqtt
import pandas as pd

EVENTS = queue.Queue()

def on_msg(_cli, _ud, msg):
    try:
        EVENTS.put_nowait((msg.topic, json.loads(msg.payload.decode())))
    except Exception:
        pass

def start_mqtt(host="localhost", port=1883, topics=("lab/+",)):
    cli = mqtt.Client()
    cli.on_message = on_msg
    cli.connect(host, port, keepalive=30)
    for t in topics:
        cli.subscribe(t)
    threading.Thread(target=cli.loop_forever, daemon=True).start()

st.set_page_config(page_title="Lab Replay Monitor", layout="wide")
st.title("Lab Replay Monitor")

if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=["ts","stream","topic","id","value"])

col1, col2, col3 = st.columns(3)
speed = col1.metric("Sim speed (×)", "—")
throughput = col2.metric("Events / min", "—")
unique_streams = col3.metric("Streams", "—")

with st.sidebar:
    st.header("Connection")
    host = st.text_input("MQTT host", "localhost")
    port = st.number_input("MQTT port", 1883)
    if st.button("Connect", type="primary"):
        start_mqtt(host, int(port))

placeholder = st.empty()
last_count = 0
last_time = time.time()

while True:
    # drain queue
    drained = 0
    while not EVENTS.empty():
        topic, msg = EVENTS.get()
        drained += 1
        ts = pd.to_datetime(msg.get("ts"))
        stream = msg.get("stream")
        data = msg.get("data", {})
        st.session_state.df.loc[len(st.session_state.df)] = [
            ts, stream, topic, data.get("id"), data.get("value")
        ]

    # KPIs
    now = time.time()
    dt = now - last_time
    if dt >= 2.0:
        curr_count = len(st.session_state.df)
        ev_per_min = (curr_count - last_count) / dt * 60.0
        throughput = ev_per_min
        last_time = now; last_count = curr_count
        unique = st.session_state.df["stream"].nunique()
        col2.metric("Events / min", f"{ev_per_min:,.0f}")
        col3.metric("Streams", f"{unique}")

    # timeline plot (last N minutes)
    df = st.session_state.df.sort_values("ts")
    if not df.empty:
        recent = df[df["ts"] >= (pd.Timestamp.utcnow().tz_localize("UTC") - pd.Timedelta(minutes=10))]
        placeholder.altair_chart(
            (recent.assign(t=lambda d: d["ts"].dt.tz_convert("UTC"))
                   .pipe(lambda d: __import__("altair").Chart(d)
                         .mark_point()
                         .encode(x="t:T", y="stream:N", color="stream:N", tooltip=["topic","id","value","t"]))),
            use_container_width=True
        )
    time.sleep(0.25)
