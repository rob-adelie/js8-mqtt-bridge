###############################################################################
# js8-mqtt bridge
#
# This project is a Python-based application that acts as a bridge between a 
# js8call  and an MQTT broker. This allows us to have a consistent easy way
# to have multiple clients communicate with js8call. 
#
# Copyright (C) 2025  RSJ Cole
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.
###############################################################################

import socket
import json
import time
import paho.mqtt.client as mqtt
from collections import deque
import logging
import sys

####### Setup Logging ######
# Create a logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create a file handler for logging to a file
file_handler = logging.FileHandler('logs/js8-mqtt-bridge.log')
file_handler.setLevel(logging.DEBUG)

# Create a stream handler for logging to the console
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.DEBUG)

# Create a formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(stream_handler)
logger.info("Starting Logging...")



# Get all parameters from the config file
conf = {}
with open('js8-mqtt-bridge.cfg', 'r') as file:
    # Iterate over each line
    for line in file:
        line = line.strip()
        if line and not line.startswith('#'):  # Ignore blank lines and comments
            key, value = line.split('=', 1)  # Split by the first '=' encountered
            conf[key.strip()] = value.strip()

MQTT_BROKER = conf["MQTT_BROKER"].strip()
MQTT_PORT = conf["MQTT_PORT"].strip()
MQTT_USERNAME = conf["MQTT_USERNAME"].strip()
MQTT_PASSWORD = conf["MQTT_PASSWORD"].strip()
JS8CALL_HOST = conf["JS8CALL_HOST"].strip()
JS8CALL_PORT = conf["JS8CALL_PORT"].strip()


TX_DELAY_SECONDS = 15
MESSAGE_TIMEOUT_SECONDS = 120

# --- Global State ---
JS8_BASE_TOPIC = "js8"
JS8_RX_COMPLETE_TOPIC = f"{JS8_BASE_TOPIC}/rx/complete"
JS8_RX_INCOMPLETE_TOPIC = f"{JS8_BASE_TOPIC}/rx/incomplete"

js8_socket = None
# This buffer is now ONLY for multi-frame query responses (no standard ID)
message_buffer = {}  
tx_queue = deque()
# Set to track IDs of messages that have already been published.
# This prevents duplicates if RX.DIRECTED arrives before the final RX.ACTIVITY frame.
published_ids = set()

# --- MQTT Callbacks ---
def on_connect(client, userdata, flags, rc, properties):
    """The callback for when the client receives a CONNACK response from the server."""
    if rc == 0:
        logger.info("Connected to MQTT Broker!")
        # Subscribe to the topic for sending commands to JS8Call
        client.subscribe(f"{JS8_BASE_TOPIC}/tx/command")
    else:
        loger.error(f"Failed to connect, return code {rc}\n")

