#!/usr/bin/env python3
"""
MQTT Broker Health Check Daemon
Continuously monitors MQTT broker connectivity and provides status.
"""

import os
import sys
import time
import logging
import signal
import paho.mqtt.client as mqtt
from datetime import datetime
import threading

# Configuration
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
CHECK_INTERVAL = 30  # seconds
HEALTH_FILE = "/tmp/mqtt_broker_health.json"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MQTTHealthChecker:
    def __init__(self):
        self.is_connected = False
        self.last_check = None
        self.error_count = 0
        self.running = True
        self.connection_successful = False
        
    def on_connect(self, client, userdata, flags, reason_code, *args):
        if reason_code == 0:
            self.connection_successful = True
            self.is_connected = True
            self.error_count = 0
            logger.info(f"✅ MQTT broker connected at {MQTT_HOST}:{MQTT_PORT}")
        else:
            self.connection_successful = False
            self.is_connected = False
            self.error_count += 1
            logger.error(f"❌ MQTT broker connection failed: {reason_code}")
    
    def on_disconnect(self, client, userdata, reason_code, *args):
        # Don't mark as failed if we successfully connected first
        if self.connection_successful:
            logger.info(f"🔌 MQTT broker disconnected (normal after health check)")
        else:
            logger.warning(f"🔌 MQTT broker disconnected: {reason_code}")
        self.is_connected = False
    
    def check_broker(self):
        """Perform a single broker connectivity check"""
        try:
            # Reset connection status for this check
            self.connection_successful = False
            self.is_connected = False
            
            client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
            client.on_connect = self.on_connect
            client.on_disconnect = self.on_disconnect
            
            # Set timeout
            client.socket_timeout = 5.0
            client.connect_timeout = 5.0
            
            # Try to connect
            client.connect(MQTT_HOST, MQTT_PORT, 10)
            client.loop_start()
            
            # Wait for connection result
            time.sleep(2)
            
            client.loop_stop()
            client.disconnect()
            
            self.last_check = datetime.now()
            
        except Exception as e:
            self.connection_successful = False
            self.is_connected = False
            self.error_count += 1
            logger.error(f"❌ MQTT broker check failed: {e}")
    
    def write_health_status(self):
        """Write health status to file for other processes to read"""
        import json
        
        status = {
            "broker_host": MQTT_HOST,
            "broker_port": MQTT_PORT,
            "is_connected": self.connection_successful,  # Use connection_successful instead
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "error_count": self.error_count,
            "status": "healthy" if self.connection_successful else "unhealthy"
        }
        
        try:
            with open(HEALTH_FILE, 'w') as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write health status: {e}")
    
    def run(self):
        """Main daemon loop"""
        logger.info(f"🚀 Starting MQTT health checker for {MQTT_HOST}:{MQTT_PORT}")
        logger.info(f"📝 Health status will be written to {HEALTH_FILE}")
        
        while self.running:
            try:
                self.check_broker()
                self.write_health_status()
                
                # Log status
                status_emoji = "✅" if self.connection_successful else "❌"
                logger.info(f"{status_emoji} Broker status: {'UP' if self.connection_successful else 'DOWN'} (errors: {self.error_count})")
                
                # Wait before next check
                time.sleep(CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("🛑 Health checker stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in health checker: {e}")
                time.sleep(CHECK_INTERVAL)
        
        logger.info("👋 MQTT health checker stopped")
    
    def stop(self):
        """Stop the daemon"""
        self.running = False

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    health_checker.stop()
    sys.exit(0)

if __name__ == "__main__":
    # Setup signal handlers
    health_checker = MQTTHealthChecker()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the health checker
    try:
        health_checker.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)