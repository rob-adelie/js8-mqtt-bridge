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
import threading
import os

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

# Mailbox configuration
MAILBOX_FILE = conf.get("MAILBOX_FILE", "mailbox_messages.json").strip()
MAILBOX_RETRIEVAL_INTERVAL = int(conf.get("MAILBOX_RETRIEVAL_INTERVAL", "3600"))


TX_DELAY_SECONDS = 15
MESSAGE_TIMEOUT_SECONDS = 120

# --- Global State ---
JS8_BASE_TOPIC = "js8"
JS8_RX_COMPLETE_TOPIC = f"{JS8_BASE_TOPIC}/rx/complete"
JS8_RX_INCOMPLETE_TOPIC = f"{JS8_BASE_TOPIC}/rx/incomplete"
JS8_MAILBOX_TOPIC = f"{JS8_BASE_TOPIC}/mailbox"

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
        # Subscribe to the mailbox request topic
        client.subscribe(f"{JS8_BASE_TOPIC}/mailbox/request")
    else:
        logger.error(f"Failed to connect, return code {rc}\n")

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
    elif msg.topic == f"{JS8_BASE_TOPIC}/mailbox/request":
        try:
            # Handle mailbox request
            payload = json.loads(msg.payload.decode())
            request_type = payload.get("type", "all")
            callsign_filter = payload.get("callsign", "").strip().upper()
            logger.info(f"Mailbox request: type={request_type}, callsign_filter='{callsign_filter}'")

            if request_type == "all":
                # Return all mailbox messages, optionally filtered by callsign
                messages = load_mailbox_messages()
                if callsign_filter:
                    # Filter messages by callsign (both FROM and TO)
                    filtered_messages = [
                        msg for msg in messages 
                        if callsign_filter in [msg.get('from', '').upper(), msg.get('to', '').upper()]
                    ]
                    response = {
                        "type": "mailbox_response",
                        "messages": filtered_messages,
                        "count": len(filtered_messages),
                        "filtered_by": callsign_filter
                    }
                    logger.info(f"Sent {len(filtered_messages)} messages filtered by callsign {callsign_filter} to MQTT")
                else:
                    response = {
                        "type": "mailbox_response",
                        "messages": messages,
                        "count": len(messages)
                    }
                    logger.info(f"Sent {len(messages)} mailbox messages to MQTT")
                client.publish(f"{JS8_MAILBOX_TOPIC}/response", json.dumps(response), qos=0)
            elif request_type == "recent":
                # Return recent messages (last 10), optionally filtered by callsign
                messages = load_mailbox_messages()
                if callsign_filter:
                    # Filter messages by callsign first, then take recent
                    filtered_messages = [
                        msg for msg in messages 
                        if callsign_filter in [msg.get('from', '').upper(), msg.get('to', '').upper()]
                    ]
                    recent_messages = filtered_messages[-10:] if len(filtered_messages) > 10 else filtered_messages
                    response = {
                        "type": "mailbox_response",
                        "messages": recent_messages,
                        "count": len(recent_messages),
                        "filtered_by": callsign_filter
                    }
                    logger.info(f"Sent {len(recent_messages)} recent messages filtered by callsign {callsign_filter} to MQTT")
                else:
                    recent_messages = messages[-10:] if len(messages) > 10 else messages
                    response = {
                        "type": "mailbox_response",
                        "messages": recent_messages,
                        "count": len(recent_messages)
                    }
                    logger.info(f"Sent {len(recent_messages)} recent mailbox messages to MQTT")
                client.publish(f"{JS8_MAILBOX_TOPIC}/response", json.dumps(response), qos=0)
            elif request_type == "refresh":
                # Force refresh mailbox from JS8Call
                process_mailbox_retrieval()
                messages = load_mailbox_messages()
                if callsign_filter:
                    # Filter messages by callsign
                    filtered_messages = [
                        msg for msg in messages 
                        if callsign_filter in [msg.get('from', '').upper(), msg.get('to', '').upper()]
                    ]
                    response = {
                        "type": "mailbox_response",
                        "messages": filtered_messages,
                        "count": len(filtered_messages),
                        "refreshed": True,
                        "filtered_by": callsign_filter
                    }
                    logger.info(f"Refreshed and sent {len(filtered_messages)} messages filtered by callsign {callsign_filter} to MQTT")
                else:
                    response = {
                        "type": "mailbox_response",
                        "messages": messages,
                        "count": len(messages),
                        "refreshed": True
                    }
                    logger.info(f"Refreshed and sent {len(messages)} mailbox messages to MQTT")
                client.publish(f"{JS8_MAILBOX_TOPIC}/response", json.dumps(response), qos=0)
        except json.JSONDecodeError:
            logger.error(f"Failed to decode mailbox request JSON: {msg.payload.decode()}")
        except Exception as e:
            logger.error(f"Error handling mailbox request: {e}")

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

