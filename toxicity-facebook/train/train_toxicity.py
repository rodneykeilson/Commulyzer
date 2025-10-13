"""Script pelatihan model klasifikasi toksisitas."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import torch  # type: ignore
from datasets import Dataset  # type: ignore
from sklearn.utils.class_weight import compute_class_weight  # type: ignore
from transformers import (  # type: ignore
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

import evaluate as hf_evaluate  # type: ignore

from utils.logger import get_logger

LOGGER = get_logger(__name__)
DEFAULT_MODEL_ID = "indolem/indobert-base-p1"
FALLBACK_MODEL_ID = "bert-base-uncased"


class WeightedLossTrainer(Trainer):
    """Trainer dengan dukungan class weight pada loss."""

    def __init__(self, *args: Any, class_weights: Optional[torch.Tensor] = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False):  # type: ignore
        labels = inputs.get("labels")
        outputs = model(**inputs)
        logits = outputs.get("logits")
        loss_fct = torch.nn.CrossEntropyLoss(weight=self.class_weights)
        loss = loss_fct(logits.view(-1, self.model.config.num_labels), labels.view(-1))
        return (loss, outputs) if return_outputs else loss


def _load_model(model_name: str) -> tuple:
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2)
        return tokenizer, model
    except Exception as exc:  # pragma: no cover - fallback network
        LOGGER.warning("Gagal memuat model %s (%s). Gunakan fallback %s", model_name, exc, FALLBACK_MODEL_ID)
        tokenizer = AutoTokenizer.from_pretrained(FALLBACK_MODEL_ID)
        model = AutoModelForSequenceClassification.from_pretrained(FALLBACK_MODEL_ID, num_labels=2)
        return tokenizer, model


def tokenize_function(examples, tokenizer, max_len: int):
    return tokenizer(examples["text_clean"], truncation=True, padding="max_length", max_length=max_len)


def load_dataset(csv_path: str) -> Dataset:
    df = pd.read_csv(csv_path)
    if "label" not in df.columns:
        raise ValueError("Kolom label wajib ada pada dataset train/val")
    df["label"] = df["label"].fillna(0).astype(int)
    return Dataset.from_pandas(df, preserve_index=False)


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    precision_metric = hf_evaluate.load("precision")
    recall_metric = hf_evaluate.load("recall")
    f1_metric = hf_evaluate.load("f1")
    precision = precision_metric.compute(predictions=preds, references=labels, average="binary")
    recall = recall_metric.compute(predictions=preds, references=labels, average="binary")
    f1 = f1_metric.compute(predictions=preds, references=labels, average="binary")
    return {
        "precision": precision.get("precision", 0.0),
        "recall": recall.get("recall", 0.0),
        "f1": f1.get("f1", 0.0),
    }


def train_model(args) -> Dict[str, Any]:
    tokenizer, model = _load_model(args.model_name)
    train_dataset = load_dataset(args.train_csv)
    val_dataset = load_dataset(args.val_csv)

    max_len = args.max_len

    tokenized_train = train_dataset.map(lambda x: tokenize_function(x, tokenizer, max_len), batched=True)
    tokenized_val = val_dataset.map(lambda x: tokenize_function(x, tokenizer, max_len), batched=True)

    for dataset in (tokenized_train, tokenized_val):
        dataset.set_format(type="torch", columns=["input_ids", "attention_mask", "label"])

    class_weights = None
    if args.class_weights:
        labels = np.array(train_dataset["label"])
        weights = compute_class_weight(class_weight="balanced", classes=np.unique(labels), y=labels)
        class_weights = torch.tensor(weights, dtype=torch.float)

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_dir=os.path.join(args.output_dir, "logs"),
        logging_steps=50,
        fp16=torch.cuda.is_available(),
    )

    trainer_cls = WeightedLossTrainer if class_weights is not None else Trainer
    trainer = trainer_cls(
        model=model,
        args=training_args,
        train_dataset=tokenized_train,
        eval_dataset=tokenized_val,
        tokenizer=tokenizer,
        compute_metrics=compute_metrics,
        class_weights=class_weights,
    )

    trainer.train()
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    LOGGER.info("Model terbaik tersimpan di %s", args.output_dir)

    metrics = trainer.evaluate()
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    with open(Path(args.output_dir) / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    LOGGER.info("Metode evaluasi: %s", metrics)
    return metrics


def predict_texts(model_path: str, texts: List[str]) -> Dict[str, List[float]]:
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    inputs = tokenizer(texts, padding=True, truncation=True, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1).cpu().numpy()
    scores = probs[:, 1].tolist()
    labels = [int(score >= 0.5) for score in scores]
    return {"scores": scores, "labels": labels}


def _parse_args():
    parser = argparse.ArgumentParser(description="Pelatihan model toksisitas berbasis Transformer.")
    parser.add_argument("--train_csv", required=True)
    parser.add_argument("--val_csv", required=True)
    parser.add_argument("--model_name", default=DEFAULT_MODEL_ID)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--max_len", type=int, default=128)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--class_weights", action="store_true")
    parser.add_argument("--use_weak_labels", action="store_true", help="Gunakan weak labels jika tersedia")
    parser.add_argument("--weak_labels_csv", help="CSV berisi weak labels untuk pretraining")
    parser.add_argument("--fast", action="store_true", help="Mode cepat untuk pengujian")
    return parser.parse_args()


def _maybe_apply_weak_labels(dataset: Dataset, weak_csv: Optional[str]) -> Dataset:
    if not weak_csv or not Path(weak_csv).exists():
        return dataset
    weak_df = pd.read_csv(weak_csv)
    if "label" not in weak_df.columns:
        LOGGER.warning("Weak label CSV tidak memiliki kolom label")
        return dataset
    combined = pd.concat([dataset.to_pandas(), weak_df], ignore_index=True)
    return Dataset.from_pandas(combined, preserve_index=False)


def main() -> None:
    args = _parse_args()
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    if args.fast:
        args.epochs = 1
        args.batch_size = max(2, args.batch_size)

    if args.use_weak_labels and args.weak_labels_csv:
        dataset = load_dataset(args.train_csv)
        dataset = _maybe_apply_weak_labels(dataset, args.weak_labels_csv)
        dataset.to_pandas().to_csv(args.train_csv, index=False)

    train_model(args)


if __name__ == "__main__":
    main()
