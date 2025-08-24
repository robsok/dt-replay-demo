#!/usr/bin/env python3
"""
Check the time range of data in InfluxDB
"""

from influxdb_client import InfluxDBClient

# Configuration
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "dt-lab-token-2025-secure-key-for-api-access"
INFLUXDB_ORG = "lab"
INFLUXDB_BUCKET = "measurements"

def main():
    print("🔍 Checking time range of data in InfluxDB...")
    
    try:
        client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        query_api = client.query_api()
        
        # Check sample timestamps and data
        sample_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: -6h)
        |> sort(columns: ["_time"], desc: false)
        |> limit(n: 5)
        '''
        
        print("📅 Earliest timestamps (sample):")
        result = query_api.query(sample_query)
        for table in result:
            for record in table.records:
                print(f"  {record.get_time()} | {record.get_measurement()}")
        
        # Check latest timestamps  
        latest_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: -6h)
        |> sort(columns: ["_time"], desc: true)
        |> limit(n: 5)
        '''
        
        print("\n📅 Latest timestamps (sample):")
        result = query_api.query(latest_query)
        for table in result:
            for record in table.records:
                print(f"  {record.get_time()} | {record.get_measurement()}")
                
        # Count recent records
        count_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: -1h)
        |> count()
        '''
        
        print("\n📊 Records in last 1 hour:")
        result = query_api.query(count_query)
        total = 0
        for table in result:
            for record in table.records:
                count = record.get_value()
                print(f"  {record.get_measurement()}: {count}")
                total += count
        print(f"  Total: {total}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()