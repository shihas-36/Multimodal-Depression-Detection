# =========================================================
# SOTA Multimodal Depression Prediction (HuggingFace Deploy)
# TwHIN-BERT (Text) + Wearable Features (Cross-Attention)
# =========================================================

import os
import re

# Force Transformers to use the PyTorch backend only.
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_TORCH", "1")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import torch
import torch.nn as nn
import torch.nn.functional as F
import pandas as pd
import gradio as gr
from transformers import AutoTokenizer, AutoModel
from sklearn.preprocessing import StandardScaler

# ---------- DEVICE ----------
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Using device:", device)

# ---------- PATHS ----------
SAVE_PATH = "./"

WEARABLE_PATH = os.path.join(SAVE_PATH, "module2_wearable_features.pt")
SOTA_MODEL_PATH = os.path.join(SAVE_PATH, "best_model_87.pt")

# TwHIN-BERT will be loaded directly from Hugging Face
TWHIN_MODEL_NAME = "Twitter/twhin-bert-base"

# ---------- FEATURES ----------
FEATURE_COLUMNS_FINAL = [
    'daily_steps',
    'sleep_hours',
    'active_minutes',
    'daily_calories',
    'hr_avg_24h',
    'hrv_score_avg',
    'stress_level_avg',
    'sleep_hrv_score'
]

# ---------- TEXT CLEANING ----------
def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'<.*?>', '', text)
    text = re.sub(r'[@#]\w+', '', text)
    text = re.sub(r'[^\w\s]', '', text)
    return re.sub(r'\s+', ' ', text).strip()

# ---------- MODEL ----------
class SOTA_MultimodalModel(nn.Module):
    def __init__(self, s_dim, w_dim, embed_dim=256):
        super().__init__()

        self.s_proj = nn.Linear(s_dim, embed_dim)
        self.w_proj = nn.Linear(w_dim, embed_dim)

        self.attn_s2w = nn.MultiheadAttention(embed_dim, 8, batch_first=True)
        self.attn_w2s = nn.MultiheadAttention(embed_dim, 8, batch_first=True)

        self.ln1 = nn.LayerNorm(embed_dim)
        self.ln2 = nn.LayerNorm(embed_dim)

        self.classifier = nn.Sequential(
            nn.Linear(embed_dim * 2, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Linear(256, 2)
        )

    def forward(self, s_feat, w_feat):

        s = self.s_proj(s_feat).unsqueeze(1)
        w = self.w_proj(w_feat).unsqueeze(1)

        s_ctx, _ = self.attn_s2w(s, w, w)
        w_ctx, _ = self.attn_w2s(w, s, s)

        s_fused = self.ln1(s + s_ctx).squeeze(1)
        w_fused = self.ln2(w + w_ctx).squeeze(1)

        return self.classifier(torch.cat([s_fused, w_fused], dim=1))


# ---------- LOAD MODELS ----------
print("Loading TwHIN-BERT from Hugging Face...")

tokenizer = AutoTokenizer.from_pretrained(TWHIN_MODEL_NAME)

twhin_model = AutoModel.from_pretrained(
    TWHIN_MODEL_NAME,
    output_hidden_states=True
).to(device).eval()

print("TwHIN-BERT loaded from Hugging Face")

# ---------- WEARABLE DATA ----------
wearable_features = torch.load(WEARABLE_PATH)

if wearable_features.ndim == 1:
    wearable_features = wearable_features.unsqueeze(0)

w_dim = wearable_features.shape[1]

scaler = StandardScaler()
scaler.fit(wearable_features.cpu().numpy())

print("Scaler ready")

# ---------- LOAD MULTIMODAL ----------
s_dim = 768

multimodal_model = SOTA_MultimodalModel(s_dim, w_dim)
multimodal_model.load_state_dict(torch.load(SOTA_MODEL_PATH, map_location=device))
multimodal_model.to(device).eval()

print("Multimodal model loaded")

# ---------- DISPLAY ----------
def wearable_to_df(w):

    values = w.cpu().tolist()
    cols = FEATURE_COLUMNS_FINAL[:len(values)]

    return pd.DataFrame([values], columns=cols)


# ---------- PREDICT ----------
def sota_predict(text,
                 daily_steps,
                 sleep_hours,
                 active_minutes,
                 daily_calories,
                 hr_avg_24h,
                 hrv_score_avg,
                 stress_level_avg,
                 sleep_hrv_score):

    try:

        text = clean_text(text)

        # TEXT EMBEDDING
        with torch.no_grad():

            enc = tokenizer(
                text,
                max_length=128,
                padding="max_length",
                truncation=True,
                return_tensors="pt"
            )

            enc = {k: v.to(device) for k, v in enc.items()}

            out = twhin_model(**enc)

            s_feat = out.hidden_states[-1][:, 0, :]

        # USER INPUT
        user_features = [[
            daily_steps,
            sleep_hours,
            active_minutes,
            daily_calories,
            hr_avg_24h,
            hrv_score_avg,
            stress_level_avg,
            sleep_hrv_score
        ]]

        scaled_features = scaler.transform(user_features)

        w_feat = torch.tensor(
            scaled_features,
            dtype=torch.float32
        ).to(device)

        # MODEL
        with torch.no_grad():

            logits = multimodal_model(s_feat, w_feat)

            probs = F.softmax(logits, dim=1).cpu().numpy()[0]

        label = "HIGH RISK" if probs[0] > probs[1] else "LOW RISK"

        md = f"""
## 🧠 Depression Risk Prediction

**Result:** **{label}**

| Class | Probability |
|------|------|
| Higher Risk | {probs[0]:.4f} |
| Lower Risk | {probs[1]:.4f} |
"""

        return md, wearable_to_df(w_feat.squeeze(0))

    except Exception as e:

        return f"Error: {e}", pd.DataFrame()


# =========================================================
# GRADIO UI
# =========================================================

with gr.Blocks(theme=gr.themes.Soft()) as demo:

    gr.Markdown("# 🧠 Multimodal Depression Detection")

    gr.Markdown(
        "This system combines **social media text** and **wearable sensor data** "
        "using a **cross-attention multimodal deep learning model**."
    )

    with gr.Row():

        with gr.Column():

            text_input = gr.Textbox(
                label="Social Media Text",
                lines=4,
                placeholder="Example: I feel tired and alone lately..."
            )

            gr.Markdown("### Wearable Sensor Inputs")

            daily_steps = gr.Number(label="Daily Steps")
            sleep_hours = gr.Number(label="Sleep Hours")
            active_minutes = gr.Number(label="Active Minutes")
            daily_calories = gr.Number(label="Daily Calories")

            hr_avg_24h = gr.Number(label="Average Heart Rate (24h)")
            hrv_score_avg = gr.Number(label="HRV Score")
            stress_level_avg = gr.Number(label="Stress Level")
            sleep_hrv_score = gr.Number(label="Sleep HRV Score")

            predict_btn = gr.Button("Predict Depression Risk")

        with gr.Column():

            result = gr.Markdown()
            wearable_df = gr.Dataframe(label="Processed Wearable Features")

    predict_btn.click(
        sota_predict,
        inputs=[
            text_input,
            daily_steps,
            sleep_hours,
            active_minutes,
            daily_calories,
            hr_avg_24h,
            hrv_score_avg,
            stress_level_avg,
            sleep_hrv_score
        ],
        outputs=[result, wearable_df]
    )

demo.launch()