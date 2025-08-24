.PHONY: broker stop pub health-check mqtt-status stack stack-stop pipeline continuous-live dash-app

broker:
	docker run --name mosquitto -p 1883:1883 -d eclipse-mosquitto

broker-ws:
	@[ -f mosquitto.conf ] || (echo "listener 1883\nallow_anonymous true\nlistener 9001\nprotocol websockets\nallow_anonymous true" > mosquitto.conf)
	docker run --name mosquitto -p 1883:1883 -p 9001:9001 -v "$$(pwd)/mosquitto.conf":/mosquitto/config/mosquitto.conf -d eclipse-mosquitto

stop:
	- docker stop mosquitto || true
	- docker rm mosquitto || true

pub:
	uv run python -m replay.run -c config/streams.yaml

# Legacy Streamlit dashboard (replaced by Dash)
# dash:
# 	MQTT_HOST=localhost MQTT_PORT=1883 MQTT_TOPIC="lab/#" uv run streamlit run dashboard/app.py --server.port 8501

health-check:
	uv run python scripts/mqtt_health_check.py

mqtt-status:
	uv run python scripts/check_mqtt_status.py

# New Docker Compose stack commands
stack:
	@[ -f mosquitto.conf ] || (echo "listener 1883\nallow_anonymous true\nlistener 9001\nprotocol websockets\nallow_anonymous true" > mosquitto.conf)
	docker-compose up -d

stack-stop:
	docker-compose down

pipeline:
	MQTT_HOST=localhost MQTT_PORT=1883 MQTT_TOPIC="lab/#" uv run python scripts/mqtt_to_influxdb.py

# Data publishers
continuous-live:
	uv run python replay/continuous_live_publisher.py

dash-app:
	MQTT_HOST=localhost MQTT_PORT=1883 MQTT_TOPIC="lab/#" INFLUX_URL=http://localhost:8086 uv run python dashboard/dash_app_clean.py
