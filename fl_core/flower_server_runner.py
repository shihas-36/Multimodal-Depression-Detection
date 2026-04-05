#!/usr/bin/env python
import os
import sys
import django

# Add project to path
sys.path.insert(0, '/app')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

try:
    import flwr as fl
    from config.settings import FLOWER_SERVER_ADDRESS, FLOWER_NUM_ROUNDS, FLOWER_MIN_CLIENTS
    
    strategy = fl.server.strategy.FedAvg(
        fraction_fit=1.0,
        min_fit_clients=FLOWER_MIN_CLIENTS,
        min_available_clients=FLOWER_MIN_CLIENTS
    )
    
    print(f"Starting Flower server at {FLOWER_SERVER_ADDRESS}...")
    fl.server.start_server(
        server_address=FLOWER_SERVER_ADDRESS,
        config=fl.server.ServerConfig(num_rounds=FLOWER_NUM_ROUNDS),
        strategy=strategy
    )
except ImportError as e:
    print(f"Warning: Flower not available, skipping Flower server: {e}")
    print("To enable Flower, install: pip install flwr")
    sys.exit(0)
except Exception as e:
    print(f"Error starting Flower server: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

