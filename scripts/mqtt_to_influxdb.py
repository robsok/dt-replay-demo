#!/usr/bin/env python3
"""
MQTT to InfluxDB Data Pipeline
Subscribes to MQTT topics and writes data to InfluxDB with proper schema.
"""

import os
import sys
import json
import time
import logging
import signal
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional

import paho.mqtt.client as mqtt
import dateutil.parser
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# Configuration
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "lab/#")

INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "dt-lab-token-2025-secure-key-for-api-access")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "lab")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "measurements")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MQTTInfluxDBPipeline:
    def __init__(self):
        self.running = True
        self.mqtt_client = None
        self.influx_client = None
        self.write_api = None
        self.message_count = 0
        self.error_count = 0
        
    def setup_influxdb(self):
        """Initialize InfluxDB client and write API"""
        try:
            self.influx_client = InfluxDBClient(
                url=INFLUXDB_URL,
                token=INFLUXDB_TOKEN,
                org=INFLUXDB_ORG
            )
            self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
            logger.info(f"✅ InfluxDB client connected to {INFLUXDB_URL}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to InfluxDB: {e}")
            return False
    
    def extract_tags_from_topic(self, topic: str) -> Dict[str, str]:
        """Extract measurement type and other tags from MQTT topic"""
        # Topic format: lab/{measurement_type}
        parts = topic.split('/')
        tags = {}
        
        if len(parts) >= 2:
            tags['measurement_type'] = parts[1]
        
        return tags
    
    def extract_tags_from_payload(self, payload: Dict[str, Any]) -> Dict[str, str]:
        """Extract tags from message payload"""
        tags = {}
        
        # Extract common tag fields
        tag_fields = ['project_id', 'instrument_id', 'particle_id', 'tube_id', 'operator']
        
        for field in tag_fields:
            if field in payload:
                # Convert to string for InfluxDB tags
                tags[field] = str(payload[field])
        
        return tags
    
    def create_influx_point(self, topic: str, payload: Dict[str, Any]) -> Optional[Point]:
        """Create InfluxDB Point from MQTT message"""
        try:
            # Extract measurement name from topic
            topic_parts = topic.split('/')
            measurement = topic_parts[1] if len(topic_parts) >= 2 else 'unknown'
            
            # Create point
            point = Point(measurement)
            
            # Add tags from topic
            topic_tags = self.extract_tags_from_topic(topic)
            for key, value in topic_tags.items():
                point = point.tag(key, value)
            
            # Add tags from payload
            payload_tags = self.extract_tags_from_payload(payload)
            for key, value in payload_tags.items():
                point = point.tag(key, value)
            
            # Handle timestamp
            timestamp = None
            if 'ts' in payload:
                try:
                    timestamp = dateutil.parser.parse(payload['ts'])
                except Exception as e:
                    logger.warning(f"Failed to parse timestamp {payload['ts']}: {e}")
            
            if timestamp:
                point = point.time(timestamp)
            
            # Add fields from payload data
            if 'data' in payload:
                data = payload['data']
                if isinstance(data, dict):
                    for key, value in data.items():
                        if key not in ['ts', 'timestamp']:  # Skip timestamp fields
                            # Determine field type
                            if isinstance(value, (int, float)):
                                point = point.field(key, float(value))
                            elif isinstance(value, bool):
                                point = point.field(key, value)
                            else:
                                point = point.field(key, str(value))
                else:
                    # If data is not a dict, store as a single field
                    point = point.field('value', str(data))
            
            # Special handling for events
            if measurement == 'events':
                # Store event text and severity as fields
                if 'data' in payload:
                    event_data = payload['data']
                    if isinstance(event_data, dict):
                        for field in ['text', 'severity']:
                            if field in event_data:
                                point = point.field(field, str(event_data[field]))
                    point = point.field('event_count', 1)  # For counting events
            
            # Add raw payload as JSON field for debugging
            point = point.field('raw_payload', json.dumps(payload))
            
            return point
            
        except Exception as e:
            logger.error(f"Failed to create InfluxDB point: {e}")
            return None
    
    def write_to_influxdb(self, point: Point):
        """Write point to InfluxDB"""
        try:
            self.write_api.write(bucket=INFLUXDB_BUCKET, record=point)
            self.message_count += 1
            
            if self.message_count % 100 == 0:
                logger.info(f"📊 Processed {self.message_count} messages")
                
        except Exception as e:
            self.error_count += 1
            logger.error(f"Failed to write to InfluxDB: {e}")
    
    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        """MQTT connection callback"""
        if reason_code == 0:
            client.subscribe(MQTT_TOPIC)
            logger.info(f"✅ MQTT connected, subscribed to {MQTT_TOPIC}")
        else:
            logger.error(f"❌ MQTT connection failed: {reason_code}")
    
    def on_message(self, client, userdata, msg):
        """MQTT message callback"""
        try:
            # Parse JSON payload
            payload = json.loads(msg.payload.decode('utf-8'))
            
            # Create InfluxDB point
            point = self.create_influx_point(msg.topic, payload)
            
            if point:
                # Write to InfluxDB
                self.write_to_influxdb(point)
                
                # Log sample messages for debugging
                if self.message_count % 50 == 0:
                    logger.info(f"📨 Sample: {msg.topic} -> {point._name}")
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from {msg.topic}: {e}")
            self.error_count += 1
        except Exception as e:
            logger.error(f"Error processing message from {msg.topic}: {e}")
            self.error_count += 1
    
    def on_disconnect(self, client, userdata, reason_code, properties=None):
        """MQTT disconnect callback"""
        logger.warning(f"🔌 MQTT disconnected: {reason_code}")
    
    def setup_mqtt(self):
        """Initialize MQTT client"""
        try:
            self.mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.on_message = self.on_message
            self.mqtt_client.on_disconnect = self.on_disconnect
            
            logger.info(f"🚀 Connecting to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
            self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to setup MQTT client: {e}")
            return False
    
    def run(self):
        """Main pipeline loop"""
        logger.info("🚀 Starting MQTT to InfluxDB pipeline")
        
        # Setup InfluxDB connection
        if not self.setup_influxdb():
            logger.error("Failed to setup InfluxDB, exiting")
            return False
        
        # Setup MQTT connection
        if not self.setup_mqtt():
            logger.error("Failed to setup MQTT, exiting")
            return False
        
        # Start MQTT loop
        self.mqtt_client.loop_start()
        
        # Status reporting thread
        def status_reporter():
            while self.running:
                time.sleep(30)  # Report every 30 seconds
                if self.running:
                    logger.info(f"📊 Status: {self.message_count} messages processed, {self.error_count} errors")
        
        status_thread = threading.Thread(target=status_reporter, daemon=True)
        status_thread.start()
        
        try:
            # Keep running until interrupted
            while self.running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("🛑 Pipeline stopped by user")
        finally:
            self.cleanup()
        
        return True
    
    def cleanup(self):
        """Clean up resources"""
        logger.info("🧹 Cleaning up resources")
        self.running = False
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        if self.write_api:
            self.write_api.close()
        
        if self.influx_client:
            self.influx_client.close()
        
        logger.info(f"📊 Final stats: {self.message_count} messages processed, {self.error_count} errors")
    
    def stop(self):
        """Stop the pipeline"""
        self.running = False

# Global pipeline instance for signal handling
pipeline = None

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    if pipeline:
        pipeline.stop()
    sys.exit(0)

if __name__ == "__main__":
    # Setup signal handlers
    pipeline = MQTTInfluxDBPipeline()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the pipeline
    try:
        success = pipeline.run()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)