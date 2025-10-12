# js8ToMqtt JS8Call MQTT Bridge

## Project Overview

This project is a Python-based middleware that acts as a bridge between the **JS8Call** amateur radio application and an **MQTT broker**. It provides a robust, decoupled architecture that allows multiple clients (such as a web dashboard, Home Assistant, or other automation tools) to send commands to and receive data from JS8Call in real time.

The middleware handles the low-level complexities of the JS8Call API, including message buffering, reassembly of multi-frame messages, and command rate limiting, ensuring the system remains stable and efficient.

## Features

* **Decoupled Architecture:** Separates JS8Call from client applications using MQTT, enabling multiple clients without overwhelming the API.

* **Message Reassembly:** Buffers multi-frame `RX.ACTIVITY` messages from the API and publishes them as a single, complete message.

* **Incomplete Message Handling:** Publishes a partial message to a dedicated topic if a transmission times out, preventing data loss.

* **Dynamic Topic Publishing:** Publishes different JS8Call events (e.g., frequency changes, PTT status) to distinct, organized MQTT topics.

* **Command Rate Limiting:** Uses a simple queue and a configurable delay to prevent sending commands to JS8Call too quickly.

* **Lightweight and Efficient:** Designed to run on resource-constrained hardware like a Raspberry Pi Zero.

## Architecture

The system is designed with a central MQTT broker acting as a hub.

* **JS8Call:** The source of all data and the destination for all commands.

* **Python Middleware:** Connects to JS8Call via a TCP socket and to the MQTT broker. It translates JS8Call events into MQTT messages and queues MQTT commands for transmission to JS8Call.

* **MQTT Broker:** The central nervous system of the project, where all communication is routed.

* **Client(s):** Any application (e.g., your React dashboard) that subscribes to the MQTT topics to receive data or publishes commands to control JS8Call.

## Prerequisites

To run the middleware, you need the following:

* **Python 3.8+**

* **JS8Call** running on the same network, with its API enabled.

* A running **MQTT Broker** (e.g., Mosquitto).

## Installation & Setup

### Linux/macOS Installation

1. **Clone the Repository:**
```bash
git clone https://github.com/rob-adelie/js8-mqtt-bridge.git
cd js8-mqtt-bridge
```

2. **Configure the Application:**
Edit `js8-mqtt-bridge.cfg` with your system settings:
- MQTT Broker details (host, port, username, password)
- JS8Call API settings (host, port)

3. **Run Installation Script:**
```bash
./install.sh
```

### Windows Installation

1. **Clone the Repository:**
```bash
git clone https://github.com/rob-adelie/js8-mqtt-bridge.git
cd js8-mqtt-bridge
```

2. **Configure the Application:**
Edit `js8-mqtt-bridge.cfg` with your system settings:
- MQTT Broker details (host, port, username, password)
- JS8Call API settings (host, port)

3. **Run Installation Script:**
Double-click `install.bat` or run from command prompt:
```cmd
install.bat
```

The Windows installer will:
- Create a Python virtual environment
- Install required dependencies
- Create a startup shortcut for automatic launch
- Set up logging directory

4. **Manual Testing:**
To test the installation, run:
```cmd
run.bat
```

5. **Uninstallation:**
To remove the installation, run:
```cmd
uninstall.bat
```



## Usage
### MQTT Topics

The middleware uses a dynamic topic structure to keep your data organized. All topics are prefixed with `js8/`.

* **Commands:** `js8/tx/command` - Publish JSON commands here.

* **Complete Messages:** `js8/rx/complete` - Subscribe to receive full, reassembled messages.

* **Incomplete Messages:** `js8/rx/incomplete` - Subscribe to receive timed-out messages.

* **All Other Events:** `js8/<event_type>` - Events like `RIG.FREQ` and `RIG.PTT` are published to topics like `js8/rig/freq`.

### Example Command

To send a message using the `mosquitto_pub` command-line tool, you would use:

mosquitto_pub -h localhost -t "js8/tx/command" -m '{"message": "CQ from my dashboard"}' -u "your_username" -P "your_password"


## Contributing

We welcome contributions! Please feel free to open issues or submit pull requests.

## License

This project is licensed under the GPL v3 License
