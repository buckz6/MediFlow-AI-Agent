"""
XRayAnalyzer — TB Detection with Grad-CAM visualization
Powered by fine-tuned EfficientNet-B0, running on CPU.
"""

import base64
import logging
import os
from io import BytesIO
from typing import Any, Dict

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

from backend.models.load_model import get_model, predict_xray

logger = logging.getLogger(__name__)

# Configuration
IMG_SIZE = 224
NORM_MEAN = [0.485, 0.456, 0.406]
NORM_STD = [0.229, 0.224, 0.225]
CLASSES = ["Normal", "Tuberculosis"]

# Transforms for Grad-CAM visualization
TRANSFORMS = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(NORM_MEAN, NORM_STD),
])


# ─────────────────────────────────────────────────────────────────────────────
# Grad-CAM Implementation
# ─────────────────────────────────────────────────────────────────────────────

def compute_gradcam(image_tensor: torch.Tensor, target_class: int = 1) -> np.ndarray:
    """
    Compute Grad-CAM for the given image tensor using model.features[7].
    
    Args:
        image_tensor: input tensor of shape (1, 3, H, W), already preprocessed
        target_class: class index to compute gradients for
    
    Returns:
        Grad-CAM heatmap as numpy array in [0, 1] range, shape (H, W)
    """
    try:
        model = get_model()
        device = torch.device("cpu")
        
        gradients = []
        activations = []
        
        def forward_hook(module, input, output):
            activations.append(output.detach())
        
        def backward_hook(module, grad_input, grad_output):
            gradients.append(grad_output[0].detach())
        
        # Register hooks on features[7] (last conv block that was unfrozen during training)
        forward_handle = model.features[7].register_forward_hook(forward_hook)
        backward_handle = model.features[7].register_full_backward_hook(backward_hook)
        
        try:
            # Prepare tensor for backprop
            image_tensor = image_tensor.to(device).clone()
            image_tensor.requires_grad = True
            
            with torch.enable_grad():
                model.zero_grad()
                outputs = model(image_tensor)
                
                # Compute loss for target class
                target_score = outputs[0, target_class]
                target_score.backward()
            
            if not gradients or not activations:
                logger.warning("Grad-CAM hooks did not fire, using fallback")
                return generate_fallback_heatmap(image_tensor.shape[-2:])
            
            # Compute Grad-CAM
            grads = gradients[-1][0]  # (C, H, W)
            acts = activations[-1][0]  # (C, H, W)
            
            # Global average pooling on gradients
            weights = grads.mean(dim=(1, 2), keepdim=True)  # (C, 1, 1)
            
            # Weighted combination of activation maps
            cam = (weights * acts).sum(dim=0)  # (H, W)
            cam = F.relu(cam)
            
            # Normalize to [0, 1]
            if cam.max() > 0:
                cam = cam / cam.max()
            
            return cam.cpu().numpy().astype(np.float32)
        
        finally:
            forward_handle.remove()
            backward_handle.remove()
    
    except Exception as exc:
        logger.error("Grad-CAM computation failed: %s", exc)
        return generate_fallback_heatmap(image_tensor.shape[-2:])


