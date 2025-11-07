// src/model/artifacts.ts
var cachedArtifacts;
function getAssetUrl(file) {
  const runtime = globalThis.chrome;
  if (runtime?.runtime?.getURL) {
    return runtime.runtime.getURL(`assets/model/${file}`);
  }
  return `assets/model/${file}`;
}
async function fetchJson(file) {
  const response = await fetch(getAssetUrl(file));
  if (!response.ok) {
    throw new Error(`Failed to load ${file}: ${response.status} ${response.statusText}`);
  }
  return response.json();
}
async function fetchText(file) {
  const response = await fetch(getAssetUrl(file));
  if (!response.ok) {
    throw new Error(`Failed to load ${file}: ${response.status} ${response.statusText}`);
  }
  return response.text();
}
function coerceVectorizer(config) {
  if (!config) {
    throw new Error("Vectorizer metadata missing.");
  }
  const ngram = config.ngram_range;
  const rawRange = Array.isArray(ngram) ? ngram.map((value) => Number(value)) : [1, 1];
  const minN = Number.isFinite(rawRange[0]) ? Number(rawRange[0]) : 1;
  const maxN = Number.isFinite(rawRange[1]) ? Number(rawRange[1]) : minN;
  const idfSource = config.idf;
  const idfValues = Array.isArray(idfSource) ? idfSource.map((value) => Number(value)) : [];
  return {
    ngramRange: [minN, maxN],
    lowercase: Boolean(config.lowercase),
    useIdf: Boolean(config.use_idf),
    smoothIdf: Boolean(config.smooth_idf),
    sublinearTf: Boolean(config.sublinear_tf),
    norm: config.norm === "l1" || config.norm === "l2" ? config.norm : null,
    binary: Boolean(config.binary),
    minDf: Number(config.min_df ?? 1),
    maxDf: Number(config.max_df ?? 1),
    tokenPattern: typeof config.token_pattern === "string" ? config.token_pattern : null,
    stopWords: Array.isArray(config.stop_words) ? config.stop_words.map((v) => String(v)) : null,
    idf: idfValues,
    vocabularySize: Number(config.vocabulary_size ?? idfValues.length),
    documentCount: typeof config.document_count === "number" ? config.document_count : void 0
  };
}
async function loadArtifacts() {
  if (cachedArtifacts) {
    return cachedArtifacts;
  }
  const metadata = await fetchJson("metadata.json");
  const vectorizerSource = metadata?.vectorizer ?? metadata;
  const vectorizer = coerceVectorizer(vectorizerSource);
  const thresholds = await fetchJson("thresholds.json").catch(() => {
    if (metadata?.thresholds) {
      return metadata.thresholds;
    }
    console.warn("Falling back to thresholds embedded in metadata.json");
    return {};
  });
  const labelsRaw = await fetchText("labels.txt").catch(() => "").then((text) => text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean));
  const metadataLabels = Array.isArray(metadata?.labels) ? metadata.labels.filter((label) => typeof label === "string") : [];
  const labels = labelsRaw.length > 0 ? labelsRaw : metadataLabels.length > 0 ? metadataLabels : Object.keys(thresholds);
  const coefficients = await fetchJson("classifier_coefficients.json");
  const intercepts = await fetchJson("classifier_intercepts.json");
  const vocabularyObj = await fetchJson("vocabulary_combined.json");
  const vocabulary = new Map(Object.entries(vocabularyObj));
  if (labels.length === 0) {
    throw new Error("No labels found in artifacts.");
  }
  if (coefficients.length !== labels.length || intercepts.length !== labels.length) {
    throw new Error("Classifier tensors do not match the number of labels.");
  }
  if (vocabulary.size === 0) {
    throw new Error("Vocabulary file appears empty.");
  }
  cachedArtifacts = {
    vectorizer,
    coefficients,
    intercepts,
    vocabulary,
    thresholds,
    labels
  };
  return cachedArtifacts;
}

