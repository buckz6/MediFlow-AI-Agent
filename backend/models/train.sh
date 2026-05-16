#!/bin/bash
set -euo pipefail

KAGGLE_JSON="$HOME/.kaggle/kaggle.json"
DATASET_DIR="backend/models/dataset"
DATASET_ROOT="$DATASET_DIR/TB_Chest_Radiography_Database"
WEIGHTS_DIR="backend/models/weights"
MODEL_INFO="$WEIGHTS_DIR/model_info.json"

# --- Kaggle credentials ---
if [ ! -f "$KAGGLE_JSON" ]; then
    echo "--- Kaggle API Credentials Not Found ---"
    mkdir -p "$HOME/.kaggle"
    read -rp "Enter Kaggle Username: " KAGGLE_USERNAME
    read -rsp "Enter Kaggle API Key: " KAGGLE_KEY
    echo
    printf '{"username":"%s","key":"%s"}\n' "$KAGGLE_USERNAME" "$KAGGLE_KEY" > "$KAGGLE_JSON"
    chmod 600 "$KAGGLE_JSON"
    echo "Saved credentials to $KAGGLE_JSON"
fi

# --- Dependencies ---
echo "--- Installing Dependencies ---"
pip install torch torchvision scikit-learn tqdm pillow pandas matplotlib kaggle -q

# --- Dataset ---
if [ ! -d "$DATASET_ROOT/Normal" ] || [ ! -d "$DATASET_ROOT/Tuberculosis" ]; then
    echo "--- Downloading Dataset ---"
    mkdir -p "$DATASET_DIR"
    kaggle datasets download -d tawsifurrahman/tuberculosis-tb-chest-xray-dataset \
        --path "$DATASET_DIR" --unzip -q
else
    echo "--- Dataset already exists, skipping download ---"
fi

# --- Training ---
echo "--- Running Training ---"
python backend/models/train.py

# --- Summary ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

if [ -f "$MODEL_INFO" ]; then
    VAL_ACC=$(python3 -c "import json; d=json.load(open('$MODEL_INFO')); print(d['val_accuracy'])")
    ACC_INT=$(printf "%.0f" "$VAL_ACC")
    echo
    if [ "$ACC_INT" -ge 80 ]; then
        echo -e "${GREEN}TRAINING SUCCESS - Val Accuracy: ${VAL_ACC}%${NC}"
    elif [ "$ACC_INT" -ge 70 ]; then
        echo -e "${YELLOW}TRAINING DONE - Val Accuracy: ${VAL_ACC}% (acceptable)${NC}"
    else
        echo -e "${RED}LOW ACCURACY - Val Accuracy: ${VAL_ACC}% (need more data)${NC}"
    fi
else
    echo -e "${RED}ERROR: $MODEL_INFO not found. Training may have failed.${NC}"
    exit 1
fi