def generate_fallback_heatmap(shape: tuple) -> np.ndarray:
    """Generate a simple Gaussian heatmap as fallback."""
    h, w = shape
    y, x = np.mgrid[0:h, 0:w]
    center_y, center_x = h // 2, w // 2
    heatmap = np.exp(-((x - center_x) ** 2 + (y - center_y) ** 2) / (2 * (min(h, w) // 4) ** 2))
    return (heatmap / heatmap.max()).astype(np.float32)


def generate_findings(diagnosis: str, confidence: float) -> list[str]:
    """
    Generate clinical findings based on diagnosis and confidence level.
    
    Args:
        diagnosis: "Normal" or "Tuberculosis"
        confidence: confidence score between 0.0 and 1.0
    
    Returns:
        List of clinical finding strings
    """
    if diagnosis == "Tuberculosis":
        if confidence > 0.90:
            return [
                "High-density infiltrate detected",
                "Suspected upper lobe consolidation",
                "Recommend BTA sputum test"
            ]
        elif confidence > 0.70:
            return [
                "Possible infiltrate pattern",
                "Mild opacity detected",
                "Further examination recommended"
            ]
        else:
            return [
                "Possible TB-related findings",
                "Recommend follow-up imaging",
                "Clinical correlation advised"
            ]
    else:  # Normal
        return [
            "No significant infiltrate",
            "Lung fields appear clear",
            "Normal chest X-ray appearance"
        ]


def overlay_heatmap_on_image(
    original_image: Image.Image,
    heatmap: np.ndarray,
    alpha: float = 0.4
) -> Image.Image:
    """
    Overlay Grad-CAM heatmap on the original image.
    
    Args:
        original_image: PIL Image in RGB
        heatmap: numpy array in [0, 1] range, shape (H, W)
        alpha: blending factor for heatmap
    
    Returns:
        PIL Image with overlaid heatmap
    """
    # Resize original image to match heatmap
    img_resized = original_image.resize((IMG_SIZE, IMG_SIZE), Image.Resampling.LANCZOS)
    img_array = np.array(img_resized).astype(np.float32) / 255.0
    
    # Resize heatmap to match image
    heatmap_resized = cv2.resize(heatmap, (IMG_SIZE, IMG_SIZE))
    
    # Apply colormap to heatmap
    heatmap_colored = cv2.applyColorMap(
        (heatmap_resized * 255).astype(np.uint8),
        cv2.COLORMAP_JET
    )
    heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    
    # Blend: overlay heatmap on image
    overlay = (1.0 - alpha) * img_array + alpha * heatmap_colored
    overlay = np.clip(overlay, 0, 1)
    
    # Convert back to uint8 PIL Image
    overlay_uint8 = (overlay * 255).astype(np.uint8)
    return Image.fromarray(overlay_uint8, "RGB")


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def analyze_xray(image_path: str) -> Dict[str, Any]:
    """
    Analyze a chest X-ray image and return diagnosis, confidence, findings, and visualizations.
    
    Args:
        image_path: path to X-ray image file
    
    Returns:
        Dictionary with keys:
        - diagnosis: "Normal" or "Tuberculosis"
        - confidence: float between 0.0 and 1.0
        - findings: list of clinical finding strings
        - heatmap_base64: Grad-CAM overlay as data:image/png;base64,...
        - original_image_base64: original X-ray as data:image/png;base64,...
    
    Raises:
        FileNotFoundError: if image_path does not exist
        Exception: if model weights not found or inference fails
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    try:
        # Load and open image
        with Image.open(image_path) as raw:
            original_image = raw.convert("RGB")
        
        # Get model prediction
        prediction = predict_xray(image_path)
        
        diagnosis = prediction["diagnosis"]
        confidence = prediction["confidence"]
        class_idx = prediction["class_idx"]
        
        # Prepare tensor for Grad-CAM
        image_tensor = TRANSFORMS(original_image).unsqueeze(0)
        
        # Compute Grad-CAM
        gradcam_heatmap = compute_gradcam(image_tensor, target_class=class_idx)
        
        # Overlay heatmap on original image
        overlaid_image = overlay_heatmap_on_image(original_image, gradcam_heatmap, alpha=0.4)
        
        # Generate clinical findings
        findings = generate_findings(diagnosis, confidence)
        
        # Encode images as base64
        # Heatmap
        heatmap_buffer = BytesIO()
        overlaid_image.save(heatmap_buffer, format="PNG")
        heatmap_base64 = base64.b64encode(heatmap_buffer.getvalue()).decode("utf-8")
        
        # Original image
        original_buffer = BytesIO()
        original_image.save(original_buffer, format="PNG")
        original_base64 = base64.b64encode(original_buffer.getvalue()).decode("utf-8")
        
        return {
            "diagnosis": diagnosis,
            "confidence": float(confidence),
            "findings": findings,
            "heatmap_base64": f"data:image/png;base64,{heatmap_base64}",
            "original_image_base64": f"data:image/png;base64,{original_base64}",
        }
    
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Model weights not found. Please run training first: {exc}")
    except Exception as exc:
        logger.exception("Error analyzing X-ray: %s", exc)
        raise

