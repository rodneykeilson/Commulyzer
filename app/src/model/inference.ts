import type {
  ModelArtifacts,
  TfidfMetadata,
  ToxicityPrediction,
  ToxicitySample,
} from './types';

const DEFAULT_TOKEN_REGEX = createTokenRegex();

function createTokenRegex(): RegExp {
  try {
    return new RegExp('[\\p{L}\\p{N}_]{2,}', 'gu');
  } catch {
    return /[A-Za-z0-9_]{2,}/g;
  }
}

function normaliseWhitespace(text: string): string {
  return text
    .replace(/[\r\n]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function getTokenRegex(metadata: TfidfMetadata): RegExp {
  if (!metadata.tokenPattern) {
    return DEFAULT_TOKEN_REGEX;
  }
  const cleaned = metadata.tokenPattern.startsWith('(?u)')
    ? metadata.tokenPattern.slice(4)
    : metadata.tokenPattern;
  try {
    return new RegExp(cleaned, 'gu');
  } catch (error) {
    console.warn('Falling back to default token regex:', error);
    return DEFAULT_TOKEN_REGEX;
  }
}

function tokenize(text: string, metadata: TfidfMetadata): string[] {
  const regex = getTokenRegex(metadata);
  const tokens: string[] = [];
  const processed = metadata.lowercase ? text.toLowerCase() : text;
  let match: RegExpExecArray | null;
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
      metadata.stopWords.map((word) =>
        metadata.lowercase ? String(word).toLowerCase() : String(word),
      ),
    );
    return tokens.filter((token) => !stopSet.has(token));
  }
  return tokens;
}

function buildFeatureVector(
  text: string,
  metadata: TfidfMetadata,
  vocabulary: Map<string, number>,
): Map<number, number> {
  const tokens = tokenize(text, metadata);
  const [minN, maxN] = metadata.ngramRange;
  const counts = new Map<number, number>();

  for (let n = minN; n <= maxN; n += 1) {
    if (n <= 0 || tokens.length < n) {
      continue;
    }
    for (let i = 0; i <= tokens.length - n; i += 1) {
      const ngram = tokens.slice(i, i + n).join(' ');
      const index = vocabulary.get(ngram);
      if (typeof index !== 'number' || Number.isNaN(index)) {
        continue;
      }
      const previous = counts.get(index) ?? 0;
      counts.set(index, previous + 1);
    }
  }

  if (counts.size === 0) {
    return counts;
  }

  const features = new Map<number, number>();
  counts.forEach((frequency, index) => {
    let tf = metadata.binary ? (frequency > 0 ? 1 : 0) : frequency;
    if (!metadata.binary && metadata.sublinearTf && tf > 0) {
      tf = 1 + Math.log(tf);
    }
    let value = tf;
    if (metadata.useIdf && metadata.idf[index] !== undefined) {
      value *= metadata.idf[index];
    }
    features.set(index, value);
  });

  if (metadata.norm === 'l2') {
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
  } else if (metadata.norm === 'l1') {
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

function sigmoid(z: number): number {
  if (z === Number.POSITIVE_INFINITY) {
    return 1;
  }
  if (z === Number.NEGATIVE_INFINITY) {
    return 0;
  }
  if (z >= 0) {
    const expNeg = Math.exp(-z);
    return 1 / (1 + expNeg);
  }
  const expPos = Math.exp(z);
  return expPos / (1 + expPos);
}

export function runInference(
  sample: ToxicitySample,
  artifacts: ModelArtifacts,
): ToxicityPrediction {
  const text =
    typeof sample.text === 'string' ? normaliseWhitespace(sample.text) : '';
  const featureVector = text
    ? buildFeatureVector(text, artifacts.vectorizer, artifacts.vocabulary)
    : new Map();

  const rawScores: Record<string, number> = {};
  const activeLabels: string[] = [];

  for (
    let classIndex = 0;
    classIndex < artifacts.labels.length;
    classIndex += 1
  ) {
    const label = artifacts.labels[classIndex];
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
    }
  }

  return {
    rawScores,
    activeLabels,
  };
}
