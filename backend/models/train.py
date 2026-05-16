import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms
from torchvision.models import EfficientNet_B0_Weights
from PIL import Image
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from tqdm import tqdm

IMG_SIZE = 224
NORM_MEAN = [0.485, 0.456, 0.406]
NORM_STD = [0.229, 0.224, 0.225]
CLASSES = ["Normal", "Tuberculosis"]
SUPPORTED_EXT = (".png", ".jpg", ".jpeg")
DEVICE = torch.device("cpu")


def resolve_dataset_root(path: str) -> str:
    candidates = [
        path,
        os.path.join(path, "TB_Chest_Radiography_Database"),
        os.path.join(path, "Tuberculosis Chest X-ray Dataset", "TB_Chest_Radiography_Database"),
    ]
    for c in candidates:
        if os.path.isdir(c) and all(os.path.isdir(os.path.join(c, cls)) for cls in CLASSES):
            return c
    raise FileNotFoundError(f"Cannot find TB_Chest_Radiography_Database with Normal/ and Tuberculosis/ under {path}")


class XRayDataset(Dataset):
    def __init__(self, image_paths, labels, transform=None):
        self.image_paths = image_paths
        self.labels = labels
        self.transform = transform

    @classmethod
    def from_folder(cls, root: str, max_per_class: int = 1500, transform=None):
        root = resolve_dataset_root(root)
        paths, labels = [], []
        for idx, cls_name in enumerate(CLASSES):
            cls_dir = os.path.join(root, cls_name)
            if not os.path.isdir(cls_dir):
                raise FileNotFoundError(f"Missing class directory: {cls_dir}")
            files = sorted(f for f in os.listdir(cls_dir) if f.lower().endswith(SUPPORTED_EXT))[:max_per_class]
            if not files:
                raise ValueError(f"No images found in {cls_dir}")
            for f in files:
                paths.append(os.path.join(cls_dir, f))
                labels.append(idx)
        return cls(paths, labels, transform)

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
        with Image.open(self.image_paths[idx]) as raw:
            img = raw.convert("RGB")
        if self.transform:
            img = self.transform(img)
        return img, self.labels[idx]


def build_model() -> nn.Module:
    model = models.efficientnet_b0(weights=EfficientNet_B0_Weights.IMAGENET1K_V1)
    for p in model.parameters():
        p.requires_grad = False
    for layer in [model.features[6], model.features[7], model.features[8]]:
        for p in layer.parameters():
            p.requires_grad = True
    in_features = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(0.3),
        nn.Linear(in_features, 256),
        nn.ReLU(),
        nn.Dropout(0.2),
        nn.Linear(256, len(CLASSES)),
    )
    return model.to(DEVICE)


def make_subset(dataset: XRayDataset, indices, transform=None):
    return XRayDataset(
        [dataset.image_paths[i] for i in indices],
        [dataset.labels[i] for i in indices],
        transform,
    )


def train(model, train_loader, val_loader, epochs, lr, save_path):
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()), lr=lr, weight_decay=1e-4
    )
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_acc = 0.0
    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": []}

    for epoch in range(1, epochs + 1):
        model.train()
        t_loss, t_correct, t_total = 0.0, 0, 0
        for imgs, lbls in tqdm(train_loader, desc=f"Epoch {epoch}/{epochs} [Train]"):
            imgs, lbls = imgs.to(DEVICE), lbls.to(DEVICE)
            optimizer.zero_grad()
            out = model(imgs)
            loss = criterion(out, lbls)
            loss.backward()
            optimizer.step()
            t_loss += loss.item() * imgs.size(0)
            t_correct += out.argmax(1).eq(lbls).sum().item()
            t_total += lbls.size(0)

        train_loss = t_loss / t_total
        train_acc = 100.0 * t_correct / t_total
        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)

        model.eval()
        v_loss, v_correct = 0.0, 0
        with torch.inference_mode():
            for imgs, lbls in val_loader:
                imgs, lbls = imgs.to(DEVICE), lbls.to(DEVICE)
                out = model(imgs)
                v_loss += criterion(out, lbls).item() * imgs.size(0)
                v_correct += out.argmax(1).eq(lbls).sum().item()

        v_total = len(val_loader.dataset)
        val_loss = v_loss / v_total
        val_acc = 100.0 * v_correct / v_total
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)

        print(f"Epoch {epoch} | Train Loss: {train_loss:.4f} Acc: {train_acc:.2f}% | Val Loss: {val_loss:.4f} Acc: {val_acc:.2f}%")
        scheduler.step()

        if val_acc > best_acc:
            best_acc = val_acc
            torch.save({"epoch": epoch, "state_dict": model.state_dict(), "val_acc": val_acc, "classes": CLASSES, "img_size": IMG_SIZE}, save_path)
            print(f"--> Saved best model (val_acc={best_acc:.2f}%)")

    return history, best_acc