def send_js8_command(command):
    """Send a command to JS8Call and return the response."""
    try:
        command_str = json.dumps(command) + '\n'
        js8_socket.sendall(command_str.encode('utf-8'))
        
        # Wait for response - handle large responses by reading until we get a complete JSON
        response_data = b""
        while True:
            try:
                chunk = js8_socket.recv(4096)
                if not chunk:
                    break
                response_data += chunk
                
                # Try to parse the response to see if it's complete
                try:
                    response_str = response_data.decode('utf-8').strip()
                    # Check if we have a complete JSON object
                    if response_str.endswith('}') and response_str.count('{') == response_str.count('}'):
                        return json.loads(response_str)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Continue reading if JSON is not complete
                    continue
                    
            except socket.timeout:
                # If we have data, try to parse it
                if response_data:
                    break
                else:
                    logger.error("Timeout waiting for response from JS8Call")
                    return None
        
        if response_data:
            response_str = response_data.decode('utf-8').strip()
            try:
                return json.loads(response_str)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON response: {e}")
                logger.error(f"Response length: {len(response_str)}")
                logger.error(f"Response (first 500 chars): {response_str[:500]}")
                return None
        else:
            logger.error("No response data received")
            return None
            
    except Exception as e:
        logger.error(f"Error sending command to JS8Call: {e}")
        return None

def retrieve_mailbox_messages():
    """Retrieve mailbox messages from JS8Call."""
    logger.info("Retrieving mailbox messages...")
    
    command = {
        "type": "INBOX.GET_MESSAGES",
        "value": "",
        "params": {
            "_ID": int(time.time() * 1000)
        }
    }
    
    response = send_js8_command(command)
    if response:
        logger.info(f"Retrieved mailbox response: {json.dumps(response, indent=2)}")
        return response
    else:
        logger.error("Failed to retrieve mailbox messages")
        return None