// src/model/inference.ts
var DEFAULT_TOKEN_REGEX = createDefaultTokenRegex();
function createDefaultTokenRegex() {
  try {
    return new RegExp("[\\p{L}\\p{N}_]{2,}", "gu");
  } catch {
    return /[A-Za-z0-9_]{2,}/g;
  }
}
function getTokenRegex(metadata) {
  if (!metadata.tokenPattern) {
    return DEFAULT_TOKEN_REGEX;
  }
  const raw = metadata.tokenPattern.startsWith("(?u)") ? metadata.tokenPattern.slice(4) : metadata.tokenPattern;
  try {
    return new RegExp(raw, "gu");
  } catch (error) {
    console.warn("Falling back to default token regex", error);
    return DEFAULT_TOKEN_REGEX;
  }
}
function normalise(text, lowercase) {
  const stripped = text.replace(/[\r\n]+/g, " ").replace(/\s+/g, " ").trim();
  return lowercase ? stripped.toLowerCase() : stripped;
}
function tokenize(text, metadata) {
  const regex = getTokenRegex(metadata);
  const tokens = [];
  const processed = metadata.lowercase ? text.toLowerCase() : text;
  let match;
  while ((match = regex.exec(processed)) !== null) {
    if (match[0]) {
      tokens.push(match[0]);
    }
    if (!regex.global) {
      break;
    }
  }
  if (metadata.stopWords && metadata.stopWords.length > 0) {
    const stopSet = new Set(
      metadata.stopWords.map(
        (word) => metadata.lowercase ? String(word).toLowerCase() : String(word)
      )
    );
    return tokens.filter((token) => !stopSet.has(token));
  }
  return tokens;
}
function buildFeatures(text, metadata, vocabulary) {
  const cleaned = normalise(text, false);
  const tokens = tokenize(cleaned, metadata);
  const [minN, maxN] = metadata.ngramRange;
  const counts = /* @__PURE__ */ new Map();
  for (let n = minN; n <= maxN; n += 1) {
    if (n <= 0 || tokens.length < n) {
      continue;
    }
    for (let i = 0; i <= tokens.length - n; i += 1) {
      const ngram = tokens.slice(i, i + n).join(" ");
      const index = vocabulary.get(ngram);
      if (typeof index !== "number" || Number.isNaN(index)) {
        continue;
      }
      const prev = counts.get(index) ?? 0;
      counts.set(index, prev + 1);
    }
  }
  if (counts.size === 0) {
    return counts;
  }
  const features = /* @__PURE__ */ new Map();
  counts.forEach((frequency, index) => {
    let tf = metadata.binary ? frequency > 0 ? 1 : 0 : frequency;
    if (!metadata.binary && metadata.sublinearTf && tf > 0) {
      tf = 1 + Math.log(tf);
    }
    let value = tf;
    if (metadata.useIdf && metadata.idf[index] !== void 0) {
      value *= metadata.idf[index];
    }
    features.set(index, value);
  });
  if (metadata.norm === "l2") {
    let norm = 0;
    features.forEach((value) => {
      norm += value * value;
    });
    if (norm > 0) {
      const scale = 1 / Math.sqrt(norm);
      features.forEach((value, key) => {
        features.set(key, value * scale);
      });
    }
  } else if (metadata.norm === "l1") {
    let norm = 0;
    features.forEach((value) => {
      norm += Math.abs(value);
    });
    if (norm > 0) {
      const scale = 1 / norm;
      features.forEach((value, key) => {
        features.set(key, value * scale);
      });
    }
  }
  return features;
}
function sigmoid(z) {
  if (z >= 0) {
    const expNeg = Math.exp(-z);
    return 1 / (1 + expNeg);
  }
  const expPos = Math.exp(z);
  return expPos / (1 + expPos);
}
function scoreText(text, artifacts) {
  const featureVector = text ? buildFeatures(text, artifacts.vectorizer, artifacts.vocabulary) : /* @__PURE__ */ new Map();
  const rawScores = {};
  const activeLabels = [];
  const triggered = {};
  artifacts.labels.forEach((label, classIndex) => {
    const weights = artifacts.coefficients[classIndex] ?? [];
    let score = artifacts.intercepts[classIndex] ?? 0;
    featureVector.forEach((value, featureIndex) => {
      if (featureIndex < weights.length) {
        score += value * (weights[featureIndex] ?? 0);
      }
    });
    const probability = sigmoid(score);
    rawScores[label] = probability;
    const threshold = artifacts.thresholds[label] ?? 0.5;
    if (probability >= threshold) {
      activeLabels.push(label);
      triggered[label] = probability;
    }
  });
  return { rawScores, activeLabels, triggered };
}

