import paho.mqtt.client as mqtt
import json
import time

# --- Configuration ---
# Attempts to load configuration from the bridge configuration file
conf = {
    "MQTT_BROKER": "192.168.10.208",
    "MQTT_PORT": "1883",
    "MQTT_USERNAME": "js8tomqtt",
    "MQTT_PASSWORD": "kwa-31415",
}

try:
    with open('js8-mqtt-bridge.cfg', 'r') as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                if value != f"<your {key.lower().replace('_', ' ')}>": # Basic check to ignore template defaults if not filled
                    conf[key.strip()] = value.strip()
except FileNotFoundError:
    print("Notice: js8-mqtt-bridge.cfg not found. Using defaults.")

JS8_BASE_TOPIC = "js8"
JS8_RX_COMPLETE_TOPIC = f"{JS8_BASE_TOPIC}/rx/complete"
JS8_TX_COMMAND_TOPIC = f"{JS8_BASE_TOPIC}/tx/command"

def on_connect(client, userdata, flags, rc, properties):
    if rc == 0:
        print("\n--- Connected to MQTT Broker! ---")
        client.subscribe(JS8_TX_COMMAND_TOPIC)
        print(f"--- Subscribed to {JS8_TX_COMMAND_TOPIC} ---\n> ", end="", flush=True)
    else:
        print(f"Failed to connect to MQTT broker, return code {rc}")

def on_message(client, userdata, msg):
    """Callback when a message is received from MQTT."""
    try:
        # Expected format from your phone app matching JS8Call JS8_TX_COMMAND_TOPIC
        payload = json.loads(msg.payload.decode())
        print(f"\n[RECEIVED from Phone (js8/tx/command)]: {payload.get('message', msg.payload.decode())}")
    except json.JSONDecodeError:
        print(f"\n[RECEIVED RAW from Phone]: {msg.payload.decode()}")
    print("> ", end="", flush=True)

def main():
    print(f"Starting emulator. Connecting to MQTT Broker {conf['MQTT_BROKER']}:{conf['MQTT_PORT']}...")
    
    # Initialize MQTT client
    mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    
    if conf['MQTT_USERNAME'] and conf['MQTT_PASSWORD']:
        # Only set if they look like actual credentials, skipping placeholders
        if not conf['MQTT_USERNAME'].startswith('<'): 
            mqtt_client.username_pw_set(username=conf['MQTT_USERNAME'], password=conf['MQTT_PASSWORD'])
        
    try:
        mqtt_client.connect(conf['MQTT_BROKER'], int(conf['MQTT_PORT']), 60)
    except Exception as e:
        print(f"Error connecting to MQTT Broker: {e}")
        return

    # Start network loop in the background
    mqtt_client.loop_start()

    print("\n" + "="*50)
    print("JS8Call <-> MQTT Emulator")
    print("Type a message to send to the phone app.")
    print("Format: <ORIGIN_CALLSIGN>:<MESSAGE>")
    print("Example: M0XYZ:Hello this is a test message!")
    print("If you just type a message, it defaults to 'M0XYZ' as the sender.")
    print("Type 'quit' or 'exit' to stop.")
    print("="*50 + "\n")

    try:
        while True:
            try:
                user_input = input("")
            except EOFError:
                break
                
            if user_input.lower() in ['quit', 'exit']:
                break

            if not user_input.strip():
                print("> ", end="", flush=True)
                continue

            # Parse origin and text from input
            if ":" in user_input:
                origin, text = user_input.split(":", 1)
                origin = origin.strip()
                text = text.strip()
            else:
                origin = "M0XYZ"
                text = user_input.strip()

            msg_id = int(time.time() * 1000)
            
            # This matches the final js8-mqtt-bridge JSON output structure
            complete_message = {
                "id": msg_id,
                "text": text,
                "snr": -12, # Mock SNR for realistic JS8Call simulation
                "origin": origin,
                "complete": True
            }

            mqtt_client.publish(JS8_RX_COMPLETE_TOPIC, json.dumps(complete_message), qos=0)
            print(f"[SENT to Phone (js8/rx/complete)]: {complete_message}")
            print("> ", end="", flush=True)

    except KeyboardInterrupt:
        print("\nShutting down emulator...")
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Emulator error: {e}")
