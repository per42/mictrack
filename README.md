# Configuration tool for Mictrack MT710

Configure [Mictrack MT710](https://www.mictrack.com/downloads/user-manual/4g-gps-tracker/MT710_User_Manual_V1.0.pdf) over USB

Implements [mictrack MT710 USB Commands List](https://www.mictrack.com/downloads/Commands-list/Mictrack_MT710_Commands_List.pdf).

Wireless details sourced from [How to Config Network or Bands for Mictrack Devices](https://help.mictrack.com/articles/how-to-config-network-or-bands-for-mictrack-devices/)
and [MT710 Specifications](https://www.mictrack.com/downloads/catalog/MT710_Catalog.pdf).

It substitutes CoolTerm in the [MT710 USB Config Tool Tutorial (macOS Version)](https://help.mictrack.com/articles/mt710-usb-config-tool-tutorial-macos-version/).

## Usage

The tool executes commands according a config file that the user provides. This config file is a YAML list of commands described by a schema that the tool can generate:

```sh
mictrack write-schema mictrack-schema.yaml
```

Load this schema in your editor to assist in writing the config. For vscode it is:

```json
"yaml.schemas": {
    "./mictrack-schema.yaml": "/config/*.yaml",
    "https://json-schema.org/draft/2020-12/schema": "/mictrack-schema.yaml"
}
```

The configuration commands must be preceeded by a `START` command and followed by either `SAVE_EXIT` or `SAVE_REBOOT`. The following is an example of a geo fenced dog collar connected to swedish 800 MHz LTE cat M1 using the SIM supplied by mictrack and reporting to the Traccar demo server. It also dumps the configuration for inspection before saving and rebooting.

```yaml
- command: START
- command: WIRELESS
  technology: LTE
  lte_cat: M1
  priority: LTE_M1
- command: RADIO_BAND
  lte_m1: B20
  lte_nb1: B20
- command: ACCESS_POINT
  apn: iot.1nce.net
- command: SERVER
  host: demo.traccar.org
  port: 5030
- command: MODE
  mode: HOME
  interval: 20
- command: READ_CONF
- command: SAVE_REBOOT
```

Configure the device by running it with the user config. If the device serial port is at /dev/ttyUSB0 and the config in swedish_pet_on_traccar.yaml, run:

```sh
mictrack config /dev/ttyUSB0 swedish_pet_on_traccar.yaml
```

Inspect the printed configuration with the help of the reference on the last page of the command list document.
