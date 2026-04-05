<<<<<<< HEAD
# Federated Learning Backend

A production-ready Django + Flower backend for federated learning with mobile clients.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Flutter Mobile App (on-device training + ONNX)     │
│  ├─ Train locally                                   │
│  ├─ Serialize weight delta                          │
│  └─ Send to Django API                              │
└────────────────┬────────────────────────────────────┘
                 │
         ┌───────▼──────────────┐
         │  Django REST API     │
         │  ├─ Auth (tokens)    │
         │  ├─ Device mgmt      │
         │  ├─ Round lifecycle  │
         │  ├─ Update storage   │
         │  └─ Model versions   │
         └────────┬─────────────┘
                  │
         ┌────────┴─────────────────┐
         │                          │
    ┌────▼────────┐        ┌───────▼──────┐
    │  PostgreSQL │        │  Flower      │
    │  ├─ Devices │        │  Aggregation │
    │  ├─ Rounds  │        │  Server      │
    │  ├─ Updates │        │  (FedAvg)    │
    │  └─ Models  │        └──────────────┘
    └─────────────┘
```

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Clone/setup project
cd federated_learning_backend

# Build and start services
docker-compose up -d

# Run migrations
docker-compose exec django python manage.py migrate

# Create superuser
docker-compose exec django python manage.py createsuperuser

# Access services
# - Django: http://localhost
# - Admin: http://localhost/admin/
# - API: http://localhost/api/fl/
# - Flower Dashboard: http://localhost/flower/
```

### Option 2: Manual Setup (Development)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DJANGO_SECRET_KEY='your-secret-key'
export DEBUG=True
export DB_NAME=federated_learning
export DB_USER=postgres

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start services (in separate terminals)
# Terminal 1: Django
python manage.py runserver 0.0.0.0:8000

# Terminal 2: Celery Worker
celery -A config worker -l info

# Terminal 3: Celery Beat (scheduler)
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Terminal 4: Flower Server (for aggregation)
python manage.py shell
>>> import flwr as fl
>>> strategy = fl.server.strategy.FedAvg(fraction_fit=1.0, min_fit_clients=3, min_available_clients=3)
>>> fl.server.start_server(server_address="127.0.0.1:8080", config=fl.server.ServerConfig(num_rounds=5), strategy=strategy)
```

## API Endpoints

### Device Management

#### Register Device
```
POST /api/fl/devices/register/
Content-Type: application/json

{
    "device_name": "iPhone-14-Pro",
    "device_type": "iOS",
    "os_version": "17.0",
    "app_version": "1.0.0"
}

Response (201):
{
    "device_id": "550e8400-e29b-41d4-a716-446655440000",
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "message": "Device registered successfully"
}
```

#### Get Device Profile
```
GET /api/fl/devices/profile/
Authorization: Bearer <token>

Response (200):
{
    "device": {
        "device_id": "550e8400-e29b-41d4-a716-446655440000",
        "device_name": "iPhone-14-Pro",
        "device_type": "iOS",
        "status": "active",
        "last_seen": "2024-04-04T12:00:00Z"
    },
    "total_updates": 5,
    "recent_updates": [...]
}
```

### Model Management

#### Get Latest Model
```
GET /api/fl/model/latest/
Authorization: Bearer <token>

Response (200):
{
    "version": "1.0.0",
    "description": "Initial model",
    "model_url": "http://localhost/media/models/model_v1.0.0.pt",
    "onnx_url": "http://localhost/media/models/onnx/model_v1.0.0.onnx",
    "created_at": "2024-04-04T10:00:00Z"
}
```

### Round Management

#### Get Current Round
```
GET /api/fl/rounds/current/
Authorization: Bearer <token>

Response (200):
{
    "round_number": 1,
    "round_id": 42,
    "model_version": "1.0.0",
    "status": "active",
    "min_clients": 3,
    "deadline": "2024-04-04T14:00:00Z",
    "already_submitted": false,
    "submitted_at": null
}
```

#### Get Round Status
```
GET /api/fl/rounds/42/status/
Authorization: Bearer <token>

Response (200):
{
    "id": 42,
    "round_number": 1,
    "status": "active",
    "participating_devices": 2,
    "aggregation_status": "pending"
}
```

### Update Submission

#### Submit Training Update
```
POST /api/fl/updates/submit/
Authorization: Bearer <token>
Content-Type: application/json

