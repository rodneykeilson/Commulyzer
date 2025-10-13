"""Klien sederhana untuk memanggil API toksisitas."""
from __future__ import annotations

import argparse
import json
import os
from typing import List

import requests  # type: ignore


def call_predict(endpoint: str, texts: List[str], api_key: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    response = requests.post(endpoint, headers=headers, data=json.dumps({"texts": texts}), timeout=30)
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Klien untuk endpoint /predict.")
    parser.add_argument("--endpoint", default="http://localhost:8000/predict")
    parser.add_argument("--texts", nargs="*", default=["Komunitas ini toxic"], help="Teks untuk diprediksi")
    args = parser.parse_args()

    api_key = os.getenv("API_KEY")
    result = call_predict(args.endpoint, args.texts, api_key)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
