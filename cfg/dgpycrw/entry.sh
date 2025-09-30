#!/usr/bin/bash
cd /app/crw

date
while true
do
    python3 -u main.py
    sleep 36000
done
