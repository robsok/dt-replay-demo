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

# Load projects configuration
def load_projects_config():
    try:
        with open('/home/rms110/dt-replay-demo/config/projects.yaml', 'r') as f:
            config = yaml.safe_load(f)
            return config['projects']
    except FileNotFoundError:
        print("Projects configuration file not found")
        return []

# Load data from InfluxDB for all projects
def load_data(project_id=None):
    try:
        return load_data_from_influxdb(project_id)
    except Exception as e:
        print(f"❌ Error loading data for project {project_id}: {e}")
        return []

# Load data from InfluxDB (original method)
def load_data_from_influxdb(project_id=None):
    try:
        client = get_influxdb_client()
        
        # Temporarily disable project filtering to debug InfluxDB structure
        project_filter = ""
        print(f"🔍 Debug: Loading data for project {project_id} without filtering")
        
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
          |> range(start: -365d)
          |> filter(fn: (r) => r._measurement =~ /(weights|density_volume|properties|packs|photos|events)/)
          {project_filter}
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        
        query_api = client.query_api()
        result = query_api.query(query=query, org=INFLUXDB_ORG)
        
        rows = []
        seen_records = set()  # To deduplicate based on measurement + timestamp + entity
        
        for table in result:
            for record in table.records:
                # Create unique key for deduplication
                sample_id = (
                    record.values.get('particle_id') or 
                    record.values.get('particle_id', 'N/A')
                )
                
                # Debug: Show sample IDs to understand the filtering
                if len(rows) < 3:  # Only show first few for debugging
                    print(f"🔍 Sample ID found: '{sample_id}' for project filter: {project_id}")
                
                # Apply client-side filtering if project specified and server-side filter didn't work
                if project_id:
                    if project_id == "RM43971":
                        # For RM43971/WEx1, only include RT-XRM43971 samples
                        if not (sample_id and sample_id.startswith('RT-XRM43971')):
                            continue
                    else:
                        # For other projects, only include samples starting with project_id
                        if not (sample_id and sample_id.startswith(project_id)):
                            continue
                
                # Use measurement + timestamp + sample_id as unique key
                unique_key = f"{record.get_measurement()}_{record.get_time()}_{sample_id}"
                
                if unique_key not in seen_records:
                    seen_records.add(unique_key)
                    
                    # After pivot, all fields are available as separate columns
                    data_dict = {
                        "particle_id": sample_id,  # Keep as particle_id for now to avoid breaking existing code
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
        print(f"📊 Loaded {len(rows)} records from InfluxDB for project {project_id}")
        
        # If no data found and it's not the main project, show helpful message
        if len(rows) == 0 and project_id != "RM43971":
            print(f"ℹ️  No data found for {project_id}. Run 'make pub' to ingest multi-project CSV data.")
        
        return rows
        
    except Exception as e:
        print(f"❌ Error loading data from InfluxDB: {e}")
        return []


# Initialize Dash app with different name
app = dash.Dash(__name__, title="Lab Digital Twin Dashboard Clean")

# CSS will be automatically loaded from assets/ folder

# Clean layout with project tabs
app.layout = html.Div([
    # Header section with improved styling
    html.Div([
        html.H1("Lab Digital Twin — Multi-Project Dashboard", className="dashboard-title"),
        html.P(f"Broker: {MQTT_HOST}:{MQTT_PORT} • Topic: {MQTT_TOPIC}", className="dashboard-subtitle")
    ], className="dashboard-header"),
    
    # Project navigation tabs
    html.Div([
        dcc.Tabs(
            id="project-tabs",
            value=None,
            children=[],  # Will be populated by callback
            className="tab-content",
            parent_className="tab-parent",
            colors={
                "border": "#4a5568",
                "primary": "#4ECDC4",
                "background": "#2d3748"
            }
        )
    ], className="tab-container"),
    
    # Auto-refresh interval
    dcc.Interval(
        id='refresh',
        interval=5*1000,
        n_intervals=0
    ),
    
], id="app-container")

# Project tabs population callback (only run once on startup)
@app.callback(
    Output('project-tabs', 'children'),
    Output('project-tabs', 'value'),
    Input('refresh', 'n_intervals'),
    prevent_initial_call=False
)
def update_project_tabs(n):
    # Only run on first load (n_intervals = 0) to avoid resetting tabs
    if n > 0:
        return dash.no_update, dash.no_update
        
    projects = load_projects_config()
    if not projects:
        return [], None
    
    tabs = []
    for project in projects:
        # Use project name for tab label (professional, no icons)
        tab_label = project['name']
        
        # Create tab content with project info AND full dashboard
        tab_content = html.Div([
            # Compact project info header
            html.Div([
                html.Div([
                    html.Span(f"Project Lead: {project['project_lead']}", style={'color': 'lightgray', 'marginRight': '15px', 'fontSize': '12px'}),
                    html.Span(f"Location: {project['location']}", style={'color': 'lightgray', 'marginRight': '15px', 'fontSize': '12px'}),
                    html.Span("Status: ", style={'color': 'white', 'fontSize': '12px'}),
                    html.Span(project['status'].upper(), className=f"status-{'active' if project['status'] == 'active' else 'warning'}", style={'fontSize': '12px'}),
                ], style={'margin': '5px'}),
                html.P(project['description'], style={'color': 'lightblue', 'fontStyle': 'italic', 'margin': '5px', 'fontSize': '11px'})
            ], className="project-info"),
            
            # Full dashboard for this specific project
            html.Div([
                # Status indicator
                html.Div(id=f"status-{project['id']}", style={'textAlign': 'center', 'margin': '10px'}),
                
                # Controls
                html.Div([
                    html.Div([
                        html.Label("Zoom Level:", style={'color': 'white', 'marginRight': '10px', 'display': 'block', 'marginBottom': '5px'}),
                        dcc.Dropdown(
                            id=f"zoom-dropdown-{project['id']}",
                            options=[
                                {'label': 'Week', 'value': 'Week'},
                                {'label': 'Month', 'value': 'Month'},
                                {'label': 'Quarter', 'value': 'Quarter'},
                                {'label': 'Year', 'value': 'Year'}
                            ],
                            value='Week',
                            className='dash-dropdown',
                            style={'width': '150px', 'minHeight': '38px'}
                        )
                    ], style={'display': 'inline-block', 'marginRight': '20px', 'verticalAlign': 'top'}),
                    
                    html.Div([
                        dcc.Checklist(
                            id=f"time-reference-{project['id']}",
                            options=[{'label': ' Use Current Time (vs Last Event Time)', 'value': 'current'}],
                            value=[],
                            style={'color': 'white'}
                        )
                    ], style={'display': 'inline-block', 'marginRight': '20px'}),
                    
                    html.Button("← Previous", id=f"prev-button-{project['id']}", n_clicks=0, className="nav-button"),
                    html.Button("Next →", id=f"next-button-{project['id']}", n_clicks=0, className="nav-button"),
                    html.Button("Jump to Latest", id=f"latest-button-{project['id']}", n_clicks=0, className="nav-button"),
                    
                ], className="controls-panel"),
                
                # Event counters
                html.Div(id=f"counters-{project['id']}", style={'margin': '20px'}),
                
                # Timeline graph
                html.Div([
                    dcc.Graph(id=f"timeline-{project['id']}")
                ], className="timeline-container"),
                
                # Recent events table
                html.H3("Recent Events", className="section-title"),
                html.Div(id=f"events-{project['id']}"),
                
                # Timeline offset store for this project
                dcc.Store(id=f"timeline-offset-{project['id']}", data=0)
            ])
        ])
        
        tab = dcc.Tab(
            label=tab_label,
            value=project['id'],
            children=tab_content,
            style={
                'backgroundColor': '#2d3748', 
                'color': 'white', 
                'border': '1px solid #4ECDC4',
                'fontSize': '12px',
                'padding': '8px 12px',
                'fontFamily': 'Arial, sans-serif'
            },
            selected_style={
                'backgroundColor': '#4ECDC4', 
                'color': 'black', 
                'fontWeight': 'bold',
                'fontSize': '12px'
            }
        )
        tabs.append(tab)
    
    # Default to first project
    default_project = projects[0]['id'] if projects else None
    
    return tabs, default_project

# Store selected project - removed since each tab has its own components now
        
# This broken callback has been removed - each project now has its own status callback

# This broken callback has been removed - each project now has its own counters callback

# This broken callback has been removed - each project now has its own timeline offset callback

# This broken callback has been removed - each project now has its own timeline callback

# Create dynamic callbacks for each project
def create_project_callbacks():
    """Create callbacks dynamically for each project"""
    projects = load_projects_config()
    
    for project in projects:
        project_id = project['id']
        
        # Status callback for each project
        @app.callback(
            Output(f'status-{project_id}', 'children'),
            Input('refresh', 'n_intervals'),
            prevent_initial_call=True
        )
        def update_status(n, pid=project_id):
            try:
                rows = load_data(pid)
                recent_count = len([r for r in rows if r['recv_ts'] > (pd.Timestamp.now().timestamp() - 120)])
                
                if recent_count > 0:
                    return html.Div(f"📡 Project {pid} active ({recent_count} recent events)", 
                                  style={'color': 'green'})
                else:
                    return html.Div(f"⚠️ Project {pid} connected but no recent data", 
                                  style={'color': 'orange'})
                    
            except Exception as e:
                return html.Div(f"❌ Project {pid} error: {str(e)[:50]}", style={'color': 'red'})
        
        # Counters callback for each project
        @app.callback(
            Output(f'counters-{project_id}', 'children'),
            Input('refresh', 'n_intervals'),
            prevent_initial_call=True
        )
        def update_counters(n, pid=project_id):
            try:
                rows = load_data(pid)
                if not rows:
                    if pid == "RM43971":
                        return html.P("No data available", style={'color': 'gray', 'textAlign': 'center'})
                    else:
                        return html.P(f"No data for {pid}. Run 'make pub' to ingest multi-project data.", 
                                    style={'color': 'gray', 'textAlign': 'center'})
                
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
                        html.H4(swimlane['name'], className="counter-title"),
                        html.P(str(swimlane_count), className="counter-value", style={'color': swimlane['color']})
                    ], className="counter-card", style={
                        'border': f'1px solid {swimlane["color"]}',
                        'display': 'inline-block',
                        'minWidth': '75px',
                        'textAlign': 'center'
                    })
                    counter_divs.append(counter_div)
                
                # Add total
                total_div = html.Div([
                    html.H4("Total Events", className="counter-title"),
                    html.P(str(len(df)), className="counter-value", style={'color': '#4ECDC4'})
                ], className="counter-card", style={
                    'border': '1px solid #4ECDC4',
                    'display': 'inline-block',
                    'minWidth': '75px',
                    'textAlign': 'center'
                })
                counter_divs.append(total_div)
                
                return html.Div(counter_divs, style={'textAlign': 'center'})
                
            except Exception as e:
                return html.P(f"Error loading counters for {pid}: {str(e)}", 
                            style={'color': 'red', 'textAlign': 'center'})
        
        # Timeline callback for each project
        @app.callback(
            Output(f'timeline-{project_id}', 'figure'),
            [Input('refresh', 'n_intervals'),
             Input(f'zoom-dropdown-{project_id}', 'value'),
             Input(f'timeline-offset-{project_id}', 'data'),
             Input(f'time-reference-{project_id}', 'value')],
            prevent_initial_call=True
        )
        def update_timeline(n, zoom_level, timeline_offset, time_reference, pid=project_id):
            try:
                zoom_level = zoom_level or 'Week'
                timeline_offset = timeline_offset or 0
                use_current_time = 'current' in (time_reference or [])
                
                rows = load_data(pid)
                if not rows:
                    if pid == "RM43971":
                        message = "Waiting for events..."
                    else:
                        message = f"No data for {pid}. Run 'make pub' to ingest multi-project data."
                    
                    return go.Figure().add_annotation(
                        text=message, 
                        xref="paper", yref="paper", 
                        x=0.5, y=0.5, showarrow=False,
                        font=dict(size=16, color="gray")
                    )
                
                # Use the existing timeline creation logic but with project-specific data
                return update_timeline_internal(rows, zoom_level, timeline_offset, use_current_time, pid)
                
            except Exception as e:
                return go.Figure().add_annotation(
                    text=f"Error for {pid}: {str(e)}", 
                    xref="paper", yref="paper", 
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(size=16, color="red")
                )
        
        # Events callback for each project
        @app.callback(
            Output(f'events-{project_id}', 'children'),
            Input('refresh', 'n_intervals'),
            prevent_initial_call=True
        )
        def update_events(n, pid=project_id):
            try:
                rows = load_data(pid)
                if not rows:
                    if pid == "RM43971":
                        return html.P("No recent events", style={'color': 'gray', 'textAlign': 'center'})
                    else:
                        return html.P(f"No events for {pid}. Run 'make pub' to ingest multi-project data.", 
                                    style={'color': 'gray', 'textAlign': 'center'})
                
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
                            html.Th("Time"),
                            html.Th("Stream"),
                            html.Th("Content")
                        ])
                    ]),
                    html.Tbody(table_data)
                ], className="events-table", style={'width': '100%'})
                
            except Exception as e:
                return html.P(f"Error loading events for {pid}: {str(e)}", 
                            style={'color': 'red', 'textAlign': 'center'})
        
        # Timeline offset callback for navigation
        @app.callback(
            Output(f'timeline-offset-{project_id}', 'data'),
            [Input(f'prev-button-{project_id}', 'n_clicks'),
             Input(f'next-button-{project_id}', 'n_clicks'),
             Input(f'latest-button-{project_id}', 'n_clicks')],
            [State(f'timeline-offset-{project_id}', 'data')],
            prevent_initial_call=True
        )
        def update_timeline_offset(prev_clicks, next_clicks, latest_clicks, current_offset, pid=project_id):
            ctx = callback_context
            if not ctx.triggered:
                return current_offset or 0
            
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            if button_id == f'prev-button-{pid}':
                return (current_offset or 0) + 1
            elif button_id == f'next-button-{pid}':
                return max(0, (current_offset or 0) - 1)
            elif button_id == f'latest-button-{pid}':
                return 0
            
            return current_offset or 0

