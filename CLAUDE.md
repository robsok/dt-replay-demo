# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development Environment
```bash
# Setup virtual environment and install dependencies
uv venv
uv pip install -r requirements.txt

# Install development dependencies (testing, linting, type checking)
uv pip install -e ".[dev]"
```

### Running the Application
```bash
# Run the replay publisher (main application)
uv run python -m replay.run -c config/streams.yaml

# Alternative using entry point
replay-run -c config/streams.yaml

# Run the dashboard (separate terminal)
cd dashboard && streamlit run app.py
```

### MQTT Broker Setup
```bash
# Option A: Local Mosquitto broker
mosquitto -v -c ./mosquitto.conf

# Option B: Docker Mosquitto
docker run --rm -p 1883:1883 -v "$PWD/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro" eclipse-mosquitto:2

# Monitor MQTT events
mosquitto_sub -t 'lab/#' -v
```

### Development Tools
```bash
# Run tests
pytest

# Linting and formatting
ruff check .
ruff format .

# Type checking
mypy .
```

## Architecture

This is an event replay system for lab digital twin demonstrations that reads CSV data and publishes events to MQTT topics in real-time.

### Core Components

**replay/** - Main replay engine package
- `config.py` - Configuration loading and dataclasses (`AppCfg`, `StreamCfg`, `BrokerCfg`)
- `scheduler.py` - Event scheduling with multi-stream time synchronization and real-time pacing
- `publisher.py` - MQTT publishing logic using aiomqtt
- `run.py` - CLI entry point and main orchestration

**dashboard/** - Streamlit-based live dashboard
- `app.py` - Real-time MQTT event viewer using paho-mqtt with threading

**config/** - Configuration files
- `streams.yaml` - Stream definitions with CSV mappings, MQTT topics, and data transformations
- `config.py` - Configuration utilities

### Data Flow
1. CSV files → scheduler loads and parses timestamps 
2. Events merged in chronological order with configurable time acceleration
3. Real-time pacing controls event emission timing
4. Events published to MQTT topics as JSON with timestamp, stream ID, and payload
5. Dashboard subscribes to MQTT and displays live events in a table

### Key Features
- Multi-stream time synchronization with heap-based merging
- Configurable time acceleration (speed parameter)
- Timezone handling and timestamp parsing flexibility
- Schema transformations (column renaming, type coercion, filtering)
- Time window filtering (start/end dates)
- Real-time dashboard with auto-refresh

### Configuration
The `config/streams.yaml` file defines:
- Global settings (speed, time windows, broker config)
- Per-stream CSV file mappings
- MQTT topic assignments  
- Data schema transformations (rename, types, filtering)
- Timezone and timestamp format specifications

### Dependencies
- **aiomqtt** - Async MQTT client for publishing
- **paho-mqtt** - MQTT client for dashboard subscription
- **pandas** - CSV data processing and time handling
- **streamlit** - Dashboard web interface
- **PyYAML** - Configuration file parsing