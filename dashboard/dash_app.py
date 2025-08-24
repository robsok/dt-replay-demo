#!/usr/bin/env python3
"""
Plotly Dash version of the Lab Digital Twin Dashboard
Replicates Streamlit timeline functionality with better real-time performance.
"""

import os
import json
import time
from datetime import datetime, timedelta

import dash
from dash import dcc, html, Input, Output, callback
from dash.dependencies import State
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import yaml
from influxdb_client import InfluxDBClient

# Configuration  
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "lab/#")

# InfluxDB Configuration (as per architecture)
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "dt-lab-token-2025-secure-key-for-api-access")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "lab")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "measurements")

# Initialize InfluxDB client
def get_influxdb_client():
    return InfluxDBClient(
        url=INFLUXDB_URL,
        token=INFLUXDB_TOKEN,
        org=INFLUXDB_ORG
    )

# Load swimlane configuration
def load_swimlane_config():
    try:
        with open('/home/rms110/dt-replay-demo/config/swimlanes.yaml', 'r') as f:
            config = yaml.safe_load(f)
            return sorted(config['swimlanes'], key=lambda x: x['order'])
    except FileNotFoundError:
        print("Swimlane configuration file not found")
        return []

# Initialize Dash app
app = dash.Dash(__name__)
app.title = "Lab Digital Twin Dashboard"

# App layout
app.layout = html.Div([
    html.H1("Lab Digital Twin — Live Events", style={'textAlign': 'center', 'color': 'white'}),
    html.P(f"Broker: {MQTT_HOST}:{MQTT_PORT} • Topic: {MQTT_TOPIC}", 
           style={'textAlign': 'center', 'color': 'gray'}),
    
    # Status indicator
    html.Div(id="status-indicator-v2", style={'textAlign': 'center', 'margin': '10px'}),
    
    # Controls
    html.Div([
        html.Div([
            html.Label("Zoom Level:", style={'color': 'white', 'marginRight': '10px'}),
            dcc.Dropdown(
                id='zoom-dropdown',
                options=[
                    {'label': 'Week', 'value': 'Week'},
                    {'label': 'Month', 'value': 'Month'},
                    {'label': 'Quarter', 'value': 'Quarter'},
                    {'label': 'Year', 'value': 'Year'}
                ],
                value='Week',
                style={'width': '150px', 'display': 'inline-block'}
            )
        ], style={'display': 'inline-block', 'marginRight': '20px'}),
        
        html.Button("← Previous", id='prev-button', n_clicks=0, 
                   style={'marginRight': '10px'}),
        html.Button("Next →", id='next-button', n_clicks=0,
                   style={'marginRight': '10px'}),
        html.Button("Jump to Latest", id='latest-button', n_clicks=0),
        
    ], style={'textAlign': 'center', 'margin': '20px'}),
    
    # Event counters
    html.Div(id="event-counters-v2", style={'margin': '20px'}),
    
    
    # Timeline graph
    dcc.Graph(id="timeline-graph-v2", style={'height': '600px'}),
    
    # Recent events table
    html.H3("Recent Events", style={'color': 'white', 'textAlign': 'center'}),
    html.Div(id="recent-events-table-v2"),
    
    # Auto-refresh interval
    dcc.Interval(
        id='interval-component',
        interval=5*1000,  # Update every 5 seconds (increased to reduce conflicts)
        n_intervals=0
    ),
    
    # Store for timeline offset
    dcc.Store(id='timeline-offset', data=0)
])

