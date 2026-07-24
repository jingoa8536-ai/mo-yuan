#!/bin/bash
# Try Ollama vision with streaming (returns partial output faster)
IMG_PATH="/c/Users/user/AppData/Local/hermes/profiles/laap-avatar-v4/image_cache/img_1cdd68034bd5.jpg"

# Convert to base64
IMG_B64=$(base64 -w0 "$IMG_PATH")

# Use streaming - curl outputs as each token is generated
curl -s -N -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"minicpm-v\",
    \"prompt\": \"Describe this image in detail in Chinese. What do you see?\",
    \"images\": [\"$IMG_B64\"],
    \"stream\": true
  }" --max-time 600 2>&1 | python3 -c "
import sys, json
full_text = ''
for line in sys.stdin:
    line = line.strip()
    if line:
        try:
            data = json.loads(line)
            chunk = data.get('response', '')
            full_text += chunk
            print(chunk, end='', flush=True)
            if data.get('done', False):
                break
        except:
            pass
"