// src/content.ts
var processedNodes = /* @__PURE__ */ new WeakSet();
var observer;
var scheduled = false;
var artifactsPromise;
function splitSentences(text) {
  const matches = text.match(/[^.!?\n\r]+[.!?\u2026]*\s*/g);
  if (!matches) {
    return [text];
  }
  return matches;
}
function injectStyles() {
  if (document.getElementById("commulyzer-style")) {
    return;
  }
  const style = document.createElement("style");
  style.id = "commulyzer-style";
  style.textContent = `
    .commulyzer-mask {
      background-color: rgba(248, 113, 113, 0.15);
      color: #b91c1c;
      font-style: italic;
      border-radius: 0.25rem;
      padding: 0.1rem 0.2rem;
    }
  `;
  document.head.appendChild(style);
}
async function getArtifacts() {
  if (!artifactsPromise) {
    artifactsPromise = loadArtifacts();
  }
  return artifactsPromise;
}
function createPlaceholder(labels, trailingWhitespace) {
  const span = document.createElement("span");
  span.className = "commulyzer-mask";
  span.setAttribute("data-commulyzer", "placeholder");
  const reason = labels.join(", ");
  span.textContent = `<this sentence was removed for ${reason}>${trailingWhitespace}`;
  processedNodes.add(span);
  return span;
}
function analyseTextNode(node, artifacts) {
  if (processedNodes.has(node)) {
    return;
  }
  const original = node.textContent ?? "";
  if (!original.trim()) {
    processedNodes.add(node);
    return;
  }
  const sentences = splitSentences(original);
  let modified = false;
  const fragments = [];
  sentences.forEach((segment) => {
    const trimmed = segment.trim();
    if (!trimmed) {
      const textNode = document.createTextNode(segment);
      processedNodes.add(textNode);
      fragments.push(textNode);
      return;
    }
    const result = scoreText(trimmed, artifacts);
    if (result.activeLabels.length === 0) {
      const cleanNode = document.createTextNode(segment);
      processedNodes.add(cleanNode);
      fragments.push(cleanNode);
      return;
    }
    modified = true;
    const trailing = segment.match(/\s+$/)?.[0] ?? "";
    fragments.push(createPlaceholder(result.activeLabels, trailing));
  });
  if (!modified) {
    processedNodes.add(node);
    return;
  }
  const fragment = document.createDocumentFragment();
  fragments.forEach((child) => {
    fragment.appendChild(child);
  });
  const parent = node.parentNode;
  if (!parent) {
    return;
  }
  parent.replaceChild(fragment, node);
}
function walkAndAnalyse(root, artifacts) {
  const treeWalker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (processedNodes.has(node)) {
        return NodeFilter.FILTER_REJECT;
      }
      const parent = node.parentElement;
      if (!parent) {
        return NodeFilter.FILTER_REJECT;
      }
      if (parent.closest('[data-commulyzer="placeholder"]')) {
        return NodeFilter.FILTER_REJECT;
      }
      const tagName = parent.tagName;
      if (tagName === "SCRIPT" || tagName === "STYLE" || tagName === "NOSCRIPT" || tagName === "TEXTAREA" || tagName === "INPUT") {
        return NodeFilter.FILTER_REJECT;
      }
      if (parent.isContentEditable) {
        return NodeFilter.FILTER_REJECT;
      }
      const text = node.textContent ?? "";
      if (!/\w/.test(text)) {
        return NodeFilter.FILTER_SKIP;
      }
      return NodeFilter.FILTER_ACCEPT;
    }
  });
  let current = treeWalker.nextNode();
  while (current) {
    analyseTextNode(current, artifacts);
    current = treeWalker.nextNode();
  }
}
async function performScan() {
  scheduled = false;
  try {
    const artifacts = await getArtifacts();
    const body = document.body;
    if (body) {
      walkAndAnalyse(body, artifacts);
    }
  } catch (error) {
    console.error("Commulyzer failed to load artifacts:", error);
    observer?.disconnect();
  }
}
function scheduleScan() {
  if (scheduled) {
    return;
  }
  scheduled = true;
  setTimeout(() => {
    void performScan();
  }, 250);
}
function startObserver() {
  if (observer) {
    observer.disconnect();
  }
  observer = new MutationObserver((mutations) => {
    const relevant = mutations.some((mutation) => {
      if (mutation.type === "characterData") {
        return true;
      }
      return mutation.addedNodes.length > 0;
    });
    if (relevant) {
      scheduleScan();
    }
  });
  observer.observe(document.body, {
    childList: true,
    characterData: true,
    subtree: true
  });
}
function init() {
  if (!document.body) {
    return;
  }
  injectStyles();
  scheduleScan();
  startObserver();
}
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init, { once: true });
} else {
  init();
}
