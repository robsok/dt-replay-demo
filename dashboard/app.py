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
import yaml

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "dt/#")
MAX_ROWS = 2000  # cap to avoid unbounded growth

# Use a temp file to persist data between streamlit runs
TEMP_FILE = os.path.join(tempfile.gettempdir(), "mqtt_dashboard_data.pkl")

# Load swimlane configuration
@st.cache_data(ttl=10)  # Cache for 10 seconds to allow refreshing
def load_swimlane_config():
    try:
        with open('/home/rms110/dt-replay-demo/config/swimlanes.yaml', 'r') as f:
            config = yaml.safe_load(f)
            return sorted(config['swimlanes'], key=lambda x: x['order'])
    except FileNotFoundError:
        st.error("Swimlane configuration file not found")
        return []

st.set_page_config(page_title="Lab Twin Dashboard", layout="wide")
st.title("Lab Digital Twin — Live Events")
st.caption(f"Broker: {MQTT_HOST}:{MQTT_PORT}  •  Topic: {MQTT_TOPIC}")

# Check if data file was recently updated (within last 60 seconds)
if os.path.exists(TEMP_FILE):
    file_age = time.time() - os.path.getmtime(TEMP_FILE)
    if file_age < 60:
        st.success(f"📡 MQTT data active (last update: {int(file_age)}s ago)")
    else:
        st.warning(f"⚠️  MQTT data stale (last update: {int(file_age/60)}min ago)")
else:
    st.error("❌ No MQTT data file found")

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
            import fcntl
            # Use file locking to prevent corruption
            lock_file = TEMP_FILE + ".lock"
            
            with open(lock_file, 'w') as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                
                # Read existing data
                if os.path.exists(TEMP_FILE):
                    try:
                        with open(TEMP_FILE, 'rb') as f:
                            rows = pickle.load(f)
                    except (pickle.PickleError, EOFError) as pe:
                        print(f"DEBUG: Corrupted pickle file, starting fresh: {pe}")
                        rows = []
                else:
                    rows = []
                
                # Add new event
                rows.append(event)
                
                # Keep only recent events
                if len(rows) > MAX_ROWS:
                    rows = rows[-MAX_ROWS:]
                
                # Write back atomically
                temp_file = TEMP_FILE + ".tmp"
                with open(temp_file, 'wb') as f:
                    pickle.dump(rows, f)
                os.rename(temp_file, TEMP_FILE)
                    
                print(f"DEBUG: Saved message for topic {msg.topic}, total: {len(rows)}")
        except Exception as e:
            print(f"DEBUG: Error saving message: {e}")

    client.on_connect = on_connect
    client.on_message = on_message

    def run_mqtt():
        try:
            print(f"DEBUG: Attempting MQTT connection to {MQTT_HOST}:{MQTT_PORT}")
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            print(f"DEBUG: MQTT connection initiated, starting loop")
            client.loop_forever()
        except Exception as e:
            print(f"DEBUG: MQTT connection error: {e}")
            print(f"DEBUG: Error type: {type(e).__name__}")

    threading.Thread(target=run_mqtt, daemon=True).start()

