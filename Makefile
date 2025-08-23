.PHONY: broker broker-ws stop pub dash health-check mqtt-status

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

dash:
	MQTT_HOST=localhost MQTT_PORT=1883 MQTT_TOPIC="lab/#" uv run streamlit run dashboard/app.py --server.port 8501

health-check:
	uv run python scripts/mqtt_health_check.py

mqtt-status:
	uv run python scripts/check_mqtt_status.py