{
    "round_id": 42,
    "num_examples": 500,
    "local_loss": 0.234,
    "local_accuracy": 0.89,
    "weight_delta": "base64-encoded-serialized-weights",
    "parameters_hash": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6",
    "dp_clip_norm": 1.0,
    "dp_noise_scale": 0.001
}

Response (201):
{
    "update_id": "660e8400-e29b-41d4-a716-446655440001",
    "status": "Update received and queued for aggregation",
    "round_number": 1
}
```

### Admin Endpoints (requires admin auth)

#### Create Round
```
POST /api/fl/rounds/create/
Authorization: Bearer <admin-token>
Content-Type: application/json

{
    "round_number": 2,
    "model_version_id": 1,
    "min_clients": 3,
    "max_clients": 100
}

Response (201): [Round object]
```

#### Close Round
```
POST /api/fl/rounds/42/close/
Authorization: Bearer <admin-token>

Response (200):
{
    "message": "Round 1 closed",
    "participating_devices": 10
}
```

#### Trigger Aggregation
```
POST /api/fl/rounds/42/aggregate/
Authorization: Bearer <admin-token>

Response (200):
{
    "message": "Aggregation completed",
    "round_number": 1,
    "result": {
        "status": "success",
        "participating_count": 10,
        "total_examples": 5000
    }
}
```

## Flutter Client Integration

### 1. Install Dependencies
```dart
# pubspec.yaml
dependencies:
  http: ^1.1.0
  path_provider: ^2.1.0
  flutter_secure_storage: ^9.0.0
```

### 2. Device Registration
```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

class FLClient {
  final String baseUrl = "http://your-server.com/api/fl";
  String? deviceId;
  String? authToken;

  Future<void> registerDevice() async {
    final response = await http.post(
      Uri.parse('$baseUrl/devices/register/'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'device_name': 'Flutter-Device-001',
        'device_type': 'Android',  // or 'iOS'
        'os_version': '14.0',
        'app_version': '1.0.0',
      }),
    );

    if (response.statusCode == 201) {
      final data = jsonDecode(response.body);
      deviceId = data['device_id'];
      authToken = data['token'];
      // Save token securely
      await _secureStorage.write(key: 'fl_token', value: authToken);
    }
  }
}
```

### 3. Fetch Model & Training
```dart
Future<void> trainAndSubmit() async {
  // Get latest model
  final modelResponse = await http.get(
    Uri.parse('$baseUrl/model/latest/'),
    headers: _getHeaders(),
  );
  
  final modelData = jsonDecode(modelResponse.body);
  
  // Download ONNX model
  final onnxBytes = await http.read(Uri.parse(modelData['onnx_url']));
  
  // Train locally (native Kotlin/Swift with TensorFlow Lite)
  final weightDelta = await _trainLocal(onnxBytes);
  
  // Get current round
  final roundResponse = await http.get(
    Uri.parse('$baseUrl/rounds/current/'),
    headers: _getHeaders(),
  );
  
  final roundData = jsonDecode(roundResponse.body);
  
  // Submit update
  final updateResponse = await http.post(
    Uri.parse('$baseUrl/updates/submit/'),
    headers: _getHeaders(),
    body: jsonEncode({
      'round_id': roundData['round_id'],
      'num_examples': 200,
      'local_loss': 0.23,
      'local_accuracy': 0.91,
      'weight_delta': base64Encode(weightDelta),
      'parameters_hash': _sha256(weightDelta),
    }),
  );
}

