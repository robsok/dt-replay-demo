#!/usr/bin/env python3
"""
Clean Plotly Dash version of the Lab Digital Twin Dashboard
Fresh start to avoid callback caching issues.
"""

import os
import json
import time
from datetime import datetime, timedelta

import dash
from dash import dcc, html, Input, Output, State, callback_context
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import yaml
from influxdb_client import InfluxDBClient

# Configuration  
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "lab/#")

# InfluxDB Configuration
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

# Load data from InfluxDB
def load_data():
    try:
        client = get_influxdb_client()
        
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
          |> range(start: -365d)
          |> filter(fn: (r) => r._measurement =~ /(weights|density_volume|properties|packs|photos|events)/)
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        
        query_api = client.query_api()
        result = query_api.query(query=query, org=INFLUXDB_ORG)
        
        rows = []
        seen_records = set()  # To deduplicate based on measurement + timestamp + entity
        
        for table in result:
            for record in table.records:
                # Create unique key for deduplication
                particle_id = (
                    record.values.get('particle_id') or 
                    record.values.get('particle_id', 'N/A')
                )
                
                # Use measurement + timestamp + particle_id as unique key
                unique_key = f"{record.get_measurement()}_{record.get_time()}_{particle_id}"
                
                if unique_key not in seen_records:
                    seen_records.add(unique_key)
                    
                    # After pivot, all fields are available as separate columns
                    data_dict = {
                        "particle_id": particle_id,
                        **{k: v for k, v in record.values.items() 
                           if not k.startswith('_') and k not in ['result', 'table']}
                    }
                    
                    row = {
                        "topic": f"lab/{record.get_measurement()}",
                        "recv_ts": record.get_time().timestamp(),
                        "stream": record.get_measurement(),
                        "data": data_dict
                    }
                    rows.append(row)
        
        client.close()
        print(f"📊 Loaded {len(rows)} records from InfluxDB")
        return rows
        
    except Exception as e:
        print(f"❌ Error loading data from InfluxDB: {e}")
        return []

# Initialize Dash app with different name
app = dash.Dash(__name__, title="Lab Digital Twin Dashboard Clean")

# Clean layout
app.layout = html.Div([
    html.H1("Lab Digital Twin — Live Events", style={'textAlign': 'center', 'color': 'white'}),
    html.P(f"Broker: {MQTT_HOST}:{MQTT_PORT} • Topic: {MQTT_TOPIC}", 
           style={'textAlign': 'center', 'color': 'gray'}),
    
    # Status indicator
    html.Div(id="status", style={'textAlign': 'center', 'margin': '10px'}),
    
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
        
        html.Div([
            dcc.Checklist(
                id='time-reference',
                options=[{'label': ' Use Current Time (vs Last Event Time)', 'value': 'current'}],
                value=[],  # Default to last event time
                style={'color': 'white'}
            )
        ], style={'display': 'inline-block', 'marginRight': '20px'}),
        
        html.Button("← Previous", id='prev-button', n_clicks=0, 
                   style={'marginRight': '10px'}),
        html.Button("Next →", id='next-button', n_clicks=0,
                   style={'marginRight': '10px'}),
        html.Button("Jump to Latest", id='latest-button', n_clicks=0),
        
    ], style={'textAlign': 'center', 'margin': '20px'}),
    
    # Event counters
    html.Div(id="counters", style={'margin': '20px'}),
    
    # Timeline graph (dynamic height based on swimlanes count)
    dcc.Graph(id="timeline"),
    
    # Larger spacer to prevent overlap
    html.Div(style={'height': '100px'}),
    
    # Recent events table
    html.H3("Recent Events", style={'color': 'white', 'textAlign': 'center', 'marginTop': '50px'}),
    html.Div(id="events"),
    
    # Auto-refresh interval
    dcc.Interval(
        id='refresh',
        interval=5*1000,
        n_intervals=0
    ),
    
    # Store for timeline offset
    dcc.Store(id='timeline-offset', data=0)
], style={'backgroundColor': '#1a202c', 'minHeight': '100vh', 'padding': '20px'})

