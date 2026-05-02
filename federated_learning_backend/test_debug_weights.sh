#!/bin/bash

# Test script to trigger debug output via curl

BASE_URL="http://localhost:8000/api/fl_core"

echo "========================================="
echo "STEP 1: Register Device"
echo "========================================="

REGISTER_RESPONSE=$(curl -s -X POST "$BASE_URL/register/" \
  -H "Content-Type: application/json" \
  -d '{
    "device_name": "test-device",
    "device_os": "test"
  }')

echo "$REGISTER_RESPONSE"

DEVICE_ID=$(echo "$REGISTER_RESPONSE" | grep -o '"device_id":"[^"]*' | cut -d'"' -f4)
TOKEN=$(echo "$REGISTER_RESPONSE" | grep -o '"token":"[^"]*' | cut -d'"' -f4)

echo ""
echo "Device ID: $DEVICE_ID"
echo "Token: $TOKEN"

if [ -z "$TOKEN" ]; then
  echo "ERROR: Failed to register device"
  exit 1
fi

echo ""
echo "========================================="
echo "STEP 2: Get Latest Model"
echo "========================================="

curl -s -X GET "$BASE_URL/model/latest/" \
  -H "Authorization: Token $TOKEN" | grep -o '"version":[^,]*'

echo ""
echo "========================================="
echo "STEP 3: Get Current Round"
echo "========================================="

ROUND_RESPONSE=$(curl -s -X GET "$BASE_URL/round/current/" \
  -H "Authorization: Token $TOKEN")

echo "$ROUND_RESPONSE"

ROUND_ID=$(echo "$ROUND_RESPONSE" | grep -o '"round_id":[^,]*' | cut -d':' -f2)

echo ""
echo "Round ID: $ROUND_ID"

if [ -z "$ROUND_ID" ]; then
  echo "ERROR: No active round found"
  echo "You may need to create a round first"
  exit 1
fi

echo ""
echo "========================================="
echo "STEP 4: Create Test Weight Data"
echo "========================================="

# Create a simple Python dict with numpy arrays (pickled)
python3 << 'EOF'
import pickle
import base64
import hashlib
import numpy as np

# Create test weights (dict of numpy arrays - common in ML frameworks)
weights = {
    'layer1_weights': np.random.randn(10, 5).astype(np.float32),
    'layer1_bias': np.random.randn(5).astype(np.float32),
    'layer2_weights': np.random.randn(5, 2).astype(np.float32),
    'layer2_bias': np.random.randn(2).astype(np.float32),
}

# Pickle and encode
weight_delta = pickle.dumps(weights)
weight_delta_b64 = base64.b64encode(weight_delta).decode('utf-8')
parameters_hash = hashlib.sha256(weight_delta).hexdigest()

# Save to file for curl
with open('/tmp/weight_delta.txt', 'w') as f:
    f.write(weight_delta_b64)
with open('/tmp/params_hash.txt', 'w') as f:
    f.write(parameters_hash)

print(f"Weight delta size: {len(weight_delta)} bytes")
print(f"Parameters hash: {parameters_hash}")
print(f"Saved to /tmp/weight_delta.txt and /tmp/params_hash.txt")
EOF

WEIGHT_DELTA=$(cat /tmp/weight_delta.txt)
PARAMS_HASH=$(cat /tmp/params_hash.txt)

echo ""
echo "========================================="
echo "STEP 5: Submit Update (THIS SHOULD TRIGGER DEBUG OUTPUT)"
echo "========================================="

curl -s -X POST "$BASE_URL/updates/submit/" \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"round_id\": $ROUND_ID,
    \"model_version\": 1,
    \"weight_delta\": \"$WEIGHT_DELTA\",
    \"parameters_hash\": \"$PARAMS_HASH\",
    \"num_examples\": 100,
    \"local_loss\": 0.5,
    \"local_accuracy\": 0.85,
    \"training_time\": 120.5
  }"

echo ""
echo ""
echo "========================================="
echo "✅ Check your docker-compose terminal for:"
echo "=== DEBUG WEIGHT TYPE ==="
echo "TYPE: <class 'dict'>"
echo "FIRST VALUE TYPE: <class 'numpy.ndarray'>"
echo "==============================="
echo "========================================="
