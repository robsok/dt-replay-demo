#!/usr/bin/env python3
"""
Query March 2025 data from InfluxDB
"""

from influxdb_client import InfluxDBClient

# Configuration
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "dt-lab-token-2025-secure-key-for-api-access"
INFLUXDB_ORG = "lab"
INFLUXDB_BUCKET = "measurements"

def main():
    print("🔍 Querying March 2025 data from InfluxDB...")
    
    try:
        client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        query_api = client.query_api()
        
        # Query for March 2025 data
        count_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: 2025-03-01T00:00:00Z, stop: 2025-03-31T23:59:59Z)
        |> count()
        '''
        
        print("📊 March 2025 record counts:")
        result = query_api.query(count_query)
        total_records = 0
        for table in result:
            for record in table.records:
                count = record.get_value()
                print(f"  {record.get_measurement()}: {count} records")
                total_records += count
        
        print(f"\n📈 Total records in March 2025: {total_records}")
        
        # Get sample data from March 2025
        sample_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: 2025-03-01T00:00:00Z, stop: 2025-03-31T23:59:59Z)
        |> limit(n: 10)
        '''
        
        print("\n📋 Sample March 2025 records:")
        result = query_api.query(sample_query)
        for table in result:
            for record in table.records:
                timestamp = record.get_time().strftime('%Y-%m-%d %H:%M:%S')
                measurement = record.get_measurement()
                field = record.get_field()
                value = record.get_value()
                print(f"  {timestamp} | {measurement} | {field}: {value}")
                
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()