#!/usr/bin/env python3
"""
Quick MQTT broker status checker
Reads the health status file and displays current broker status.
"""

import json
import os
import sys
from datetime import datetime, timedelta

HEALTH_FILE = "/tmp/mqtt_broker_health.json"

def read_health_status():
    """Read and display MQTT broker health status"""
    try:
        if not os.path.exists(HEALTH_FILE):
            print("❌ No health status file found. Is the health checker running?")
            print(f"   Expected file: {HEALTH_FILE}")
            return False
        
        with open(HEALTH_FILE, 'r') as f:
            status = json.load(f)
        
        # Parse last check time
        last_check = None
        if status.get('last_check'):
            last_check = datetime.fromisoformat(status['last_check'])
            time_ago = datetime.now() - last_check
        
        # Display status
        print(f"🔍 MQTT Broker Status Check")
        print(f"   Host: {status.get('broker_host', 'unknown')}")
        print(f"   Port: {status.get('broker_port', 'unknown')}")
        print(f"   Status: {'✅ UP' if status.get('is_connected') else '❌ DOWN'}")
        print(f"   Errors: {status.get('error_count', 0)}")
        
        if last_check:
            if time_ago < timedelta(minutes=2):
                print(f"   Last Check: {last_check.strftime('%H:%M:%S')} ({int(time_ago.total_seconds())}s ago)")
            else:
                print(f"   Last Check: {last_check.strftime('%H:%M:%S')} ⚠️  (stale data)")
        
        print(f"   Overall: {status.get('status', 'unknown').upper()}")
        
        return status.get('is_connected', False)
        
    except Exception as e:
        print(f"❌ Error reading health status: {e}")
        return False

if __name__ == "__main__":
    is_healthy = read_health_status()
    sys.exit(0 if is_healthy else 1)