# Helper function to get public holidays for a given year
def get_public_holidays(year):
    """
    Returns a set of public holiday dates for the given year.
    Currently configured for Australian public holidays.
    You can customize this based on your location.
    """
    from datetime import date
    
    holidays = set()
    
    # Fixed date holidays
    holidays.add(date(year, 1, 1))   # New Year's Day
    holidays.add(date(year, 1, 26))  # Australia Day
    holidays.add(date(year, 4, 25))  # ANZAC Day
    holidays.add(date(year, 12, 25)) # Christmas Day
    holidays.add(date(year, 12, 26)) # Boxing Day
    
    # Easter-based holidays (simplified calculation)
    try:
        # Simple Easter calculation (approximate)
        # For more accuracy, you could use a library like `holidays`
        import calendar
        
        # Queen's Birthday (second Monday in June in most Australian states)
        june_first = date(year, 6, 1)
        june_first_weekday = june_first.weekday()
        days_to_second_monday = (7 - june_first_weekday) % 7 + 7
        queens_birthday = date(year, 6, 1 + days_to_second_monday)
        holidays.add(queens_birthday)
        
        # Labour Day varies by state - using first Monday in March (WA)
        march_first = date(year, 3, 1)
        march_first_weekday = march_first.weekday()
        days_to_first_monday = (7 - march_first_weekday) % 7
        labour_day = date(year, 3, 1 + days_to_first_monday)
        holidays.add(labour_day)
        
    except:
        # If calculation fails, just skip the calculated holidays
        pass
    
    return holidays

