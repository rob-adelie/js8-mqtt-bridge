#!/bin/bash

# setup virtual environment and activate
python3 -m venv venv 
source venv/bin/activate

# Install the pip requirements
pip3 install --no-cache-dir -r requirements.txt

# Define the directory path
SERVICE_DIR="$HOME/.config/systemd/user"
# Use mkdir -p to create the directory safely
mkdir -p "$SERVICE_DIR"
cp ./js8-mqtt-bridge.service "$SERVICE_DIR/"

# Enable lingering for the local user, so the service will start on boot
sudo loginctl enable-linger $USER
systemctl --user enable js8-mqtt-bridge.service
systemctl --user start js8-mqtt-bridge.service
systemctl --user status js8-mqtt-bridge.service

mkdir -p logs