# Load data from InfluxDB
def load_data():
    try:
        client = get_influxdb_client()
        
        # Query last 7 days of data to include more timeline data
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
          |> range(start: -7d)
          |> filter(fn: (r) => r._measurement =~ /(weights|density_volume|properties|packs|photos|events)/)
        '''
        
        query_api = client.query_api()
        result = query_api.query(query=query, org=INFLUXDB_ORG)
        
        # Convert to format expected by dashboard
        rows = []
        for table in result:
            for record in table.records:
                # Get particle_id from tags or fields
                particle_id = (
                    record.values.get('particle_id') or 
                    record.values.get('particle_id', 'N/A')
                )
                
                # Convert InfluxDB record to dashboard format
                row = {
                    "topic": f"lab/{record.get_measurement()}",
                    "recv_ts": record.get_time().timestamp(),
                    "stream": record.get_measurement(),
                    "data": {
                        "particle_id": particle_id,
                        "_field": record.get_field(),
                        "_value": record.get_value(),
                        # Add other relevant fields
                        **{k: v for k, v in record.values.items() 
                           if not k.startswith('_') and k not in ['result', 'table']}
                    }
                }
                rows.append(row)
        
        client.close()
        print(f"📊 Loaded {len(rows)} records from InfluxDB")
        return rows
        
    except Exception as e:
        print(f"❌ Error loading data from InfluxDB: {e}")
        import traceback
        traceback.print_exc()
        return []

# Status indicator callback
@app.callback(
    Output('status-indicator-v2', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_status(n):
    try:
        client = get_influxdb_client()
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
          |> range(start: -2m)
          |> filter(fn: (r) => r._measurement =~ /(weights|density_volume|properties|packs|photos|events)/)
          |> count()
          |> yield(name: "count")
        '''
        
        query_api = client.query_api()
        result = query_api.query(query=query, org=INFLUXDB_ORG)
        client.close()
        
        recent_count = 0
        for table in result:
            for record in table.records:
                recent_count += record.get_value()
        
        if recent_count > 0:
            return html.Div(f"📡 InfluxDB data active ({recent_count} recent events)", 
                          style={'color': 'green'})
        else:
            return html.Div("⚠️ InfluxDB connected but no recent data", 
                          style={'color': 'orange'})
            
    except Exception as e:
        return html.Div(f"❌ InfluxDB connection error: {str(e)[:50]}", style={'color': 'red'})

