# dt-replay-demo

Event-replay lab for asynchronous station streams → MQTT → twin/dashboard.

## Quickstart

```bash
# 1) create venv at repo root
uv venv
uv pip install -r replay/requirements.txt

# 2) run a local MQTT broker (choose one)
# A) Mosquitto foreground:
mosquitto -v -c ./mosquitto.conf
# or B) Docker:
# docker run --rm -p 1883:1883 -v "$PWD/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro" eclipse-mosquitto:2

# 3) configure streams
# edit config/streams.yaml (example includes lab/weights & lab/photos)

# 4) replay
uv run python -m replay.run -c config/streams.yaml

# 5) watch events
mosquitto_sub -t 'lab/#' -v

