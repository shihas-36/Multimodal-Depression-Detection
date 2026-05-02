FROM python:3.10-slim

WORKDIR /app

# Install minimal runtime dependencies (no build tools needed - using pre-built wheels)
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip for better wheel support
RUN pip install --upgrade pip setuptools wheel

# Install Python dependencies (all have pre-built wheels)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/staticfiles /app/media

# Collect static files
RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

# Railway will provide the start command via railway.toml
# Do NOT set CMD here
