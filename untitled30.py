import argparse

import flwr as fl
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset


class FusionModel(nn.Module):
    def __init__(self, s_dim=768, w_dim=64):
        super().__init__()
        self.s_proj = nn.Linear(s_dim, 256)
        self.w_proj = nn.Linear(w_dim, 256)
        self.attn = nn.MultiheadAttention(256, 4, batch_first=True)
        self.classifier = nn.Sequential(
            nn.Linear(512, 128),
            nn.ReLU(),
            nn.Linear(128, 2),
        )

    def forward(self, s, w):
        s = self.s_proj(s).unsqueeze(1)
        w = self.w_proj(w).unsqueeze(1)
        attn_out, _ = self.attn(w, s, s)
        fused = torch.cat([attn_out.squeeze(1), w.squeeze(1)], dim=1)
        return self.classifier(fused)


def generate_client_data(n=200, seed=0):
    torch.manual_seed(seed)
    x_text = torch.randn(n, 768)
    x_wear = torch.randn(n, 64)
    y = torch.randint(0, 2, (n,))
    return x_text, x_wear, y


class FLClient(fl.client.NumPyClient):
    def __init__(self, model, data):
        self.model = model
        self.x_text, self.x_wear, self.y = data

        dataset = TensorDataset(self.x_text, self.x_wear, self.y)
        self.loader = DataLoader(dataset, batch_size=32, shuffle=True)

        self.loss_fn = nn.CrossEntropyLoss()
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=1e-4)

    def get_parameters(self, config):
        return [val.detach().cpu().numpy() for _, val in self.model.state_dict().items()]

    def set_parameters(self, parameters):
        keys = list(self.model.state_dict().keys())
        state_dict = dict(zip(keys, parameters))
        self.model.load_state_dict({k: torch.tensor(v) for k, v in state_dict.items()})

    def fit(self, parameters, config):
        self.set_parameters(parameters)
        self.model.train()

        for _ in range(1):
            for s, w, y in self.loader:
                self.optimizer.zero_grad()
                out = self.model(s, w)
                loss = self.loss_fn(out, y)
                loss.backward()
                self.optimizer.step()

        return self.get_parameters(config), len(self.x_text), {}

    def evaluate(self, parameters, config):
        self.set_parameters(parameters)
        self.model.eval()
        correct = 0

        with torch.no_grad():
            for s, w, y in self.loader:
                preds = torch.argmax(self.model(s, w), dim=1)
                correct += (preds == y).sum().item()

        acc = correct / len(self.x_text)
        return 0.0, len(self.x_text), {"accuracy": acc}


def start_server(server_address="0.0.0.0:8080", rounds=5, min_clients=3):
    strategy = fl.server.strategy.FedAvg(
        fraction_fit=1.0,
        min_fit_clients=min_clients,
        min_available_clients=min_clients,
    )

    fl.server.start_server(
        server_address=server_address,
        config=fl.server.ServerConfig(num_rounds=rounds),
        strategy=strategy,
    )


def start_client(server_address="127.0.0.1:8080", client_id=0, samples=200):
    model = FusionModel()
    data = generate_client_data(n=samples, seed=client_id)
    client = FLClient(model=model, data=data)
    fl.client.start_numpy_client(server_address=server_address, client=client)


def parse_args():
    parser = argparse.ArgumentParser(description="Federated learning demo with Flower + PyTorch")
    parser.add_argument("mode", choices=["server", "client"], help="Run as server or client")
    parser.add_argument("--server-address", default="127.0.0.1:8080", help="Flower server address")
    parser.add_argument("--rounds", type=int, default=5, help="Number of federated rounds (server)")
    parser.add_argument("--min-clients", type=int, default=3, help="Minimum clients per round (server)")
    parser.add_argument("--client-id", type=int, default=0, help="Client ID used as random seed")
    parser.add_argument("--samples", type=int, default=200, help="Samples per client")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.mode == "server":
        start_server(
            server_address=args.server_address,
            rounds=args.rounds,
            min_clients=args.min_clients,
        )
    else:
        start_client(
            server_address=args.server_address,
            client_id=args.client_id,
            samples=args.samples,
        )


if __name__ == "__main__":
    main()