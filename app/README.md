# Commulyzer App

This directory hosts the Expo + React Native client for running Commulyzer's baseline toxicity detector entirely on-device.

## Getting Started

```powershell
cd app
npm install
npm run start
```

Expo CLI opens the developer tools. Press `a` to launch Android, `i` for iOS (on macOS), or `w` to open the web preview.

## Model Assets

Copy the JSON exports from `artifacts/baseline/json/` into `app/assets/model/` before running the app. The loader expects:

- `metadata.json`
- `labels.txt`
- `thresholds.json`
- `classifier_coefficients.json`
- `classifier_intercepts.json`
- `vocabulary_combined.json`

Large vocabulary shards are optional once `vocabulary_combined.json` is present.

## Next Steps

- Implement the TF–IDF + logistic regression pipeline in TypeScript under `src/model/`.
- Add UI for pasting text and displaying per-label scores/thresholded tags.
- Package the inference layer for reuse across mobile and desktop shells.
