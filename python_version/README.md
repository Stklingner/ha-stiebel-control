# Stiebel-Control Python

A Python implementation of the Stiebel Eltron Heat Pump control system using python-can and paho-mqtt.

This project enables monitoring and controlling Stiebel Eltron Heat Pumps via a CAN interface, with seamless integration to Home Assistant through MQTT.

## Features

- Connect to Stiebel Eltron Heat Pumps via CAN bus
- Auto-discovery in Home Assistant via MQTT
- Monitor temperature, energy consumption, and operation status
- Control operating modes and settings
- Calculated efficiency metrics (COP)
- Configurable sensor mapping and transformations

## Requirements

### Hardware
- Raspberry Pi or similar Linux-based computer
- CAN bus interface (like MCP2515 CAN transceiver)
- Physical connection to the Heat Pump CAN bus

### Software
- Python 3.7 or higher
- Required Python packages (see requirements.txt)
- CAN interface configured on the host system
- MQTT broker (can be Home Assistant's built-in broker)

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/stiebel-control-python.git
   cd stiebel-control-python
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure your CAN interface (if not already done):
   ```bash
   sudo ip link set can0 type can bitrate 20000
   sudo ip link set up can0
   ```

4. Edit the configuration files to match your setup:
   - Update MQTT broker details in `service_config.yaml`
   - Configure desired sensors and controls in `entity_config.yaml`
   - Adjust CAN bus parameters if needed

## Configuration

The system is configured through two separate files:

### Service Configuration (`service_config.yaml`)

This file defines the core service settings:
- Logging levels
- CAN bus parameters
- MQTT connection settings
- Reference to the entity configuration file

### Entity Configuration (`entity_config.yaml`) 

This file defines all entities exposed to Home Assistant:
- Sensors and their mappings to heat pump signals
- Controls for changing settings
- Transformation rules for sensor data

This separation allows for easier maintenance and reuse of entity configurations across different installations.

See the included configuration files for comprehensive examples.

## Usage

Start the application:

```bash
python -m stiebel_control.main --config service_config.yaml
```

For automatic startup, you can create a systemd service:

```bash
sudo nano /etc/systemd/system/stiebel-control.service
```

Add the following content:

```ini
[Unit]
Description=Stiebel Eltron Heat Pump Control
After=network.target

[Service]
User=your_user
WorkingDirectory=/path/to/stiebel-control-python
ExecStart=/usr/bin/python3 -m stiebel_control --config service_config.yaml
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable stiebel-control.service
sudo systemctl start stiebel-control.service
```

## Home Assistant Integration

The application automatically sets up devices and entities in Home Assistant via MQTT discovery. Once running, you should see a "Stiebel Eltron Heat Pump" device appear in Home Assistant with all configured sensors and controls.

## Creating a Dashboard

You can create a custom dashboard in Home Assistant to display your heat pump data. Here's a sample configuration:

```yaml
title: Heat Pump Dashboard
views:
  - title: Heat Pump
    cards:
      - type: vertical-stack
        cards:
          - type: gauge
            entity: sensor.outside_temperature
            name: Outside Temperature
            min: -20
            max: 40
            severity:
              green: 5
              yellow: 30
              red: 35
            
          - type: gauge
            entity: sensor.dhw_temperature
            name: DHW Temperature
            min: 0
            max: 65
            severity:
              green: 45
              yellow: 35
              red: 25
              
      - type: entities
        title: Controls
        entities:
          - entity: select.program_switch
          - entity: button.refresh_values
          - entity: button.update_time
          
      - type: history-graph
        title: Temperatures
        hours_to_show: 24
        entities:
          - entity: sensor.outside_temperature
          - entity: sensor.flow_temperature
          - entity: sensor.return_temperature
          - entity: sensor.dhw_temperature
```

## Troubleshooting

### CAN Bus Issues
- Verify your CAN interface is working:
  ```bash
  ip -details link show can0
  ```
- Test CAN communication:
  ```bash
  candump can0
  ```

### MQTT Issues
- Verify MQTT connection:
  ```bash
  mosquitto_sub -h your_mqtt_host -t 'stiebel_control/#' -v
  ```

### Application Issues
- Check the logs:
  ```bash
  journalctl -u stiebel-control.service
  ```
- Increase log level in `service_config.yaml` to DEBUG for more details

## Project Structure

- `stiebel_control/`: Main package
  - `main.py`: Application entry point
  - `can_interface.py`: CAN bus communication
  - `mqtt_interface.py`: MQTT integration
  - `elster_table.py`: Heat pump signal definitions

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the GPLv3 License - see the LICENSE file for details.

## Acknowledgments

This project is based on the original [ha-stiebel-control](https://github.com/Stklingner/ha-stiebel-control) project, with a complete rewrite to use Python libraries.

Special thanks to:
- [Bastian Stahmer](https://github.com/bullitt186) (Name Assumed!)
- [roberreiters](https://community.home-assistant.io/t/configured-my-esphome-with-mcp2515-can-bus-for-stiebel-eltron-heating-pump/366053) 
- [Jürg Müller](http://juerg5524.ch/list_data.php)
