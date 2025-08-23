#!/bin/bash
#
# To setup environment
# python3 -m venv venv
#

source venv/bin/activate
# To profile use call below
#python3 -m cProfile -o profile_output.prof js8tomqtt.py
python3  js8-mqtt-bridge.py