# Event counters callback
@app.callback(
    Output('event-counters-v2', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_event_counters(n):
    try:
        rows = load_data()
        if not rows:
            return html.P("No data available", style={'color': 'gray', 'textAlign': 'center'})
        
        df = pd.DataFrame(rows)
        if not df.empty:
            if "topic" in df.columns:
                df["stream_type"] = df["topic"].str.replace("lab/", "")
            elif "stream" in df.columns:
                df["stream_type"] = df["stream"]
            else:
                df["stream_type"] = "unknown"
        stream_counts = df["stream_type"].value_counts().to_dict()
        
        swimlanes_config = load_swimlane_config()
        counter_divs = []
        
        for swimlane in swimlanes_config:
            swimlane_count = sum(stream_counts.get(stream, 0) for stream in swimlane['streams'])
            
            counter_div = html.Div([
                html.H4(swimlane['name'], style={'margin': '0', 'color': 'white'}),
                html.P(str(swimlane_count), style={'margin': '0', 'fontSize': '24px', 'color': swimlane['color'], 'fontWeight': 'bold'})
            ], style={
                'textAlign': 'center',
                'backgroundColor': '#2d3748',
                'padding': '15px',
                'borderRadius': '8px',
                'margin': '10px',
                'display': 'inline-block',
                'minWidth': '150px',
                'border': f'2px solid {swimlane["color"]}',
                'boxShadow': '0 4px 6px rgba(0, 0, 0, 0.3)'
            })
            counter_divs.append(counter_div)
        
        # Add total
        total_div = html.Div([
            html.H4("Total Events", style={'margin': '0', 'color': 'white'}),
            html.P(str(len(df)), style={'margin': '0', 'fontSize': '24px', 'color': '#4ECDC4'})
        ], style={
            'textAlign': 'center',
            'backgroundColor': '#2d3748',
            'padding': '10px',
            'borderRadius': '5px',
            'margin': '5px',
            'display': 'inline-block',
            'minWidth': '120px'
        })
        counter_divs.append(total_div)
        
        return html.Div(counter_divs, style={'textAlign': 'center'})
    except Exception as e:
        return html.P(f"Error loading event counters: {str(e)}", style={'color': 'red', 'textAlign': 'center'})

# Simplified timeline graph callback - remove complex inputs temporarily
@app.callback(
    Output('timeline-graph-v2', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_timeline_graph(n):
    zoom_level = 'Week'  # Fixed for now
    timeline_offset = 0   # Fixed for now
    rows = load_data()
    return update_timeline_graph_internal(rows, zoom_level, timeline_offset)

# Recent events table callback
@app.callback(
    Output('recent-events-table-v2', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_recent_events(n):
    try:
        rows = load_data()
        if not rows:
            return html.P("No recent events", style={'color': 'gray', 'textAlign': 'center'})
        
        df = pd.DataFrame(rows)
        df["recv_time"] = pd.to_datetime(df["recv_ts"], unit="s")
        if not df.empty:
            if "topic" in df.columns:
                df["stream_type"] = df["topic"].str.replace("lab/", "")
            elif "stream" in df.columns:
                df["stream_type"] = df["stream"]
            else:
                df["stream_type"] = "unknown"
        
        recent_df = df.sort_values("recv_ts", ascending=False).head(20)
        
        table_data = []
        for _, row in recent_df.iterrows():
            table_data.append(html.Tr([
                html.Td(row["recv_time"].strftime("%Y-%m-%d %H:%M:%S"), style={'color': 'white', 'padding': '5px'}),
                html.Td(row["stream_type"], style={'color': 'lightblue', 'padding': '5px'}),
                html.Td(str(row.get("data", {}).get("particle_id", "N/A"))[:20], style={'color': 'lightgray', 'padding': '5px'})
            ]))
        
        return html.Table([
            html.Thead([
                html.Tr([
                    html.Th("Time", style={'color': 'white', 'padding': '10px'}),
                    html.Th("Stream", style={'color': 'white', 'padding': '10px'}),
                    html.Th("Particle ID", style={'color': 'white', 'padding': '10px'})
                ])
            ]),
            html.Tbody(table_data)
        ], style={'width': '100%', 'border': '1px solid gray'})
    except Exception as e:
        return html.P(f"Error loading recent events: {str(e)}", style={'color': 'red', 'textAlign': 'center'})

# Internal timeline function (extracted from callback)
def update_timeline_graph_internal(rows, zoom_level, timeline_offset):
    try:
        if not rows:
            return go.Figure().add_annotation(
                text="Waiting for events...", 
                xref="paper", yref="paper", 
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=20, color="gray")
            )
        
        df = pd.DataFrame(rows)
        df["recv_time"] = pd.to_datetime(df["recv_ts"], unit="s")
        if not df.empty:
            if "topic" in df.columns:
                df["stream_type"] = df["topic"].str.replace("lab/", "")
            elif "stream" in df.columns:
                df["stream_type"] = df["stream"]
            else:
                df["stream_type"] = "unknown"
        
        # Load swimlanes configuration
        swimlanes = load_swimlane_config()
        measurement_swimlanes = [sl for sl in swimlanes if sl['name'] != 'Events']
        measurement_swimlanes = sorted(measurement_swimlanes, key=lambda x: x['order'])
        
        if not measurement_swimlanes:
            return go.Figure().add_annotation(
                text="No swimlane configuration found", 
                xref="paper", yref="paper", 
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=20, color="red")
            )
        
        # Calculate time window
        if not df.empty:
            latest_time = df['recv_time'].max()
        else:
            latest_time = pd.Timestamp.now()
        
        time_windows = {
            "Week": pd.Timedelta(weeks=1),
            "Month": pd.Timedelta(days=30), 
            "Quarter": pd.Timedelta(days=90),
            "Year": pd.Timedelta(days=365)
        }
        
        window_duration = time_windows[zoom_level]
        offset = timeline_offset or 0
        window_end = latest_time - (offset * window_duration)
        window_start = window_end - window_duration
        
        # Filter data to time window
        window_df = df[(df['recv_time'] >= window_start) & (df['recv_time'] <= window_end)].copy()
        
        # Create date range
        window_start_date = window_start.date()
        window_end_date = window_end.date()
        all_dates = pd.date_range(start=window_start_date, end=window_end_date, freq='D')
        all_dates = [d.date() for d in all_dates]
        
        if not all_dates:
            all_dates = [window_end_date]
        
        # Calculate daily event counts
        if not window_df.empty:
            window_df['date'] = pd.to_datetime(window_df['recv_time']).dt.date
            daily_counts = window_df.groupby(['date', 'stream_type']).size().reset_index(name='count')
        else:
            daily_counts = pd.DataFrame(columns=['date', 'stream_type', 'count'])
        
        # Create subplot figure
        fig = make_subplots(
            rows=len(measurement_swimlanes), 
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            subplot_titles=None
        )
        
        # Add bars for each swimlane
        for i, swimlane in enumerate(measurement_swimlanes, 1):
            swimlane_counts_by_date = {date: 0 for date in all_dates}
            
            for stream_type in swimlane['streams']:
                stream_counts = daily_counts[daily_counts['stream_type'] == stream_type]
                for _, row in stream_counts.iterrows():
                    if row['date'] in swimlane_counts_by_date:
                        swimlane_counts_by_date[row['date']] += row['count']
            
            dates = [pd.Timestamp(date) for date in all_dates]
            counts = [swimlane_counts_by_date[date] for date in all_dates]
            max_count = max(counts) if counts else 0
            
            fig.add_trace(
                go.Bar(
                    x=dates,
                    y=counts,
                    name=swimlane['name'],
                    marker_color=swimlane['color'],
                    opacity=0.8,
                    text=counts,
                    textposition="outside",
                    textfont=dict(color="white", size=9),
                    hovertemplate=f'<b>{swimlane["name"]}</b><br>Date: %{{x}}<br>Count: %{{y}}<extra></extra>',
                    showlegend=False
                ),
                row=i, col=1
            )
            
            fig.update_yaxes(
                showticklabels=False, 
                showgrid=False,
                zeroline=True,
                zerolinecolor='rgba(0,0,0,0.3)',
                range=[0, max_count * 1.2] if max_count > 0 else [0, 1],
                row=i, col=1
            )
            
            # Add swimlane background and weekend shading
            if dates and len(dates) > 0:
                hex_color = swimlane['color'].lstrip('#')
                r, g, b = tuple(int(hex_color[j:j+2], 16) for j in (0, 2, 4))
                y_max = max_count * 1.2 if max_count > 0 else 1
                
                fig.add_shape(
                    type="rect",
                    x0=dates[0], x1=dates[-1],
                    y0=0, y1=y_max,
                    xref=f"x{i}", yref=f"y{i}",
                    fillcolor=f"rgba({r},{g},{b},0.08)",
                    line=dict(color=f"rgba({r},{g},{b},0.4)", width=1),
                    layer="below",
                    row=i, col=1
                )
                
                # Weekend shading
                for date in dates:
                    if date.weekday() >= 5:
                        fig.add_shape(
                            type="rect",
                            x0=date, x1=date + pd.Timedelta(days=1),
                            y0=0, y1=y_max,
                            xref=f"x{i}", yref=f"y{i}",
                            fillcolor="rgba(128,128,128,0.15)",
                            line=dict(width=0),
                            layer="below",
                            row=i, col=1
                        )
            
            # Add right-side label
            fig.add_annotation(
                text=swimlane['name'],
                x=1.02,
                y=(len(measurement_swimlanes) - i + 0.5) / len(measurement_swimlanes),
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=10, color=swimlane['color']),
                xanchor="left",
                yanchor="middle"
            )
        
        # Configure x-axis
        if dates and len(dates) > 0:
            if zoom_level == "Week":
                fig.update_xaxes(
                    tickmode='array',
                    tickvals=dates,
                    ticktext=[date.strftime('%a %m/%d') for date in dates],
                    tickfont=dict(size=11),
                    showgrid=True,
                    gridwidth=1,
                    gridcolor='rgba(128,128,128,0.2)'
                )
        
        fig.update_layout(
            height=80 * len(measurement_swimlanes) + 100,
            showlegend=False,
            title=f"{zoom_level} view: {window_start.strftime('%b %d')} to {window_end.strftime('%b %d, %Y')} | {len(window_df)} events",
            title_x=0.5,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            margin=dict(l=50, r=120, t=100, b=50)
        )
        
        return fig
        
    except Exception as e:
        print(f"❌ Error in timeline graph: {e}")
        return go.Figure().add_annotation(
            text=f"Error: {str(e)}", 
            xref="paper", yref="paper", 
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="red")
        )

# Simplified timeline offset management - removed to isolate issue
# @app.callback(
#     Output('timeline-offset', 'data'),
#     [Input('prev-button', 'n_clicks'),
#      Input('next-button', 'n_clicks'), 
#      Input('latest-button', 'n_clicks')],
#     [State('timeline-offset', 'data')],
#     prevent_initial_call=True
# )
# def update_timeline_offset(prev_clicks, next_clicks, latest_clicks, current_offset):
#     return 0  # Always return 0 for now


# Set dark theme
app.layout.style = {'backgroundColor': '#1a202c', 'minHeight': '100vh', 'padding': '20px'}

if __name__ == '__main__':
    print("🚀 Starting Dash Lab Digital Twin Dashboard")
    print(f"📡 MQTT: {MQTT_HOST}:{MQTT_PORT} (topic: {MQTT_TOPIC})")
    print("🌐 Dashboard: http://localhost:8050")
    
    # Run the app
    app.run(debug=False, host='0.0.0.0', port=8050)