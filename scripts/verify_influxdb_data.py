#!/usr/bin/env python3
"""
Verify data in InfluxDB
"""

from influxdb_client import InfluxDBClient

# Configuration
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "dt-lab-token-2025-secure-key-for-api-access"
INFLUXDB_ORG = "lab"
INFLUXDB_BUCKET = "measurements"

def main():
    print("🔍 Checking InfluxDB data...")
    
    try:
        client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        query_api = client.query_api()
        
        # Simple count query
        count_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: -1h)
        |> count()
        '''
        
        print("\n📊 Total records in last hour:")
        result = query_api.query(count_query)
        for table in result:
            for record in table.records:
                print(f"  {record.get_measurement()}: {record.get_value()} records")
        
        # Get sample data
        sample_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: -10m)
        |> limit(n: 5)
        '''
        
        print("\n📋 Sample records (last 10 minutes):")
        result = query_api.query(sample_query)
        for table in result:
            for record in table.records:
                print(f"  {record.get_time()} | {record.get_measurement()} | {record.get_field()}: {record.get_value()}")
                
        # List measurements
        measurements_query = f'''
        import "influxdata/influxdb/schema"
        schema.measurements(bucket: "{INFLUXDB_BUCKET}")
        '''
        
        print("\n📈 Available measurements:")
        try:
            result = query_api.query(measurements_query)
            for table in result:
                for record in table.records:
                    print(f"  - {record.get_value()}")
        except Exception as e:
            print(f"  Error listing measurements: {e}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()