# Internal timeline function (extracted from callback to reuse logic)
def update_timeline_internal(rows, zoom_level, timeline_offset, use_current_time, project_id):
    """Create timeline figure for a specific project using existing logic"""
    try:
        if not rows:
            return go.Figure().add_annotation(
                text=f"Waiting for events for project {project_id}...", 
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
        
        # Create subplot figure with error handling
        try:
            fig = make_subplots(
                rows=len(measurement_swimlanes), 
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.02,
                subplot_titles=None
            )
        except Exception as e:
            return go.Figure().add_annotation(
                text=f"Error creating timeline layout: {str(e)}", 
                xref="paper", yref="paper", 
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="red")
            )
        
        # Add bars/annotations for each swimlane (simplified version - just show bars)
        for i, swimlane in enumerate(measurement_swimlanes, 1):
            swimlane_counts_by_date = {date: 0 for date in all_dates}
            
            for stream_type in swimlane['streams']:
                stream_counts = daily_counts[daily_counts['stream_type'] == stream_type]
                for _, row in stream_counts.iterrows():
                    if row['date'] in swimlane_counts_by_date:
                        swimlane_counts_by_date[row['date']] += row['count']
            
            dates = [pd.Timestamp(date) + pd.Timedelta(hours=12) for date in all_dates]
            counts = [swimlane_counts_by_date[date] for date in all_dates]
            max_count = max(counts) if counts else 0
            
            show_text = zoom_level in ['Week', 'Month']
            text_values = None
            if show_text:
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
                    hovertemplate=f'<b>{swimlane["name"]}</b><br>Date: %{{x}}<br>Count: %{{y}}<br>Project: {project_id}<extra></extra>',
                    showlegend=False
                ),
                row=i, col=1
            )
            
            fig.update_yaxes(
                showticklabels=False, 
                showgrid=False,
                zeroline=True,
                zerolinecolor='rgba(0,0,0,0.3)',
                range=[0, max_count * 1.5] if max_count > 0 else [0, 1],
                row=i, col=1
            )
            
            # Add swimlane background and weekend/holiday shading
            if dates and len(dates) > 0:
                hex_color = swimlane['color'].lstrip('#')
                r, g, b = tuple(int(hex_color[j:j+2], 16) for j in (0, 2, 4))
                y_max = max_count * 1.5 if max_count > 0 else 1
                
                # Use original date boundaries (not shifted) for background shapes
                original_dates = [pd.Timestamp(date) for date in all_dates]
                
                # Add swimlane background
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
                    if orig_date.weekday() >= 5:  # Saturday (5) or Sunday (6)
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
                
                # Public holiday shading (Australian public holidays)
                # You can customize this list based on your location
                public_holidays = get_public_holidays(original_dates[0].year if original_dates else pd.Timestamp.now().year)
                
                for orig_date in original_dates:
                    # Check if this date is a public holiday
                    if orig_date.date() in public_holidays:
                        fig.add_shape(
                            type="rect",
                            x0=orig_date, x1=orig_date + pd.Timedelta(days=1),
                            y0=0, y1=y_max,
                            xref=f"x{i}", yref=f"y{i}",
                            fillcolor="rgba(255,215,0,0.2)",  # Gold color for holidays
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
        title = f"Project {project_id} - {zoom_level} view: {window_start.strftime('%b %d')} to {window_end.strftime('%b %d, %Y')} | {len(window_df)} events | {time_label}{offset_text}"
        
        fig.update_layout(
            height=100 * len(measurement_swimlanes) + 100,
            showlegend=False,
            title=title,
            title_x=0.5,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            margin=dict(l=50, r=120, t=100, b=50)
        )
        
        return fig
        
    except Exception as e:
        print(f"❌ Error in timeline graph for {project_id}: {e}")
        return go.Figure().add_annotation(
            text=f"Error for {project_id}: {str(e)}", 
            xref="paper", yref="paper", 
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="red")
        )

# Create all callbacks after app initialization
create_project_callbacks()

if __name__ == '__main__':
    print("🚀 Starting Clean Dash Lab Digital Twin Dashboard")
    print(f"📡 MQTT: {MQTT_HOST}:{MQTT_PORT} (topic: {MQTT_TOPIC})")
    print("🌐 Dashboard: http://localhost:8051")
    
    # Run on different port to avoid conflicts
    app.run(debug=False, host='0.0.0.0', port=8051)