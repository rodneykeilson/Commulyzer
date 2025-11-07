# Commulyzer Browser Extension

This extension scans the visible text on any page, runs Commulyzer's baseline toxicity classifier locally, and replaces sentences that exceed the learned toxicity thresholds with explanatory placeholders such as:

```
<this sentence was removed for toxic, obscene>
```

All inference happens in the browser using the exported TF–IDF + logistic regression artifacts. No network calls or server components are required.

## Project Structure

- `manifest.json` – Chrome/Chromium Manifest V3 descriptor (also compatible with Firefox Nightly MV3).
- `src/` – source TypeScript/JavaScript modules.
  - `content.ts` – entry point injected into every page.
  - `model/` – TF–IDF helpers and inference logic.
- `assets/model/` – copy of the Commulyzer baseline JSON artifacts (same bundle used by the mobile app).
- `dist/` – compiled content script emitted by the build step.
- `package.json` / `tsconfig.json` – tooling configuration for bundling with esbuild.

## Getting Started

```powershell
cd commulyzer-extension
npm install
npm run build
```

Before building, export the baseline model to JSON:

```powershell
python export_baseline_to_json.py --artifacts-dir outputs/models/baseline --output-dir commulyzer-extension/assets/model
```

Alternatively copy the bundle already present under `app/assets/model/`.

After `npm run build`, load the `commulyzer-extension` folder as an unpacked extension in Chrome/Edge or follow the MV3 workflow for Firefox Nightly.

## How It Works

1. The content script lazily loads the artifacts from `chrome.runtime.getURL(...)`.
2. It walks the DOM with a `TreeWalker`, collecting text nodes and splitting them into sentences.
3. Each sentence is vectorised with the TF–IDF parameters and scored using logistic regression.
4. Sentences whose probabilities exceed any label threshold are replaced in-place with a placeholder that names the triggered labels.
5. A mutation observer reprocesses dynamically inserted content (e.g. infinite scroll feeds) with a debounce guard.

## Development Scripts

- `npm run build` – compile the TypeScript source into `dist/content.js`.
- `npm run watch` – rebuild on changes for easier iteration.
- `npm run lint` – run ESLint on the extension source.

## Notes

- The bundled artifacts can be large (vocabulary JSON is ~20 MB). Chrome can load large static assets but initial processing may take a few seconds on low-end hardware.
- Replace the placeholder icon under `icons/icon128.png` with your preferred artwork before distributing the extension.
- All detection happens client-side; respect site terms of service when modifying page content.
