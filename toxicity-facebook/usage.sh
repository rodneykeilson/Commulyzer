#!/usr/bin/env bash
set -euo pipefail

# Skrip contoh untuk menjalankan pipeline secara berurutan.
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Smoke test dengan dataset sampel
python preprocess/clean.py --in data/sample/sample_raw.jsonl --out data/sample/sample_processed.csv --fast
python train/train_toxicity.py --train_csv data/sample/train.csv --val_csv data/sample/val.csv --output_dir models/best --epochs 1 --batch_size 4 --fast
python eval/evaluate.py --model_path models/best --test_csv data/sample/val.csv --query "Sample"

# Pipeline penuh (ubah sesuai kebutuhan)
# python -m scrapers.cli --query "Mobile Legends" --discover --max-posts 500 --out data/raw/mobilelegends_raw.jsonl
# python preprocess/clean.py --in data/raw/mobilelegends_raw.jsonl --out data/processed/mobilelegends_items.csv
# python labeling/prepare_annotation.py --in data/processed/mobilelegends_items.csv --sample 500 --out labeling/to_label.csv
# python train/train_toxicity.py --train_csv data/sample/train.csv --val_csv data/sample/val.csv --output_dir models/best
# uvicorn api.app:app --host 0.0.0.0 --port 8000
