import type { ModelArtifacts, TfidfMetadata } from './types';

type RawVectorizer = {
  ngram_range?: unknown;
  lowercase?: unknown;
  use_idf?: unknown;
  smooth_idf?: unknown;
  sublinear_tf?: unknown;
  norm?: unknown;
  binary?: unknown;
  min_df?: unknown;
  max_df?: unknown;
  token_pattern?: unknown;
  stop_words?: unknown;
  idf?: unknown;
  vocabulary_size?: unknown;
  document_count?: unknown;
};

type MetadataFile = {
  vectorizer?: RawVectorizer;
  labels?: unknown;
  thresholds?: Record<string, number>;
};

let cachedArtifacts: ModelArtifacts | undefined;

function getAssetUrl(file: string): string {
  const runtime = (globalThis as Record<string, unknown>).chrome as
    | { runtime?: { getURL?: (path: string) => string } }
    | undefined;
  if (runtime?.runtime?.getURL) {
    return runtime.runtime.getURL(`assets/model/${file}`);
  }
  return `assets/model/${file}`;
}

async function fetchJson<T>(file: string): Promise<T> {
  const response = await fetch(getAssetUrl(file));
  if (!response.ok) {
    throw new Error(`Failed to load ${file}: ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

async function fetchText(file: string): Promise<string> {
  const response = await fetch(getAssetUrl(file));
  if (!response.ok) {
    throw new Error(`Failed to load ${file}: ${response.status} ${response.statusText}`);
  }
  return response.text();
}

function coerceVectorizer(config: RawVectorizer | undefined | null): TfidfMetadata {
  if (!config) {
    throw new Error('Vectorizer metadata missing.');
  }

  const ngram = config.ngram_range;
  const rawRange = Array.isArray(ngram)
    ? ngram.map((value: unknown) => Number(value))
    : [1, 1];
  const minN = Number.isFinite(rawRange[0]) ? Number(rawRange[0]) : 1;
  const maxN = Number.isFinite(rawRange[1]) ? Number(rawRange[1]) : minN;
  const idfSource = config.idf;
  const idfValues = Array.isArray(idfSource)
    ? idfSource.map((value: unknown) => Number(value))
    : [];

  return {
    ngramRange: [minN, maxN],
    lowercase: Boolean(config.lowercase),
    useIdf: Boolean(config.use_idf),
    smoothIdf: Boolean(config.smooth_idf),
    sublinearTf: Boolean(config.sublinear_tf),
    norm: config.norm === 'l1' || config.norm === 'l2' ? config.norm : null,
    binary: Boolean(config.binary),
    minDf: Number(config.min_df ?? 1),
    maxDf: Number(config.max_df ?? 1),
    tokenPattern: typeof config.token_pattern === 'string' ? config.token_pattern : null,
    stopWords: Array.isArray(config.stop_words) ? config.stop_words.map((v) => String(v)) : null,
    idf: idfValues,
    vocabularySize: Number(config.vocabulary_size ?? idfValues.length),
    documentCount: typeof config.document_count === 'number' ? config.document_count : undefined,
  };
}

export async function loadArtifacts(): Promise<ModelArtifacts> {
  if (cachedArtifacts) {
    return cachedArtifacts;
  }

  const metadata = await fetchJson<MetadataFile>('metadata.json');
  const vectorizerSource = metadata?.vectorizer ?? (metadata as unknown as RawVectorizer | undefined);
  const vectorizer = coerceVectorizer(vectorizerSource);
  const thresholds = await fetchJson<Record<string, number>>('thresholds.json').catch(() => {
    if (metadata?.thresholds) {
      return metadata.thresholds;
    }
    console.warn('Falling back to thresholds embedded in metadata.json');
    return {};
  });
  const labelsRaw = await fetchText('labels.txt').catch(() => '')
    .then((text) => text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean));
  const metadataLabels = Array.isArray(metadata?.labels)
    ? metadata.labels.filter((label): label is string => typeof label === 'string')
    : [];
  const labels = labelsRaw.length > 0 ? labelsRaw : metadataLabels.length > 0 ? metadataLabels : Object.keys(thresholds);
  const coefficients = await fetchJson<number[][]>('classifier_coefficients.json');
  const intercepts = await fetchJson<number[]>('classifier_intercepts.json');
  const vocabularyObj = await fetchJson<Record<string, number>>('vocabulary_combined.json');
  const vocabulary = new Map<string, number>(Object.entries(vocabularyObj));

  if (labels.length === 0) {
    throw new Error('No labels found in artifacts.');
  }
  if (coefficients.length !== labels.length || intercepts.length !== labels.length) {
    throw new Error('Classifier tensors do not match the number of labels.');
  }
  if (vocabulary.size === 0) {
    throw new Error('Vocabulary file appears empty.');
  }

  cachedArtifacts = {
    vectorizer,
    coefficients,
    intercepts,
    vocabulary,
    thresholds,
    labels,
  };

  return cachedArtifacts;
}
