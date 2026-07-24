#!/bin/bash
# Generate base64 and call Ollama API properly
IMG_PATH="/c/Users/user/AppData/Local/hermes/profiles/laap-avatar-v4/image_cache/img_1cdd68034bd5.jpg"

# Convert image to base64
IMG_B64=$(base64 -w0 "$IMG_PATH")

# Create JSON payload
cat > /tmp/vision_payload.json << EOF
{
  "model": "minicpm-v",
  "prompt": "请用中文详细描述这张图片里有什么内容。包括：1)这是什么场景 2)有什么物体 3)颜色和氛围 4)任何文字",
  "images": ["$IMG_B64"],
  "stream": false,
  "options": {
    "temperature": 0.1,
    "max_tokens": 300
  }
}
EOF

# Call Ollama API
curl -s -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d @/tmp/vision_payload.json \
  --max-time 300