# Status callback
@app.callback(
    Output('status', 'children'),
    Input('refresh', 'n_intervals')
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

# Counters callback
@app.callback(
    Output('counters', 'children'),
    Input('refresh', 'n_intervals')
)
def update_counters(n):
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

# Timeline offset management callback
@app.callback(
    Output('timeline-offset', 'data'),
    [Input('prev-button', 'n_clicks'),
     Input('next-button', 'n_clicks'), 
     Input('latest-button', 'n_clicks')],
    [State('timeline-offset', 'data')]
)
def update_timeline_offset(prev_clicks, next_clicks, latest_clicks, current_offset):
    ctx = callback_context
    if not ctx.triggered:
        return current_offset or 0
        
    try:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        if button_id == 'prev-button':
            return (current_offset or 0) - 1
        elif button_id == 'next-button':
            return (current_offset or 0) + 1
        elif button_id == 'latest-button':
            return 0
    except (IndexError, KeyError):
        pass
    
    return current_offset or 0

# Timeline callback
@app.callback(
    Output('timeline', 'figure'),
    [Input('refresh', 'n_intervals'),
     Input('zoom-dropdown', 'value'),
     Input('timeline-offset', 'data'),
     Input('time-reference', 'value')]
)
def update_timeline(n, zoom_level, timeline_offset, time_reference):
    try:
        # Set defaults
        zoom_level = zoom_level or 'Week'
        timeline_offset = timeline_offset or 0
        use_current_time = 'current' in (time_reference or [])
        
        print(f"🔄 Timeline update: zoom={zoom_level}, offset={timeline_offset}, current_time={use_current_time}")
        
        rows = load_data()
        print(f"📊 Loaded {len(rows)} rows from InfluxDB")
        
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
        
        # Load swimlanes configuration (include all swimlanes now)
        swimlanes = load_swimlane_config()
        measurement_swimlanes = sorted(swimlanes, key=lambda x: x['order'])
        
        if not measurement_swimlanes:
            return go.Figure().add_annotation(
                text="No swimlane configuration found", 
                xref="paper", yref="paper", 
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=20, color="red")
            )
        
        # Calculate time window based on zoom level and offset
        time_windows = {
            "Week": pd.Timedelta(weeks=1),
            "Month": pd.Timedelta(days=30), 
            "Quarter": pd.Timedelta(days=90),
            "Year": pd.Timedelta(days=365)
        }
        
        window_duration = time_windows[zoom_level]
        
        # Choose reference time based on checkbox
        if use_current_time:
            reference_time = pd.Timestamp.now()
            time_label = "Current Time"
        else:
            reference_time = df['recv_time'].max() if not df.empty else pd.Timestamp.now()
            time_label = "Last Event Time"
        
        # Apply offset (0 = most recent period, 1 = previous period, etc.)
        window_end = reference_time - (timeline_offset * window_duration)
        window_start = window_end - window_duration
        
        # Filter data to time window
        window_df = df[(df['recv_time'] >= window_start) & (df['recv_time'] <= window_end)].copy()
        print(f"📊 Time window: {window_start} to {window_end}")
        print(f"📊 Window data: {len(window_df)} events (from {len(df)} total)")
        
        # Create date range
        window_start_date = window_start.date()
        window_end_date = window_end.date()
        all_dates = pd.date_range(start=window_start_date, end=window_end_date, freq='D')
        all_dates = [d.date() for d in all_dates]
        
        if not all_dates:
            all_dates = [window_end_date]
            
        print(f"📊 Date range: {len(all_dates)} days from {all_dates[0] if all_dates else 'none'} to {all_dates[-1] if all_dates else 'none'}")
        
        # Limit date range for performance (prevent freeze on very large ranges)
        max_days = {
            'Week': 7,
            'Month': 31, 
            'Quarter': 92,
            'Year': 365
        }
        
        if len(all_dates) > max_days.get(zoom_level, 365):
            limit = max_days.get(zoom_level, 365)
            print(f"⚠️  Date range too large ({len(all_dates)} days), limiting {zoom_level} view to {limit} days")
            all_dates = all_dates[-limit:]
        
        # Additional safeguard for Year view to prevent freezing
        if zoom_level == 'Year' and len(all_dates) > 300:
            print(f"⚠️  Year view with {len(all_dates)} days, further limiting to 300 days for performance")
            all_dates = all_dates[-300:]
        
        # Calculate daily event counts
        if not window_df.empty:
            window_df['date'] = pd.to_datetime(window_df['recv_time']).dt.date
            daily_counts = window_df.groupby(['date', 'stream_type']).size().reset_index(name='count')
        else:
            daily_counts = pd.DataFrame(columns=['date', 'stream_type', 'count'])
        
        # Create subplot figure with error handling
        print(f"📊 Creating subplots: {len(measurement_swimlanes)} swimlanes")
        try:
            fig = make_subplots(
                rows=len(measurement_swimlanes), 
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.02,
                subplot_titles=None
            )
            print(f"📊 Subplots created successfully")
        except Exception as e:
            print(f"❌ Error creating subplots: {e}")
            return go.Figure().add_annotation(
                text=f"Error creating timeline layout: {str(e)}", 
                xref="paper", yref="paper", 
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="red")
            )
        
        # Add bars/annotations for each swimlane
        for i, swimlane in enumerate(measurement_swimlanes, 1):
            # Handle Events swimlane differently - show text for Week/Month, markers for Quarter/Year
            if swimlane['name'] == 'Events':
                # Get actual event data for this swimlane
                events_data = []
                for stream_type in swimlane['streams']:
                    stream_events = window_df[window_df['stream_type'] == stream_type]
                    
                    print(f"🔍 Total {stream_type} records: {len(stream_events)}")
                    
                    # Debug: Let's see what all the fields look like
                    if not stream_events.empty:
                        for idx, row in stream_events.head(3).iterrows():  # Just first 3 for debugging
                            data_dict = row.get('data', {})
                            print(f"🔍 Sample event record: field='{data_dict.get('_field')}', value='{data_dict.get('_value')}', all_keys={list(data_dict.keys())}")
                    
                    # With pivoted data, all event fields should be available directly
                    for _, row in stream_events.iterrows():
                        data_dict = row.get('data', {})
                        
                        # Now 'text' should be a direct field in data_dict
                        event_text = (
                            data_dict.get('text') or 
                            data_dict.get('value') or
                            str(list(data_dict.items())[:3]) if data_dict else
                            'Event'
                        )
                        
                        severity = data_dict.get('severity', 'info')
                        event_time = row['recv_time']
                        
                        print(f"🔍 Pivoted event - text: '{event_text}', severity: '{severity}' at {event_time}")
                        
                        events_data.append({
                            'time': event_time,
                            'text': event_text,
                            'severity': severity
                        })
                
                # Add a minimal bar to establish the timeline
                dates = [pd.Timestamp(date) + pd.Timedelta(hours=12) for date in all_dates]
                empty_counts = [0] * len(all_dates)
                
                fig.add_trace(
                    go.Bar(
                        x=dates,
                        y=empty_counts,
                        name=swimlane['name'],
                        marker_color='rgba(0,0,0,0)',  # Invisible bars
                        showlegend=False,
                        hoverinfo='skip'
                    ),
                    row=i, col=1
                )
                
                # Show text for Week/Month views, markers for Quarter/Year views
                if zoom_level in ['Week', 'Month']:
                    # Add event text annotations with smart positioning
                    for idx, event in enumerate(events_data):
                        # Color based on severity
                        severity_colors = {
                            'info': swimlane['color'],
                            'warning': '#FFA500',
                            'error': '#FF4444',
                            'critical': '#CC0000'
                        }
                        color = severity_colors.get(event['severity'], swimlane['color'])
                        
                        # Smart text processing with line wrapping
                        max_chars_per_line = {
                            'Week': 20,    # Longer lines for detailed view
                            'Month': 15
                        }
                        char_limit = max_chars_per_line.get(zoom_level, 15)
                        
                        # Wrap text into multiple lines
                        text = event['text']
                        words = text.split()
                        lines = []
                        current_line = ""
                        
                        for word in words:
                            test_line = current_line + (" " + word if current_line else word)
                            if len(test_line) <= char_limit:
                                current_line = test_line
                            else:
                                if current_line:
                                    lines.append(current_line)
                                    current_line = word
                                else:
                                    # Word is too long, truncate it
                                    lines.append(word[:char_limit-3] + "...")
                                    break
                            
                            # Limit to 3 lines max to prevent overflow
                            if len(lines) >= 2:
                                if current_line:
                                    lines.append(current_line[:char_limit-3] + "...")
                                break
                        
                        if current_line and len(lines) < 3:
                            lines.append(current_line)
                        
                        wrapped_text = "<br>".join(lines)
                        
                        # Stagger y position but keep within bounds (0.2 to 0.8)
                        y_positions = [0.4, 0.5, 0.6]  # Closer to center to avoid cutoff
                        y_pos = y_positions[idx % len(y_positions)]
                        
                        # Larger font sizes for better readability
                        font_sizes = {
                            'Week': 11,    # Increased from 9
                            'Month': 10,   # Increased from 8  
                        }
                        font_size = font_sizes.get(zoom_level, 10)
                        
                        # Text angle: -45 degrees
                        text_angle = -45
                        
                        # Add text annotation with better anchoring to prevent bottom cutoff
                        fig.add_annotation(
                            x=event['time'],
                            y=y_pos,
                            text=wrapped_text,
                            textangle=text_angle,
                            showarrow=False,
                            font=dict(size=font_size, color=color),
                            xref=f"x{i}",
                            yref=f"y{i}",
                            xanchor="center",
                            yanchor="bottom",  # Changed from "middle" to "bottom" to prevent cutoff
                            bgcolor="rgba(0,0,0,0.1)",  # Subtle background for better readability
                            bordercolor=color,
                            borderwidth=0.5
                        )
                else:
                    # For Quarter/Year views, show hoverable markers instead of text
                    for event in events_data:
                        # Color based on severity
                        severity_colors = {
                            'info': swimlane['color'],
                            'warning': '#FFA500',
                            'error': '#FF4444',
                            'critical': '#CC0000'
                        }
                        color = severity_colors.get(event['severity'], swimlane['color'])
                        
                        # Add scatter marker with hover text
                        fig.add_trace(
                            go.Scatter(
                                x=[event['time']],
                                y=[0.5],  # Center of swimlane
                                mode='markers',
                                marker=dict(
                                    size=8,
                                    color=color,
                                    symbol='circle',
                                    line=dict(width=1, color='white')
                                ),
                                hovertemplate=f'<b>{event["text"]}</b><br>Severity: {event["severity"]}<br>Time: %{{x}}<extra></extra>',
                                showlegend=False,
                                name=""
                            ),
                            row=i, col=1
                        )
                
                max_count = 1  # Set to 1 for proper scaling
                
            else:
                # Handle regular measurement swimlanes (counts)
                swimlane_counts_by_date = {date: 0 for date in all_dates}
                
                for stream_type in swimlane['streams']:
                    stream_counts = daily_counts[daily_counts['stream_type'] == stream_type]
                    for _, row in stream_counts.iterrows():
                        if row['date'] in swimlane_counts_by_date:
                            swimlane_counts_by_date[row['date']] += row['count']
                
                # Shift dates by 12 hours to center bars over days
                dates = [pd.Timestamp(date) + pd.Timedelta(hours=12) for date in all_dates]
                counts = [swimlane_counts_by_date[date] for date in all_dates]
                max_count = max(counts) if counts else 0
                
                # Show text labels only for Week and Month views, but hide zeros
                show_text = zoom_level in ['Week', 'Month']
                text_values = None
                if show_text:
                    # Show only non-zero values
                    text_values = [str(count) if count > 0 else '' for count in counts]
                
                fig.add_trace(
                    go.Bar(
                        x=dates,
                        y=counts,
                        name=swimlane['name'],
                        marker_color=swimlane['color'],
                        opacity=0.8,
                        text=text_values,
                        textposition="outside" if show_text else None,
                        textfont=dict(color="white", size=9) if show_text else None,
                        hovertemplate=f'<b>{swimlane["name"]}</b><br>Date: %{{x}}<br>Count: %{{y}}<extra></extra>',
                        showlegend=False
                    ),
                    row=i, col=1
                )
            
            # Increase y-range to prevent text cutoff (was 1.2, now 1.5)
            fig.update_yaxes(
                showticklabels=False, 
                showgrid=False,
                zeroline=True,
                zerolinecolor='rgba(0,0,0,0.3)',
                range=[0, max_count * 1.5] if max_count > 0 else [0, 1],
                row=i, col=1
            )
            
            # Add swimlane background and weekend shading (skip background for Events)
            if dates and len(dates) > 0:
                hex_color = swimlane['color'].lstrip('#')
                r, g, b = tuple(int(hex_color[j:j+2], 16) for j in (0, 2, 4))
                y_max = max_count * 1.5 if max_count > 0 else 1  # Match the new y-range
                
                # Use original date boundaries (not shifted) for background shapes
                original_dates = [pd.Timestamp(date) for date in all_dates]
                
                # Skip background styling for Events swimlane
                if swimlane['name'] != 'Events':
                    fig.add_shape(
                        type="rect",
                        x0=original_dates[0], x1=original_dates[-1] + pd.Timedelta(days=1),
                        y0=0, y1=y_max,
                        xref=f"x{i}", yref=f"y{i}",
                        fillcolor=f"rgba({r},{g},{b},0.08)",
                        line=dict(color=f"rgba({r},{g},{b},0.4)", width=1),
                        layer="below",
                        row=i, col=1
                    )
                
                # Weekend shading using original dates
                for orig_date in original_dates:
                    if orig_date.weekday() >= 5:  # Saturday or Sunday
                        fig.add_shape(
                            type="rect",
                            x0=orig_date, x1=orig_date + pd.Timedelta(days=1),
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
        
        # Configure x-axis formatting based on zoom level
        if dates and len(dates) > 0:
            # Use original dates for tick marks (day boundaries)
            original_dates = [pd.Timestamp(date) for date in all_dates]
            
            if zoom_level == "Week":
                fig.update_xaxes(
                    tickmode='array',
                    tickvals=original_dates,
                    ticktext=[date.strftime('%a %m/%d') for date in original_dates],
                    tickfont=dict(size=11),
                    showgrid=True,
                    gridwidth=1,
                    gridcolor='rgba(128,128,128,0.2)'
                )
            elif zoom_level == "Month":
                # Sample original dates for less crowded display
                sample_dates = original_dates[::3] if len(original_dates) > 10 else original_dates
                tick_texts = []
                for date in sample_dates:
                    week_num = date.isocalendar()[1]
                    year_short = date.strftime('%y')
                    month_day = date.strftime('%b %d')
                    tick_texts.append(f"wk {week_num} ('{year_short})<br>{month_day}")
                
                fig.update_xaxes(
                    tickmode='array',
                    tickvals=sample_dates,
                    ticktext=tick_texts,
                    tickfont=dict(size=9),
                    showgrid=True,
                    gridwidth=1,
                    gridcolor='rgba(128,128,128,0.2)'
                )
            elif zoom_level == "Quarter":
                # Show starting weeks of each month only
                month_start_dates = []
                month_start_texts = []
                
                # Group dates by month and find the first date of each month
                seen_months = set()
                for date in original_dates:
                    month_key = (date.year, date.month)
                    if month_key not in seen_months:
                        seen_months.add(month_key)
                        # Find the first Monday or first day of this month in our data
                        month_dates = [d for d in original_dates if d.year == date.year and d.month == date.month]
                        if month_dates:
                            # Use the first date of the month in our dataset
                            first_date = min(month_dates)
                            month_start_dates.append(first_date)
                            month_start_texts.append(first_date.strftime('%b %Y'))
                
                # If no month starts found, fall back to sampling every 2 weeks
                if not month_start_dates:
                    month_start_dates = original_dates[::14] if len(original_dates) > 14 else original_dates
                    month_start_texts = [d.strftime('%b %Y') for d in month_start_dates]
                
                fig.update_xaxes(
                    tickmode='array',
                    tickvals=month_start_dates,
                    ticktext=month_start_texts,
                    tickfont=dict(size=9),
                    tickangle=0,  # Horizontal
                    showgrid=True,
                    gridwidth=1,
                    gridcolor='rgba(128,128,128,0.2)'
                )
            else:  # Year view
                # For year view, show major month markers (quarterly or monthly depending on data size)
                if len(original_dates) > 0:
                    # Group by month and show first date of each month
                    monthly_dates = []
                    monthly_texts = []
                    seen_months = set()
                    
                    for date in original_dates:
                        month_key = (date.year, date.month)
                        if month_key not in seen_months:
                            seen_months.add(month_key)
                            # Add first date of this month
                            month_dates = [d for d in original_dates if d.year == date.year and d.month == date.month]
                            if month_dates:
                                first_date = min(month_dates)
                                monthly_dates.append(first_date)
                                monthly_texts.append(first_date.strftime('%b %Y'))
                    
                    # If too many months, sample every 2-3 months
                    if len(monthly_dates) > 12:
                        sample_dates = monthly_dates[::3]  # Every 3rd month (quarterly)
                        tick_texts = [monthly_texts[i] for i in range(0, len(monthly_texts), 3)]
                    elif len(monthly_dates) > 6:
                        sample_dates = monthly_dates[::2]  # Every 2nd month
                        tick_texts = [monthly_texts[i] for i in range(0, len(monthly_texts), 2)]
                    else:
                        sample_dates = monthly_dates
                        tick_texts = monthly_texts
                        
                    # Fallback if no monthly data found
                    if not sample_dates:
                        sample_dates = original_dates[::max(1, len(original_dates)//10)]
                        tick_texts = [date.strftime('%b %Y') for date in sample_dates]
                else:
                    # No dates available
                    sample_dates = []
                    tick_texts = []
                
                if sample_dates and tick_texts:
                    fig.update_xaxes(
                        tickmode='array',
                        tickvals=sample_dates,
                        ticktext=tick_texts,
                        tickfont=dict(size=8),
                        showgrid=True,
                        gridwidth=1,
                        gridcolor='rgba(128,128,128,0.2)'
                    )
                else:
                    # Fallback to auto-formatting if no custom ticks
                    fig.update_xaxes(
                        tickfont=dict(size=8),
                        showgrid=True,
                        gridwidth=1,
                        gridcolor='rgba(128,128,128,0.2)'
                    )
        
        # Create title with time reference info
        offset_text = f" (offset: {timeline_offset})" if timeline_offset != 0 else ""
        title = f"{zoom_level} view: {window_start.strftime('%b %d')} to {window_end.strftime('%b %d, %Y')} | {len(window_df)} events | {time_label}{offset_text}"
        
        fig.update_layout(
            height=100 * len(measurement_swimlanes) + 100,  # Increased from 80 to 100 per swimlane
            showlegend=False,
            title=title,
            title_x=0.5,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            margin=dict(l=50, r=120, t=100, b=50)
        )
        
        print(f"✅ Timeline figure completed with {len(fig.data)} traces")
        return fig
        
    except Exception as e:
        print(f"❌ Error in timeline graph: {e}")
        return go.Figure().add_annotation(
            text=f"Error: {str(e)}", 
            xref="paper", yref="paper", 
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="red")
        )

# Events table callback
@app.callback(
    Output('events', 'children'),
    Input('refresh', 'n_intervals')
)
def update_events(n):
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
            data_dict = row.get("data", {})
            
            # Show relevant content based on stream type
            if row["stream_type"] == "events":
                # With pivoted data, text should be directly available
                content = data_dict.get('text', data_dict.get('value', 'Event'))
                content_style = {'color': '#FFA500', 'padding': '5px'}  # Orange for events
            else:
                # For measurements, show particle_id and value
                particle_id = data_dict.get("particle_id", "N/A")
                value = data_dict.get("_value", data_dict.get("value", ""))
                if value:
                    content = f"{particle_id} (value: {value})"
                else:
                    content = particle_id
                content_style = {'color': 'lightgray', 'padding': '5px'}
            
            # Truncate long content
            content = str(content)[:50] + ('...' if len(str(content)) > 50 else '')
            
            table_data.append(html.Tr([
                html.Td(row["recv_time"].strftime("%Y-%m-%d %H:%M:%S"), style={'color': 'white', 'padding': '5px'}),
                html.Td(row["stream_type"], style={'color': 'lightblue', 'padding': '5px'}),
                html.Td(content, style=content_style)
            ]))
        
        return html.Table([
            html.Thead([
                html.Tr([
                    html.Th("Time", style={'color': 'white', 'padding': '10px'}),
                    html.Th("Stream", style={'color': 'white', 'padding': '10px'}),
                    html.Th("Content", style={'color': 'white', 'padding': '10px'})  # Changed from "Particle ID"
                ])
            ]),
            html.Tbody(table_data)
        ], style={'width': '100%', 'border': '1px solid gray'})
    except Exception as e:
        return html.P(f"Error loading recent events: {str(e)}", style={'color': 'red', 'textAlign': 'center'})

if __name__ == '__main__':
    print("🚀 Starting Clean Dash Lab Digital Twin Dashboard")
    print(f"📡 MQTT: {MQTT_HOST}:{MQTT_PORT} (topic: {MQTT_TOPIC})")
    print("🌐 Dashboard: http://localhost:8051")
    
    # Run on different port to avoid conflicts
    app.run(debug=False, host='0.0.0.0', port=8051)