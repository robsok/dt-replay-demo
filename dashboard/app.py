# dashboard/app.py
import os, json, time, threading
import pandas as pd
import streamlit as st
import paho.mqtt.client as mqtt
import tempfile
import pickle
import dateutil.parser
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "dt/#")
MAX_ROWS = 2000  # cap to avoid unbounded growth

# Use a temp file to persist data between streamlit runs
TEMP_FILE = os.path.join(tempfile.gettempdir(), "mqtt_dashboard_data.pkl")

st.set_page_config(page_title="Lab Twin Dashboard", layout="wide")
st.title("Lab Digital Twin — Live Events")
st.caption(f"Broker: {MQTT_HOST}:{MQTT_PORT}  •  Topic: {MQTT_TOPIC}")

# Initialize session state
if "mqtt_started" not in st.session_state:
    st.session_state.mqtt_started = False

# Start MQTT client only once
if not st.session_state.mqtt_started:
    st.session_state.mqtt_started = True
    
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)

    def on_connect(client, userdata, flags, reason_code, properties):
        client.subscribe(MQTT_TOPIC)
        print(f"DEBUG: Connected to MQTT broker, subscribed to {MQTT_TOPIC}")

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            print(f"DEBUG: Raw MQTT payload: {json.dumps(payload, indent=2)}")
        except Exception as e:
            print(f"DEBUG: Failed to parse JSON: {e}")
            payload = {"payload": msg.payload.decode("utf-8", errors="ignore")}
        
        # Append to file instead of queue
        # Use the event timestamp from the message, fallback to current time
        event_ts = time.time()  # default fallback
        if isinstance(payload, dict) and 'ts' in payload:
            try:
                # Parse the ISO timestamp from the message
                event_ts = dateutil.parser.parse(payload['ts']).timestamp()
                print(f"DEBUG: Parsed event timestamp: {payload['ts']} -> {event_ts}")
            except Exception as e:
                print(f"DEBUG: Failed to parse timestamp {payload.get('ts')}: {e}")
        else:
            print(f"DEBUG: No 'ts' field in payload keys: {list(payload.keys()) if isinstance(payload, dict) else 'not dict'}")
        
        event = {
            "recv_ts": event_ts,  # now uses event timestamp
            "topic": msg.topic,
            **(payload if isinstance(payload, dict) else {"payload": payload}),
        }
        
        try:
            # Read existing data
            if os.path.exists(TEMP_FILE):
                with open(TEMP_FILE, 'rb') as f:
                    rows = pickle.load(f)
            else:
                rows = []
            
            # Add new event
            rows.append(event)
            
            # Keep only recent events
            if len(rows) > MAX_ROWS:
                rows = rows[-MAX_ROWS:]
            
            # Write back
            with open(TEMP_FILE, 'wb') as f:
                pickle.dump(rows, f)
                
            print(f"DEBUG: Saved message for topic {msg.topic}, total: {len(rows)}")
        except Exception as e:
            print(f"DEBUG: Error saving message: {e}")

    client.on_connect = on_connect
    client.on_message = on_message

    def run_mqtt():
        try:
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            client.loop_forever()
        except Exception as e:
            print(f"DEBUG: MQTT connection error: {e}")

    threading.Thread(target=run_mqtt, daemon=True).start()

# Load data from file
try:
    if os.path.exists(TEMP_FILE):
        with open(TEMP_FILE, 'rb') as f:
            rows = pickle.load(f)
        print(f"DEBUG: Loaded {len(rows)} rows from file")
    else:
        rows = []
        print("DEBUG: No data file found, starting fresh")
except Exception as e:
    print(f"DEBUG: Error loading data: {e}")
    rows = []

