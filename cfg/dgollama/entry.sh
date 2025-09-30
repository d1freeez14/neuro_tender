#!/usr/bin/bash

echo "serve"
OLLAMA_HOST=0.0.0.0  ollama serve &
sleep 5
echo "run"

ollama create model -f /opt/Modelfile

ollama run model

tail -f /dev/null
