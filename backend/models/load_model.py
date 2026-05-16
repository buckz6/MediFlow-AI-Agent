import os

import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image

_model = None
CLASSES = ["Normal", "Tuberculosis"]
IMG_SIZE = 224
NORM_MEAN = [0.485, 0.456, 0.406]
NORM_STD = [0.229, 0.224, 0.225]
WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "weights", "efficientnet_tb.pth")

_transform = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(NORM_MEAN, NORM_STD),
])


def _build_model() -> nn.Module:
    model = models.efficientnet_b0(weights=None)
    in_features = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(0.3),
        nn.Linear(in_features, 256),
        nn.ReLU(),
        nn.Dropout(0.2),
        nn.Linear(256, len(CLASSES)),
    )
    return model


def get_model() -> nn.Module:
    """Load once, reuse forever across requests."""
    global _model
    if _model is not None:
        return _model

    if not os.path.exists(WEIGHTS_PATH):
        raise FileNotFoundError(
            f"Weights not found at {WEIGHTS_PATH}. Run backend/models/train.py first."
        )

    torch.set_num_threads(2)
    model = _build_model()
    ckpt = torch.load(WEIGHTS_PATH, map_location="cpu")
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    _model = model
    return _model


def predict_xray(image_path: str) -> dict:
    """Single image inference."""
    with Image.open(image_path) as raw:
        img = raw.convert("RGB")

    tensor = _transform(img).unsqueeze(0)

    with torch.inference_mode():
        logits = get_model()(tensor)
        probs = torch.softmax(logits, dim=1)[0]

    class_idx = int(probs.argmax().item())
    confidence = round(float(probs[class_idx].item()), 4)

    return {
        "diagnosis": CLASSES[class_idx],
        "confidence": confidence,
        "class_idx": class_idx,
        "probabilities": {CLASSES[i]: round(float(probs[i].item()), 4) for i in range(len(CLASSES))},
    }