# Create DataFrame and calculate metrics
df = pd.DataFrame(rows)
if not df.empty:
    df["recv_time"] = pd.to_datetime(df["recv_ts"], unit="s")
    
    # Calculate metrics
    total_events = len(df)
    latest_event = df["recv_time"].max()  # now shows actual event time
    
    # Count events by stream type (extract from topic)
    df["stream_type"] = df["topic"].str.replace("lab/", "")
    stream_counts = df["stream_type"].value_counts().to_dict()
    
    # Top row - Latest event time and clear button
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.subheader("Lab Measurement Dashboard")
    with col2:
        st.metric("Latest Event", latest_event.strftime("%Y-%m-%d %H:%M:%S") if latest_event else "None")
    with col3:
        if st.button("Clear Data", type="secondary"):
            try:
                if os.path.exists(TEMP_FILE):
                    os.remove(TEMP_FILE)
                st.success("Data cleared!")
                st.rerun()
            except Exception as e:
                st.error(f"Error clearing data: {e}")
    
    # Metrics row - Event counters
    st.subheader("Event Counters")
    
    # Create columns for each stream type
    stream_types = ["weights", "packs", "properties", "magnetics", "density_volume", "photos"]
    cols = st.columns(len(stream_types))
    
    for i, stream_type in enumerate(stream_types):
        with cols[i]:
            count = stream_counts.get(stream_type, 0)
            st.metric(stream_type.title(), count)
    
    # Add total events metric
    st.metric("Total Events", total_events)
    
    # Timeline visualization section
    st.subheader("Event Timeline")
    
    # Create timeline graph with separate swimlanes for each stream type
    if len(df) > 0:
        # Color mapping for different stream types
        color_map = {
            'weights': '#FF6B6B',
            'packs': '#4ECDC4', 
            'properties': '#45B7D1',
            'magnetics': '#96CEB4',
            'density_volume': '#FECA57',
            'photos': '#FF9FF3'
        }
        
        # Create subplot with separate row for each stream type
        stream_types = df['stream_type'].unique()
        fig = make_subplots(
            rows=len(stream_types), 
            cols=1,
            shared_xaxes=True,
            subplot_titles=[f"{st.title()} Stream" for st in stream_types],
            vertical_spacing=0.05
        )
        
        # Add data for each stream type
        for i, stream_type in enumerate(stream_types, 1):
            stream_data = df[df['stream_type'] == stream_type].sort_values('recv_time')
            
            fig.add_trace(
                go.Scatter(
                    x=stream_data['recv_time'],
                    y=[stream_type] * len(stream_data),
                    mode='markers',
                    marker=dict(
                        size=8,
                        color=color_map.get(stream_type, '#95A5A6'),
                        symbol='circle'
                    ),
                    name=stream_type.title(),
                    text=stream_data.apply(lambda row: f"{row['stream_type']}: {row.get('data', {}).get('id', 'N/A')}", axis=1),
                    hovertemplate='<b>%{text}</b><br>Time: %{x}<br><extra></extra>'
                ),
                row=i, col=1
            )
            
            # Remove y-axis labels for cleaner look
            fig.update_yaxes(showticklabels=False, row=i, col=1)
        
        # Update layout
        fig.update_layout(
            height=150 * len(stream_types),
            showlegend=True,
            title="Lab Measurements Timeline (Swimlane View)",
            xaxis_title="Time"
        )
        
        # Update x-axis to show time nicely
        fig.update_xaxes(
            tickangle=45,
            tickformat='%H:%M:%S'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data for timeline visualization")
    
    # Bottom section - Event stream
    st.subheader("Live Event Stream")
    # Rename recv_time to event_time for clarity
    display_df = df.sort_values("recv_ts", ascending=False)[["recv_time", "stream_type", "ts", "stream", "data"]].copy()
    display_df = display_df.rename(columns={"recv_time": "event_time"})
    st.dataframe(display_df, use_container_width=True, height=400)
else:
    st.info("Waiting for events…")

# Lightweight auto-refresh (~1s)
# New API in modern Streamlit:
st.query_params["t"] = str(time.time())
time.sleep(1)
st.rerun()
