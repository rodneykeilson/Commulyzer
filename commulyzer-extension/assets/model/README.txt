Copy the Commulyzer baseline JSON artifacts into this directory before building the extension.

Required files:
- metadata.json
- labels.txt
- thresholds.json
- classifier_coefficients.json
- classifier_intercepts.json
- vocabulary_combined.json

Use `python export_baseline_to_json.py --artifacts-dir outputs/models/baseline --output-dir commulyzer-extension/assets/model` to generate them or copy from `app/assets/model/`.