# Load data from file
try:
    import fcntl
    if os.path.exists(TEMP_FILE):
        lock_file = TEMP_FILE + ".lock"
        try:
            with open(lock_file, 'w') as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
                with open(TEMP_FILE, 'rb') as f:
                    rows = pickle.load(f)
            print(f"DEBUG: Loaded {len(rows)} rows from file")
        except (pickle.PickleError, EOFError) as pe:
            print(f"DEBUG: Corrupted pickle file during load, starting fresh: {pe}")
            rows = []
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
                st.cache_data.clear()  # Clear Streamlit cache
                st.success("Data cleared!")
                st.rerun()
            except Exception as e:
                st.error(f"Error clearing data: {e}")
    
    # Metrics row - Event counters
    st.subheader("Event Counters")
    
    # Create columns for each swimlane from config
    swimlanes_config = load_swimlane_config()
    cols = st.columns(len(swimlanes_config))
    
    for i, swimlane in enumerate(swimlanes_config):
        with cols[i]:
            # Sum counts for all streams in this swimlane
            swimlane_count = sum(stream_counts.get(stream, 0) for stream in swimlane['streams'])
            
            # Special styling for events
            if swimlane['name'] == "Events":
                st.metric(f"📋 {swimlane['name']}", swimlane_count)
            else:
                st.metric(swimlane['name'], swimlane_count)
    
    # Add total events metric
    st.metric("Total Events", total_events)
    
    # Timeline visualization section
    st.subheader("Event Timeline")
    
    # Timeline controls
    col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
    with col1:
        zoom_level = st.selectbox("Zoom", ["Week", "Month", "Quarter", "Year"], index=0)
    with col2:
        if st.button("← Previous"):
            if "timeline_offset" not in st.session_state:
                st.session_state.timeline_offset = 0
            st.session_state.timeline_offset -= 1
            st.rerun()
    with col3:
        if st.button("Next →"):
            if "timeline_offset" not in st.session_state:
                st.session_state.timeline_offset = 0
            st.session_state.timeline_offset += 1
            st.rerun()
    with col4:
        if st.button("Jump to Latest"):
            st.session_state.timeline_offset = 0
            st.rerun()
    
    # Initialize timeline offset
    if "timeline_offset" not in st.session_state:
        st.session_state.timeline_offset = 0
    
    # Load swimlane configuration (already sorted by order)
    swimlanes = load_swimlane_config()
    
    # Create timeline graph with separate swimlanes for each stream type
    if len(df) > 0 and swimlanes:
        # Calculate time window based on zoom level and offset
        latest_time = df['recv_time'].max()
        
        # Define time window durations
        time_windows = {
            "Week": pd.Timedelta(weeks=1),
            "Month": pd.Timedelta(days=30), 
            "Quarter": pd.Timedelta(days=90),
            "Year": pd.Timedelta(days=365)
        }
        
        window_duration = time_windows[zoom_level]
        
        # Always show latest event time (or current time if no events) on the right, extend backwards
        reference_time = latest_time if not df.empty else pd.Timestamp.now()
        window_end = reference_time - (st.session_state.timeline_offset * window_duration)  
        window_start = window_end - window_duration
        
        # Filter data to time window
        if zoom_level == "Week":
            # For week view, exclude the last day to show exactly 7 days
            actual_end = window_end - pd.Timedelta(days=1)
            window_df = df[
                (df['recv_time'] >= window_start) & 
                (df['recv_time'] < actual_end)  # Use < instead of <=
            ].copy()
        else:
            window_df = df[
                (df['recv_time'] >= window_start) & 
                (df['recv_time'] <= window_end)
            ].copy()
        
        # Show time window info  
        if not window_df.empty:
            data_start = window_df['recv_time'].min().date()
            data_end = window_df['recv_time'].max().date() 
            days_in_data = (data_end - data_start).days + 1
        else:
            data_start = data_end = None
            days_in_data = 0
            
        # Show clean time window info without variable debug data
        st.info(f"📅 {zoom_level} view: {window_start.strftime('%b %d')} to {window_end.strftime('%b %d, %Y')} | {len(window_df)} events")
        
        # Use windowed data for visualization
        df_viz = window_df
        
        # Create color mapping from swimlane config
        color_map = {stream: sl['color'] for sl in swimlanes for stream in sl['streams']}
        
        # Severity color mapping for events
        severity_colors = {
            'info': '#4ECDC4',
            'warning': '#FFA500', 
            'error': '#FF6B6B',
            'critical': '#8B0000'
        }
        
        # Get events for annotations (not shown in swimlanes)
        events_df = df_viz[df_viz['stream_type'] == 'events'] if 'events' in df_viz['stream_type'].values else pd.DataFrame()
        
        # Show ALL swimlanes from config (don't filter by data availability)
        # Separate events swimlane from measurement swimlanes  
        events_swimlane = next((sl for sl in swimlanes if sl['name'] == 'Events'), None)
        measurement_swimlanes = [sl for sl in swimlanes if sl['name'] != 'Events']
        
        # Ensure measurement swimlanes are sorted by order
        measurement_swimlanes = sorted(measurement_swimlanes, key=lambda x: x['order'])
        
        
        # Create subplot with separate row for each measurement swimlane
        fig = make_subplots(
            rows=len(measurement_swimlanes), 
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08  # Slightly more space for separators
        )
        
        # Calculate daily event counts for each stream type across full time window
        if not df_viz.empty:
            df_viz['date'] = pd.to_datetime(df_viz['recv_time']).dt.date
            daily_counts = df_viz.groupby(['date', 'stream_type']).size().reset_index(name='count')
        else:
            daily_counts = pd.DataFrame(columns=['date', 'stream_type', 'count'])
        
        # Create complete date range for the full time window
        window_start_date = window_start.date()
        window_end_date = window_end.date()
        if zoom_level == "Week":
            # For week view, exclude the last day to match tick generation
            all_dates = pd.date_range(start=window_start_date, end=window_end_date, freq='D')[:-1]
        else:
            all_dates = pd.date_range(start=window_start_date, end=window_end_date, freq='D')
        all_dates = [d.date() for d in all_dates]

        # Add bars for each swimlane
        for i, swimlane in enumerate(measurement_swimlanes, 1):
            # Aggregate counts for all streams in this swimlane across ALL dates
            swimlane_counts_by_date = {}
            
            # Initialize all dates with zero counts
            for date in all_dates:
                swimlane_counts_by_date[date] = 0
            
            # Fill in actual counts where data exists
            for stream_type in swimlane['streams']:
                stream_counts = daily_counts[daily_counts['stream_type'] == stream_type]
                for _, row in stream_counts.iterrows():
                    if row['date'] in swimlane_counts_by_date:
                        swimlane_counts_by_date[row['date']] += row['count']
            
            # Convert to lists for plotting (maintaining date order)
            dates = [pd.Timestamp(date) for date in all_dates]
            counts = [swimlane_counts_by_date[date] for date in all_dates]
            
            # Add bars for this swimlane (even if all counts are zero)
            fig.add_trace(
                go.Bar(
                    x=dates,
                    y=counts,
                    name=swimlane['name'],
                    marker_color=swimlane['color'],
                    opacity=0.8,
                    width=86400000 * 0.6,  # 60% of day width for cleaner look
                    hovertemplate=f'<b>{swimlane["name"]}</b><br>Date: %{{x}}<br>Count: %{{y}}<extra></extra>',
                    base=0  # Anchor bars to y=0 baseline
                ),
                row=i, col=1
            )
            
            # Add text annotations for event counts (positioned in middle of day period)
            for j, (date, count) in enumerate(zip(dates, counts)):
                if count > 0:
                    # Calculate y position as middle of this swimlane using paper coordinates
                    y_pos = 1 - ((i - 0.5) / len(measurement_swimlanes))  # Middle of swimlane i
                    fig.add_annotation(
                        x=date,
                        y=y_pos,
                        xref="x", 
                        yref="paper",  # Use paper coordinates for consistent positioning
                        text=str(count),
                        showarrow=False,
                        font=dict(size=10, color="black"),
                        xanchor="center",
                        yanchor="middle"
                    )
            
            # Remove y-axis labels for cleaner look and set proper y-axis range
            fig.update_yaxes(
                showticklabels=False, 
                showgrid=False,
                zeroline=True,  # Show zero line
                zerolinecolor='rgba(0,0,0,0.3)',  # Subtle zero line
                range=[0, None],  # Start exactly at 0
                row=i, col=1
            )
        
        # Add horizontal separator lines between swimlanes
        for i in range(1, len(measurement_swimlanes)):
            # Calculate y position for separator (between rows)
            y_pos = 1 - (i / len(measurement_swimlanes))
            fig.add_shape(
                type="line",
                x0=0, x1=1,
                y0=y_pos, y1=y_pos,
                xref="paper", yref="paper",
                line=dict(
                    color="rgba(128,128,128,0.3)",
                    width=1
                ),
                layer="below"
            )
        
        # Add swimlane labels on the right side
        for i, swimlane in enumerate(measurement_swimlanes, 1):
            # Calculate y position for label (center of each row)
            y_pos = 1 - ((i - 0.5) / len(measurement_swimlanes))
            fig.add_annotation(
                x=1.01,  # Closer to plot edge
                y=y_pos,
                xref="paper", yref="paper",
                text=f"<b>{swimlane['name']}</b>",
                showarrow=False,
                font=dict(size=11, color="black"),
                xanchor="left",
                yanchor="middle"
            )
        
        # Ensure plot has margin for labels
        fig.update_layout(margin=dict(r=200))  # Right margin for labels
        
        # Add event annotations with stacking for same-day events
        if not events_df.empty:
            # Group events by date to handle stacking
            events_df['event_date'] = pd.to_datetime(events_df['recv_time']).dt.date
            date_groups = events_df.groupby('event_date')
            
            for date, day_events in date_groups:
                # Sort events within the day by time
                day_events = day_events.sort_values('recv_time')
                
                for stack_idx, (_, event) in enumerate(day_events.iterrows()):
                    event_data = event.get('data', {})
                    severity = event_data.get('severity', 'info')
                    text = event_data.get('text', 'Event')
                    operator = event_data.get('operator', 'Unknown')
                    event_time = event['recv_time']
                    
                    # Add vertical line as shape
                    fig.add_shape(
                        type="line",
                        x0=event_time, x1=event_time,
                        y0=0, y1=1,
                        xref="x", yref="paper",
                        line=dict(
                            color=severity_colors.get(severity, '#95A5A6'),
                            width=2,
                            dash='dash' if severity == 'warning' else 'solid'
                        )
                    )
                    
                    # Stack annotations vertically for same-day events
                    y_offset = 1.02 + (stack_idx * 0.12)  # Stack upwards
                    
                    # Add annotation for the event
                    fig.add_annotation(
                        x=event_time,
                        y=y_offset,
                        xref="x", yref="paper",
                        text=f"<b>{text}</b><br>({operator})",
                        showarrow=True,
                        arrowhead=2,
                        arrowsize=1,
                        arrowwidth=1,
                        arrowcolor=severity_colors.get(severity, '#95A5A6'),
                        font=dict(size=8, color=severity_colors.get(severity, '#95A5A6')),
                        bgcolor='rgba(255,255,255,0.9)',
                        bordercolor=severity_colors.get(severity, '#95A5A6'),
                        borderwidth=1
                    )
        
        # Update layout - make swimlanes thinner with space for x-axis labels
        fig.update_layout(
            height=60 * len(measurement_swimlanes) + 50,  # Extra 50px for x-axis labels
            showlegend=False,  # No legend needed - we have right-side labels
            title="Lab Measurements Timeline with Events (Swimlane View)",
            margin=dict(r=200, b=60)  # Right margin for swimlane labels, bottom for x-axis
        )
        
        # Add weekend and holiday background shading (use windowed data)
        if not df_viz.empty:
            date_range = pd.date_range(
                start=df_viz['recv_time'].min().date(),
                end=df_viz['recv_time'].max().date(),
                freq='D'
            )
            
            for date in date_range:
                # Add daily vertical grid lines at day boundaries (noon of each day)
                # This creates boundaries between days so bars fall within day periods
                boundary_time = pd.Timestamp(date) + pd.Timedelta(hours=12)  # Noon = day boundary
                line_width = 2 if zoom_level == "Week" else 1
                line_opacity = 0.5 if zoom_level == "Week" else 0.3
                fig.add_shape(
                    type="line",
                    x0=boundary_time, x1=boundary_time,
                    y0=0, y1=1,
                    xref="x", yref="paper",
                    line=dict(
                        color=f"rgba(128,128,128,{line_opacity})",
                        width=line_width
                    ),
                    layer="below"
                )
                
                # Check if weekend (Saturday=5, Sunday=6)
                if date.weekday() >= 5:  # Weekend
                    # Shift weekend shading to align with day boundaries (start at previous noon)
                    weekend_start = pd.Timestamp(date) - pd.Timedelta(hours=12)  # Start at previous noon
                    weekend_end = pd.Timestamp(date) + pd.Timedelta(hours=12)    # End at current noon
                    fig.add_shape(
                        type="rect",
                        x0=weekend_start, x1=weekend_end,
                        y0=0, y1=1,
                        xref="x", yref="paper",
                        fillcolor="rgba(128,128,128,0.15)",
                        line=dict(width=0),
                        layer="below"
                    )
                
                # Check for common Australian public holidays
                aus_holidays_2025 = [
                    '2025-01-01',  # New Year's Day
                    '2025-01-27',  # Australia Day
                    '2025-04-18',  # Good Friday
                    '2025-04-21',  # Easter Monday
                    '2025-04-25',  # ANZAC Day
                    '2025-06-09',  # Queen's Birthday
                    '2025-12-25',  # Christmas Day
                    '2025-12-26',  # Boxing Day
                ]
                
                if date.strftime('%Y-%m-%d') in aus_holidays_2025:
                    fig.add_shape(
                        type="rect",
                        x0=date, x1=date + pd.Timedelta(days=1),
                        y0=0, y1=1,
                        xref="x", yref="paper",
                        fillcolor="rgba(200,100,100,0.2)",  # Reddish for holidays
                        line=dict(width=0),
                        layer="below"
                    )

        # Configure x-axis based on zoom level - use full window, not just data range
        tick_vals = []
        tick_texts = []
        
        if zoom_level == "Week":
            # Daily ticks for full week window (7 days)
            window_start_date = window_start.date()
            window_end_date = window_end.date()
            
            # Generate daily ticks for the full 7-day window, excluding the last day
            date_range = pd.date_range(start=window_start_date, end=window_end_date, freq='D')[:-1]  # 7 days -> 6 ticks
            for date in date_range:
                if pd.notna(date):
                    tick_vals.append(date)
                    tick_texts.append(date.strftime('%a %m/%d'))
        
        elif zoom_level == "Month":
            # Weekly ticks for full month window  
            window_start_date = window_start.date()
            window_end_date = window_end.date()
            start_monday = window_start_date - pd.Timedelta(days=window_start_date.weekday())
            current_date = start_monday
            while current_date <= window_end_date:
                if pd.notna(current_date):
                    week_num = current_date.isocalendar()[1]
                    year = current_date.year
                    month_day = current_date.strftime('%b %d')
                    
                    tick_vals.append(current_date)
                    tick_texts.append(f"wk {week_num:02d}({year % 100})<br>{month_day}")
                current_date += pd.Timedelta(weeks=1)
            
        elif zoom_level == "Quarter":
            # Bi-weekly ticks for full quarter window
            window_start_date = window_start.date()
            window_end_date = window_end.date()
            start_monday = window_start_date - pd.Timedelta(days=window_start_date.weekday())
            current_date = start_monday
            while current_date <= window_end_date:
                if pd.notna(current_date):
                    week_num = current_date.isocalendar()[1]
                    year = current_date.year
                    month_day = current_date.strftime('%b %d')
                    
                    tick_vals.append(current_date)
                    tick_texts.append(f"wk {week_num:02d}({year % 100})<br>{month_day}")
                current_date += pd.Timedelta(weeks=2)  # Every 2 weeks for less clutter
        
        elif zoom_level == "Year":
            # Monthly ticks for full year window
            window_start_date = window_start.date()
            window_end_date = window_end.date()
            start_month = pd.Timestamp(window_start_date.replace(day=1))
            end_month = pd.Timestamp(window_end_date.replace(day=1))
            date_range = pd.date_range(start=start_month, end=end_month, freq='MS')
            for date in date_range:
                if pd.notna(date):
                    tick_vals.append(date)
                    tick_texts.append(date.strftime('%b %Y'))
        
        # Update x-axis with appropriate formatting
        if tick_vals:
            # Final validation - remove any NaN/NaT values
            valid_ticks = []
            valid_texts = []
            for i, tick_val in enumerate(tick_vals):
                if pd.notna(tick_val) and not pd.isna(tick_val):
                    valid_ticks.append(tick_val)
                    valid_texts.append(tick_texts[i])
            
            if valid_ticks:
                # Configure x-axis for all subplots (no title)
                fig.update_xaxes(
                    tickmode='array',
                    tickvals=valid_ticks,
                    ticktext=valid_texts,
                    tickfont=dict(size=11, color="black"),
                    showgrid=True,
                    gridwidth=1,
                    gridcolor='rgba(128,128,128,0.2)'
                )
                
                # Add title only to the bottom subplot
                bottom_row = len(measurement_swimlanes)
                fig.update_xaxes(
                    title="Date",
                    row=bottom_row, col=1
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

# Simple auto-refresh mechanism
# Initialize refresh counter
if 'refresh_counter' not in st.session_state:
    st.session_state.refresh_counter = 0

# Increment counter and rerun periodically
st.session_state.refresh_counter += 1
if st.session_state.refresh_counter % 5 == 0:  # Every 5th run (about 10-15 seconds)
    time.sleep(2)

# Always rerun to keep the refresh cycle going
time.sleep(3)  # 3 second intervals
st.rerun()