def on_message(client, userdata, msg):
    """The callback for when a PUBLISH message is received from the server."""
    logger.debug(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")
    if msg.topic == f"{JS8_BASE_TOPIC}/tx/command":
        try:
            # We add the raw JSON string to the queue; it's parsed later.
            tx_queue.append(msg.payload.decode())
            logger.info("Command added to queue.")
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON payload: {msg.payload.decode()}")

# --- JS8Call API Functions ---
def connect_js8call():
    """Continuously retries the connection to the JS8Call API until successful."""
    global js8_socket
    
    while True:
        try:
            logger.info("Attempting to connect to JS8Call...")
            js8_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            js8_socket.settimeout(1)  # Increase timeout for better stability
            js8_socket.connect((JS8CALL_HOST, int(JS8CALL_PORT)))
            logger.info("Connected to JS8Call API")
            return True  # Exit the function on success
        except (socket.error, Exception) as e:
            logger.error(f"Error connecting to JS8Call: {e}. Retrying in 5 seconds...")
            js8_socket.close() # Ensure socket is closed before next attempt
            time.sleep(5)  # Wait before retrying to avoid excessive CPU usage

# --- Main Logic ---
def main():
    if not connect_js8call():
        return

    mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
   
    mqtt_client.username_pw_set(username=MQTT_USERNAME, password=MQTT_PASSWORD)
    mqtt_client.connect(MQTT_BROKER, int(MQTT_PORT), 60)
    mqtt_client.loop_start()

    logger.info("js8call monitoring running...")
    buffer = ""
    last_timeout_check = time.time()
    last_tx_time = time.time()

    try:
        while True:
            current_time = time.time()

            # Command queue processing
            # Check if there are commands to send and if the TX delay has passed
            if tx_queue and current_time - last_tx_time > TX_DELAY_SECONDS:
                command_payload_str = tx_queue.popleft()
                try:
                    command_payload = json.loads(command_payload_str)
                    logger.info(f"Processing command from queue: {command_payload}")
                    logger.debug(command_payload_str)

                    # Check if the command contains the 'message' key 
                    if 'message' in command_payload:
                        # Construct the CORRECT JS8Call API JSON payload
                        js8_payload = {
                            "type": "TX.SEND_MESSAGE",
                            "value": command_payload["message"],
                            "params": {
                                "_ID": int(time.time() * 1000)
                            }
                        }
                        
                        js8_payload_str = json.dumps(js8_payload) + '\n'
                        js8_socket.sendall(js8_payload_str.encode('utf-8'))
                        last_tx_time = current_time
                    else:
                        logger.warn("Command payload did not contain a 'message' key.")
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON from TX queue: {command_payload_str}")


            # Message timeout check for query responses
            if current_time - last_timeout_check > 5:
                last_timeout_check = current_time
                timed_out_keys = []
                for msg_key, msg_data in message_buffer.items():
                    # This check is ONLY for query responses
                    timeout_duration = 3
                    if current_time - msg_data['last_seen'] > timeout_duration:
                        timed_out_keys.append(msg_key)
                
                for msg_key in timed_out_keys:
                    msg_data = message_buffer[msg_key]
                    message_id = msg_data['origin'] # Use origin as ID for query responses

                    logger,info(f"Query response from {msg_data['origin']} timed out. Publishing as complete.")
                    complete_message = {
                        "id": message_id,
                        "text": msg_data['text'],
                        "origin": msg_data['origin'],
                        "complete": True
                    }
                    mqtt_client.publish(JS8_RX_COMPLETE_TOPIC, json.dumps(complete_message), qos=0)
                    
                    del message_buffer[msg_key]

            # Receive and process messages from JS8Call
            try:
                data = js8_socket.recv(1024)
                if data:
                    buffer += data.decode('utf-8')
                    while '\n' in buffer:
                        message, buffer = buffer.split('\n', 1)
                        try:
                            js8_message = json.loads(message)
                            message_type = js8_message.get("type", "unknown")
                            
                            if message_type == "RX.ACTIVITY":
                                message_id = js8_message.get("params", {}).get("ID")
                                snr = js8_message.get("params", {}).get("SNR")
                                origin = js8_message.get("params", {}).get("ORIGIN")
                                text_content = js8_message.get("params", {}).get("TEXT", "")
                                
                                # Ignore RX.ACTIVITY for directed messages
                                if message_id is not None:
                                    logger.debug(f"Ignoring RX.ACTIVITY frame with ID '{message_id}' as we wait for RX.DIRECTED.")
                                    continue

                                # Only buffer messages that do NOT have a standard message ID
                                if origin:
                                    logger.debug(f"Buffering RX.ACTIVITY frame from '{origin}' as a query response.")
                                    buffer_key = origin
                                    
                                    if buffer_key not in message_buffer:
                                        message_buffer[buffer_key] = {
                                            'id': None,  
                                            'origin': origin,  
                                            'text': '',  
                                            'snr':snr,
                                            'last_seen': current_time
                                        }
                                    
                                    message_buffer[buffer_key]['text'] += text_content
                                    message_buffer[buffer_key]['last_seen'] = current_time

                            elif message_type == "RX.DIRECTED":
                                # This is the final, fully reassembled message from JS8Call.
                                message_id = js8_message.get("params", {}).get("ID")
                                logger.info(f"Received definitive RX.DIRECTED message with ID '{message_id}'. Publishing now.")
                                
                                complete_message = {
                                    "id": message_id,
                                    "text": js8_message.get("value", ""),
                                    "snr": snr,
                                    "origin": js8_message.get("params", {}).get("ORIGIN", ""),
                                    "complete": True
                                }
                                mqtt_client.publish(JS8_RX_COMPLETE_TOPIC, json.dumps(complete_message), qos=0)
                                logger.info(f"Published complete message from RX.DIRECTED: {complete_message['text']}")
                                
                            else:
                                # All other message types
                                logger.debug(f"Received other message type: {message_type}. Publishing to dynamic topic.")
                                dynamic_topic = f"{JS8_BASE_TOPIC}/{message_type.replace('.', '/').lower()}"
                                mqtt_client.publish(dynamic_topic, json.dumps(js8_message), qos=0)

                        except json.JSONDecodeError:
                            logger.error(f"Failed to decode JSON: {message}")
            except socket.timeout:
                pass

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        if js8_socket:
            js8_socket.close()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

if __name__ == "__main__":
    main()

