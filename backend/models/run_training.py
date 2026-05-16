"""
MediFlow — Windows Training Runner
Jalankan: python backend/models/run_training.py
Pengganti train.sh untuk Windows (PowerShell)
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Warna untuk PowerShell
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
NC     = "\033[0m"

def print_header():
    print(f"{BLUE}")
    print("  ╔══════════════════════════════════════════╗")
    print("  ║   MediFlow TB Detection — Training       ║")
    print("  ║   Dataset: TB Chest X-ray (Kaggle)       ║")
    print("  ╚══════════════════════════════════════════╝")
    print(f"{NC}")

def run(cmd, check=True):
    result = subprocess.run(cmd, shell=True)
    if check and result.returncode != 0:
        print(f"{RED}❌ Command gagal: {cmd}{NC}")
        sys.exit(1)
    return result.returncode

def setup_kaggle():
    print(f"{BLUE}[1/4] Mengecek Kaggle credentials...{NC}")
    
    kaggle_dir  = Path.home() / ".kaggle"
    kaggle_json = kaggle_dir / "kaggle.json"
    
    if kaggle_json.exists():
        print(f"{GREEN}✅ kaggle.json sudah ada{NC}")
        return

    print(f"{YELLOW}kaggle.json belum ditemukan.{NC}")
    print()
    print("Buka: https://www.kaggle.com → Account → Settings → API → Create New Token")
    print()
    username = input("Masukkan Kaggle USERNAME : ").strip()
    
    import getpass
    api_key  = getpass.getpass("Masukkan Kaggle API KEY  : ").strip()

    kaggle_dir.mkdir(parents=True, exist_ok=True)
    kaggle_json.write_text(
        json.dumps({"username": username, "key": api_key}),
        encoding="utf-8"
    )
    # Windows tidak punya chmod, tapi file sudah aman di user folder
    print(f"{GREEN}✅ kaggle.json berhasil dibuat di {kaggle_json}{NC}")

def install_deps():
    print(f"\n{BLUE}[2/4] Install dependencies...{NC}")
    run(f"{sys.executable} -m pip install torch torchvision scikit-learn "
        f"tqdm pillow pandas matplotlib kaggle -q")
    print(f"{GREEN}✅ Dependencies siap{NC}")

def download_dataset():
    print(f"\n{BLUE}[3/4] Download dataset TB Chest X-ray (~130MB)...{NC}")

    dataset_dir = Path("backend/models/dataset/TB_Chest_Radiography_Database")
    normal_dir  = dataset_dir / "Normal"
    tb_dir      = dataset_dir / "Tuberculosis"

    if normal_dir.exists() and tb_dir.exists():
        n_normal = len(list(normal_dir.glob("*.png"))) + len(list(normal_dir.glob("*.jpg")))
        n_tb     = len(list(tb_dir.glob("*.png")))     + len(list(tb_dir.glob("*.jpg")))
        if n_normal > 100 and n_tb > 100:
            print(f"{GREEN}✅ Dataset sudah ada: {n_normal} Normal, {n_tb} TB{NC}")
            return

    print("   Mendownload dari Kaggle...")
    run(f"{sys.executable} -m kaggle datasets download "
        f"-d tawsifurrahman/tuberculosis-tb-chest-xray-dataset "
        f"--path backend/models/dataset/ --unzip -q")
    print(f"{GREEN}✅ Dataset berhasil didownload{NC}")

def run_training():
    print(f"\n{BLUE}[4/4] Memulai training...{NC}")
    print("   Estimasi waktu: 2–3 jam di CPU. Bisa ditinggal.\n")
    run(f"{sys.executable} backend/models/train.py")

def print_result():
    info_path = Path("backend/models/weights/model_info.json")
    if not info_path.exists():
        print(f"{RED}❌ model_info.json tidak ditemukan{NC}")
        return

    with open(info_path) as f:
        info = json.load(f)

    acc = info.get("val_accuracy", 0) * 100

    print()
    if acc > 80:
        color = GREEN
        label = "✅ TRAINING SUKSES"
    elif acc > 70:
        color = YELLOW
        label = "⚠️  TRAINING SELESAI (cukup untuk demo)"
    else:
        color = RED
        label = "❌ AKURASI RENDAH (perlu lebih banyak data)"

    print(f"{color}{'='*45}")
    print(f"  {label}")
    print(f"  Val Accuracy : {acc:.1f}%")
    print(f"  Weights      : backend/models/weights/efficientnet_tb.pth")
    print(f"  Plot         : backend/models/weights/training_report.png")
    print(f"  Report       : backend/models/weights/class_report.txt")
    print(f"{'='*45}{NC}")
    print()
    print("Langkah selanjutnya:")
    print("  docker-compose up --build")

if __name__ == "__main__":
    print_header()
    setup_kaggle()
    install_deps()
    download_dataset()
    run_training()
    print_result()