def evaluate(model, test_loader, weights_path, report_path):
    ckpt = torch.load(weights_path, map_location="cpu")
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    preds, targets = [], []
    with torch.inference_mode():
        for imgs, lbls in tqdm(test_loader, desc="Evaluating"):
            out = model(imgs.to(DEVICE))
            preds.extend(out.argmax(1).cpu().tolist())
            targets.extend(lbls.tolist())

    report = classification_report(targets, preds, target_names=CLASSES)
    cm = confusion_matrix(targets, preds)
    print("\n--- Test Results ---\n", report)
    print("Confusion Matrix:\n", cm)

    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("Classification Report:\n")
        f.write(report)
        f.write("\nConfusion Matrix:\n")
        f.write(str(cm))


def save_plots(history, path):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].plot(history["train_acc"], label="Train Acc")
    axes[0].plot(history["val_acc"], label="Val Acc")
    axes[0].set_title("Accuracy")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Accuracy (%)")
    axes[0].legend()
    axes[1].plot(history["train_loss"], label="Train Loss")
    axes[1].plot(history["val_loss"], label="Val Loss")
    axes[1].set_title("Loss")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Loss")
    axes[1].legend()
    plt.tight_layout()
    plt.savefig(path, bbox_inches="tight")
    print(f"Plot saved to {path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="backend/models/dataset")
    parser.add_argument("--weights", default="backend/models/weights/efficientnet_tb.pth")
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-4)
    args = parser.parse_args()

    weights_dir = os.path.dirname(args.weights)
    os.makedirs(weights_dir, exist_ok=True)

    train_transform = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.RandomHorizontalFlip(0.3),
        transforms.RandomRotation(10),
        transforms.ColorJitter(brightness=0.2, contrast=0.2),
        transforms.ToTensor(),
        transforms.Normalize(NORM_MEAN, NORM_STD),
    ])
    val_transform = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(NORM_MEAN, NORM_STD),
    ])

    print("Loading dataset...")
    full = XRayDataset.from_folder(args.dataset, max_per_class=1500)

    indices = list(range(len(full)))
    train_idx, temp_idx, _, temp_lbl = train_test_split(
        indices, full.labels, train_size=0.7, stratify=full.labels, random_state=42
    )
    val_idx, test_idx = train_test_split(
        temp_idx, train_size=0.15 / 0.30, stratify=temp_lbl, random_state=42
    )[:2]

    train_loader = DataLoader(make_subset(full, train_idx, train_transform), batch_size=args.batch, shuffle=True, num_workers=0)
    val_loader   = DataLoader(make_subset(full, val_idx,   val_transform),   batch_size=args.batch, shuffle=False, num_workers=0)
    test_loader  = DataLoader(make_subset(full, test_idx,  val_transform),   batch_size=args.batch, shuffle=False, num_workers=0)

    model = build_model()
    history, best_acc = train(model, train_loader, val_loader, args.epochs, args.lr, args.weights)

    report_path = os.path.join(weights_dir, "class_report.txt")
    plot_path   = os.path.join(weights_dir, "training_report.png")
    info_path   = os.path.join(weights_dir, "model_info.json")

    evaluate(model, test_loader, args.weights, report_path)
    save_plots(history, plot_path)

    os.makedirs(weights_dir, exist_ok=True)
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump({
            "model": "efficientnet_b0",
            "classes": CLASSES,
            "img_size": IMG_SIZE,
            "val_accuracy": round(best_acc, 4),
            "epochs": args.epochs,
            "dataset": os.path.abspath(args.dataset),
        }, f, indent=2)

    print(f"\nBest val accuracy: {best_acc:.2f}%")
    print(f"Weights : {args.weights}")
    print(f"Report  : {report_path}")
    print(f"Plot    : {plot_path}")
    print(f"Info    : {info_path}")


if __name__ == "__main__":
    main()
