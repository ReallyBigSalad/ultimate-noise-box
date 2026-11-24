#!/bin/bash

FILE=/data/my_data/noise.txt
if [ -f "$FILE" ]; then
    echo "$FILE exists."
else 
    echo "$FILE does not exist. Performing initial setup."
    touch "${FILE}"
    mkdir -p /data/my_data/noise
fi

cp -n ./assets/*.wav /data/my_data/noise/ 2>/dev/null || true
cp -n ./assets/*.jpg /data/my_data/noise/ 2>/dev/null || true

python3 noise.py
