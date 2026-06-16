# IoT Smart Home

Smart-house system (3 Raspberry Pi devices: door/security, kitchen/hall, bedroom/living).
Sensors and actuators publish over MQTT to a Flask server that stores data in InfluxDB and
visualizes it in Grafana. A web dashboard sends commands back to the devices over MQTT.

```
PI app (sensors/actuators) --MQTT--> mosquitto --> Flask server --> InfluxDB --> Grafana
Web dashboard --MQTT command--> mosquitto --> PI app (command listener)
```

## Run the full system in Docker (any Linux machine)

The whole stack (broker, InfluxDB, Grafana, Flask server, and a headless PI app with all
devices simulated) runs from a single compose file:

```bash
docker compose up --build
```

Then verify:

- Server health: <http://localhost:5001/health> -> `mqtt_connected` and `influxdb_connected` must be `true`
- Web dashboard: <http://localhost:5001/dashboard> (alarm / timer / BRGB / DL controls + notifications)
- Grafana: <http://localhost:3000> (admin / admin)

The headless app logs sensor activity to stdout:

```bash
docker compose logs -f app
```

### Reproduce the "Pi sends nothing" bug

On a real Raspberry Pi the broker/server live on another machine, so `broker_host: "localhost"`
(the default in `settings.json`) means the device talks to itself and nothing is published.
Reproduce it by pointing the app at the wrong host:

```bash
# Edit the app service env in docker-compose.yml: MQTT_BROKER_HOST=localhost
docker compose up --build app
# -> no data reaches the server; /health shows no sensor writes
```

### Run on a real Raspberry Pi

Use the same code; just point the device at the server over the LAN (no code edits needed):

```bash
export MQTT_BROKER_HOST=<server-ip>      # e.g. 192.168.1.10
export INFLUXDB_URL=http://<server-ip>:8086
python src/main.py            # interactive TUI
# or
python src/main.py --headless # stdout logging, for SSH / services
```

Set `simulated: true/false` per device in the settings file to mix real hardware with
simulated devices.

## Local (non-Docker) usage

```bash
pip install -r requirements.txt
docker compose up -d mosquitto influxdb grafana   # infra only
python src/server.py                              # Flask server on :5001
python src/main.py                                # TUI app
```

See [commands.md](commands.md) for the in-TUI command reference.

## Tests

```bash
pip install -r requirements-dev.txt

# Unit tests (no broker needed)
pytest tests/unit -v

# Integration tests (need a broker on localhost:1883)
docker compose up -d mosquitto
pytest tests/integration -v
```

## Configuration

- `settings.json` - local/Pi configuration (per-device `simulated` flag, MQTT, InfluxDB).
- `docker/settings.docker.json` - Docker configuration (all devices simulated, `broker_host: mosquitto`).
- Environment overrides (apply to any settings file): `MQTT_BROKER_HOST`, `MQTT_BROKER_PORT`,
  `INFLUXDB_URL`, `INFLUXDB_TOKEN`, `INFLUXDB_ORG`, `INFLUXDB_BUCKET`, `SETTINGS_PATH`, `HEADLESS`.
