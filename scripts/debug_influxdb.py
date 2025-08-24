#!/usr/bin/env python3
"""
Debug InfluxDB data with wider time ranges
"""

from influxdb_client import InfluxDBClient
from datetime import datetime, timezone

# Configuration
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "dt-lab-token-2025-secure-key-for-api-access"
INFLUXDB_ORG = "lab"
INFLUXDB_BUCKET = "measurements"

def main():
    print("🔍 Debugging InfluxDB data...")
    
    try:
        client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        query_api = client.query_api()
        
        # Try very wide time range
        queries = [
            ("Last 24 hours", "-24h"),
            ("Last 7 days", "-7d"),
            ("All time", "-30d"),
        ]
        
        for name, range_str in queries:
            print(f"\n📊 Total records ({name}):")
            count_query = f'''
            from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: {range_str})
            |> count()
            '''
            
            try:
                result = query_api.query(count_query)
                found_data = False
                for table in result:
                    for record in table.records:
                        print(f"  {record.get_measurement()}: {record.get_value()} records")
                        found_data = True
                if not found_data:
                    print(f"  No records found in {name}")
            except Exception as e:
                print(f"  Error querying {name}: {e}")
        
        # Try to get ANY data without time filters
        print(f"\n🔍 Attempting query without time range:")
        no_time_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
        |> limit(n: 3)
        '''
        
        try:
            result = query_api.query(no_time_query)
            found_data = False
            for table in result:
                for record in table.records:
                    print(f"  {record.get_time()} | {record.get_measurement()} | {record.get_field()}: {record.get_value()}")
                    found_data = True
            if not found_data:
                print("  No records found at all")
        except Exception as e:
            print(f"  Error: {e}")
            
        # Check if bucket exists and has any data
        print(f"\n🪣 Bucket information:")
        buckets_api = client.buckets_api()
        buckets = buckets_api.find_buckets()
        for bucket in buckets.buckets:
            print(f"  Bucket: {bucket.name} (ID: {bucket.id})")
            
    except Exception as e:
        print(f"❌ Connection Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()