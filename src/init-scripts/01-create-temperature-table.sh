#!/bin/bash

until curl -s http://localhost:8086/ping > /dev/null; do
    sleep 2
done

INFLUXDB_ORG=${INFLUXDB_ORG:-smart-home}
INFLUXDB_BUCKET=${INFLUXDB_BUCKET:-temperature-events}
INFLUXDB_TOKEN=${INFLUXDB_TOKEN:-smart-home-token}

influx write \
  --bucket "$INFLUXDB_BUCKET" \
  --org "$INFLUXDB_ORG" \
  --token "$INFLUXDB_TOKEN" \
  --precision s \
  'temperature_events,device_id=schema_init,location=test temperature=0.0'

influx delete \
  --bucket "$INFLUXDB_BUCKET" \
  --org "$INFLUXDB_ORG" \
  --token "$INFLUXDB_TOKEN" \
  --start '1970-01-01T00:00:00Z' \
  --stop '2099-12-31T23:59:59Z' \
  --predicate 'device_id="schema_init"'