def load_mailbox_messages():
    """Load existing mailbox messages from file."""
    if os.path.exists(MAILBOX_FILE):
        try:
            with open(MAILBOX_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading mailbox file: {e}")
            return []
    return []

def save_mailbox_messages(messages):
    """Save mailbox messages to file."""
    try:
        with open(MAILBOX_FILE, 'w') as f:
            json.dump(messages, f, indent=2)
        logger.info(f"Saved {len(messages)} mailbox messages to {MAILBOX_FILE}")
    except IOError as e:
        logger.error(f"Error saving mailbox file: {e}")

def append_new_mailbox_messages(new_messages, existing_messages):
    """Append new messages to existing mailbox messages, avoiding duplicates."""
    if not new_messages or not isinstance(new_messages, list):
        return existing_messages
    
    # Create a set of existing message IDs for quick lookup
    existing_ids = {msg.get('id', '') for msg in existing_messages if 'id' in msg}
    
    # Add new messages that don't already exist
    added_count = 0
    for new_msg in new_messages:
        # Extract the message ID from JS8Call format
        message_id = None
        if 'params' in new_msg and '_ID' in new_msg['params']:
            message_id = new_msg['params']['_ID']
        elif 'id' in new_msg:
            message_id = new_msg['id']
        
        if message_id and message_id not in existing_ids:
            # Convert JS8Call message format to our standard format
            converted_msg = convert_js8_message(new_msg)
            existing_messages.append(converted_msg)
            existing_ids.add(message_id)
            added_count += 1
    
    if added_count > 0:
        logger.info(f"Added {added_count} new mailbox messages")
    
    return existing_messages

def convert_js8_message(js8_msg):
    """Convert JS8Call message format to our standard format."""
    if 'params' not in js8_msg:
        return js8_msg
    
    params = js8_msg['params']
    
    # Extract the message text
    text = params.get('TEXT', '')
    
    # Extract sender and recipient
    from_callsign = params.get('FROM', '')
    to_callsign = params.get('TO', '')
    
    # Extract timestamp
    timestamp = params.get('UTC', '')
    
    # Extract other useful info
    snr = params.get('SNR', 0)
    freq = params.get('FREQ', 0)
    
    # Create our standard message format
    converted = {
        'id': params.get('_ID', ''),
        'type': js8_msg.get('type', 'UNKNOWN'),
        'from': from_callsign,
        'to': to_callsign,
        'text': text,
        'timestamp': timestamp,
        'snr': snr,
        'freq': freq,
        'raw_params': params  # Keep original params for reference
    }
    
    return converted

def process_mailbox_retrieval():
    """Process mailbox retrieval and update storage."""
    try:
        # Retrieve messages from JS8Call
        response = retrieve_mailbox_messages()
        if not response:
            logger.warning("No response received from JS8Call")
            return
        
        # Load existing messages
        existing_messages = load_mailbox_messages()
        
        # Extract messages from response - try different possible formats
        new_messages = []
        
        # Check various possible response formats
        if 'params' in response:
            if 'MESSAGES' in response['params'] and isinstance(response['params']['MESSAGES'], list):
                new_messages = response['params']['MESSAGES']
                logger.info(f"Found {len(new_messages)} messages in response['params']['MESSAGES']")
            elif 'messages' in response['params'] and isinstance(response['params']['messages'], list):
                new_messages = response['params']['messages']
                logger.info(f"Found {len(new_messages)} messages in response['params']['messages']")
        
        if 'value' in response:
            if isinstance(response['value'], list):
                new_messages = response['value']
                logger.info(f"Found {len(new_messages)} messages in response['value']")
            elif isinstance(response['value'], str) and response['value']:
                # Sometimes messages might be in a string format
                try:
                    parsed_value = json.loads(response['value'])
                    if isinstance(parsed_value, list):
                        new_messages = parsed_value
                        logger.info(f"Found {len(new_messages)} messages in parsed response['value']")
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse response['value'] as JSON: {response['value']}")
        
        # If still no messages found, log the full response structure for debugging
        if not new_messages:
            logger.warning("No messages found in response. Full response structure:")
            logger.warning(json.dumps(response, indent=2))
        else:
            logger.info(f"Successfully extracted {len(new_messages)} messages from JS8Call response")
        
        # Append new messages to existing ones
        updated_messages = append_new_mailbox_messages(new_messages, existing_messages)
        
        # Save updated messages
        save_mailbox_messages(updated_messages)
        
    except Exception as e:
        logger.error(f"Error processing mailbox retrieval: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

def mailbox_retrieval_worker():
    """Background worker for periodic mailbox retrieval."""
    while True:
        try:
            process_mailbox_retrieval()
            time.sleep(MAILBOX_RETRIEVAL_INTERVAL)
        except Exception as e:
            logger.error(f"Error in mailbox retrieval worker: {e}")
            time.sleep(60)  # Wait 1 minute before retrying on error

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

    # Perform initial mailbox retrieval
    logger.info("Performing initial mailbox retrieval...")
    process_mailbox_retrieval()

    # Start mailbox retrieval worker in background thread
    mailbox_thread = threading.Thread(target=mailbox_retrieval_worker, daemon=True)
    mailbox_thread.start()
    logger.info("Started mailbox retrieval worker thread")

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
                        logger.warning("Command payload did not contain a 'message' key.")
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON from TX queue: {command_payload_str}")


            # Message timeout check for query responses
            if current_time - last_timeout_check > 5:
                last_timeout_check = current_time
                timed_out_keys = []
                for msg_key, msg_data in message_buffer.items():
                    # This check is ONLY for query responses
                    # Use longer timeout for heartbeat messages (they often have grid info in later frames)
                    text_content = msg_data.get('text', '')
                    if '@HB' in text_content or 'HEARTBEAT' in text_content:
                        timeout_duration = 10  # Longer timeout for heartbeat messages
                    else:
                        timeout_duration = 3  # Standard timeout for other query responses
                    
                    if current_time - msg_data['last_seen'] > timeout_duration:
                        timed_out_keys.append(msg_key)
                
                for msg_key in timed_out_keys:
                    msg_data = message_buffer[msg_key]
                    message_id = msg_data['origin'] # Use origin as ID for query responses

                    logger.info(f"Query response from {msg_data['origin']} timed out. Publishing as complete.")
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
                                logger.debug(text_content)

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
                                snr = js8_message.get("params", {}).get("SNR")
                                logger.info(f"Received definitive RX.DIRECTED message with ID '{message_id}'. Publishing now.")
                                
                                complete_message = {
                                    "id": message_id,
                                    "text": js8_message.get("value", ""),
                                    "snr": snr,
                                    "origin": js8_message.get("params", {}).get("ORIGIN", ""),
                                    "complete": True
                                }
                                logger.debug(complete_message)
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