Map<String, String> _getHeaders() {
  return {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer $authToken',
  };
}
```

## Database Models

### Device
- `device_id`: UUID (unique)
- `user`: Foreign key to Django User
- `device_name`: Device identifier
- `device_type`: iOS / Android
- `os_version`: OS version
- `app_version`: App version
- `status`: active / inactive / suspended
- `last_seen`: Last API call timestamp
- `created_at`: Registration time

### ModelVersion
- `version`: Semantic version (e.g., "1.0.0")
- `description`: Model description
- `model_file`: PyTorch model file
- `onnx_file`: ONNX export
- `is_active`: Current production model flag
- `created_at`: Creation timestamp

### Round
- `round_number`: Unique round ID
- `model_version`: FK to ModelVersion
- `status`: pending / active / closed / completed / failed
- `min_clients`: Minimum clients required
- `max_clients`: Maximum clients to accept
- `started_at`: Round start time
- `closed_at`: Update submission deadline
- `ended_at`: Round completion time
- `aggregation_status`: pending / in_progress / completed / failed

### ClientUpdate
- `update_id`: UUID (unique)
- `device`: FK to Device
- `round`: FK to Round
- `num_examples`: Number of local training examples
- `local_loss`: Local training loss
- `local_accuracy`: Local training accuracy
- `weight_delta`: Serialized model weights
- `parameters_hash`: SHA256 of weight_delta for integrity
- `dp_clip_norm`: Gradient clipping norm (optional)
- `dp_noise_scale`: DP noise std (optional)
- `status`: pending / received / validated / aggregated / failed
- `submitted_at`: Submission timestamp

## Configuration

### Environment Variables
```bash
# Django
DJANGO_SECRET_KEY=your-production-secret-key
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Database
DB_ENGINE=django.db.backends.postgresql
DB_NAME=federated_learning
DB_USER=postgres
DB_PASSWORD=secure-password
DB_HOST=postgres
DB_PORT=5432

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# CORS
CORS_ALLOWED_ORIGINS=https://your-app.com

# Flower
FLOWER_SERVER_ADDRESS=0.0.0.0:8080
FLOWER_NUM_ROUNDS=5
FLOWER_MIN_CLIENTS=3
```

### .env File Example
```bash
# .env
DJANGO_SECRET_KEY=super-secret-key-change-in-production
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com
DB_NAME=federated_learning
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=postgres
DB_PORT=5432
```

## Deployment Checklist

- [ ] Set `DEBUG=False` in production
- [ ] Use strong `DJANGO_SECRET_KEY`
- [ ] Configure PostgreSQL with backups
- [ ] Use Redis with persistence
- [ ] Enable HTTPS/SSL
- [ ] Configure CORS properly
- [ ] Set up log aggregation
- [ ] Monitor CPU/memory/disk
- [ ] Implement rate limiting on API
- [ ] Add database connection pooling
- [ ] Backup model files regularly
- [ ] Monitor Flower aggregation
- [ ] Set up alerts for failed rounds
- [ ] Implement audit logging

## Testing

### Run Tests
```bash
python manage.py test fl_core

# With coverage
coverage run --source='.' manage.py test fl_core
coverage report
```

### Manual API Testing
```bash
# Register device
curl -X POST http://localhost:8000/api/fl/devices/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "device_name": "test-device",
    "device_type": "iOS",
    "os_version": "17.0",
    "app_version": "1.0.0"
  }'

# Get device profile (using token from registration)
curl -X GET http://localhost:8000/api/fl/devices/profile/ \
  -H "Authorization: Bearer your-token"
```

## Troubleshooting

### Flower Server Not Starting
- Check port 8080 is not in use
- Verify Redis is running
- Check Flower logs: `docker-compose logs flower_server`

### Update Submission Failures
- Verify device token is active
- Check round is "active" status
- Validate parameters_hash matches
- Check weight_delta is properly base64 encoded

### Slow Aggregation
- Reduce number of clients
- Optimize model size (quantization)
- Use parallel processing in aggregation

### Database Connection Issues
- Verify PostgreSQL is running
- Check DB credentials in .env
- Ensure database exists
- Run `python manage.py migrate`

## Support & Contributing

For issues or questions:
1. Check Django logs: `docker-compose logs django`
2. Check Celery logs: `docker-compose logs celery_worker`
3. Access Django admin for debugging: `http://localhost/admin/`
4. Monitor Flower dashboard: `http://localhost/flower/`

## License

MIT
=======
git clone https://github.com/shihas-36/Multimodal-Depression-Detection.git
cd Multimodal-Depression-Detection

git checkout -b main
echo "# Multimodal Depression Detection" > README.md
git add README.md
git commit -m "Initial commit"
git push -u origin main

# then create a new branch
git checkout -b <your-branch-name>
git push -u origin <your-branch-name>
>>>>>>> 52349f4a042f30e5440e734b7907bdabb7759c95
