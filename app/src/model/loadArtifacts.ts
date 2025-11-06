import type { ModelArtifacts, TfidfMetadata } from './types';
import coefficientsJson from '../../assets/model/classifier_coefficients.json';
import interceptsJson from '../../assets/model/classifier_intercepts.json';
import metadataJson from '../../assets/model/metadata.json';
import thresholdsJson from '../../assets/model/thresholds.json';

type VocabularyChunk = Record<string, number>;
type VocabularyMap = Map<string, number>;

const vocabularyChunkLoaders: Record<string, () => Promise<VocabularyChunk>> = {
  'vocabulary_001.json': async () =>
    (await import('../../assets/model/vocabulary_001.json'))
      .default as VocabularyChunk,
  'vocabulary_002.json': async () =>
    (await import('../../assets/model/vocabulary_002.json'))
      .default as VocabularyChunk,
  'vocabulary_003.json': async () =>
    (await import('../../assets/model/vocabulary_003.json'))
      .default as VocabularyChunk,
  'vocabulary_004.json': async () =>
    (await import('../../assets/model/vocabulary_004.json'))
      .default as VocabularyChunk,
  'vocabulary_005.json': async () =>
    (await import('../../assets/model/vocabulary_005.json'))
      .default as VocabularyChunk,
  'vocabulary_006.json': async () =>
    (await import('../../assets/model/vocabulary_006.json'))
      .default as VocabularyChunk,
};

function coerceVectorizer(config: any): TfidfMetadata {
  if (!config) {
    throw new Error('Vectorizer metadata missing.');
  }

  const ngramRangeRaw = Array.isArray(config.ngram_range)
    ? config.ngram_range.map((value: unknown) => Number(value))
    : [1, 1];

  const minN = Number.isFinite(ngramRangeRaw[0]) ? Number(ngramRangeRaw[0]) : 1;
  const maxN = Number.isFinite(ngramRangeRaw[1])
    ? Number(ngramRangeRaw[1])
    : minN;
  const idfValues = Array.isArray(config.idf)
    ? config.idf.map((value: unknown) => Number(value))
    : [];

  return {
    ngramRange: [minN, maxN],
    lowercase: Boolean(config.lowercase),
    useIdf: Boolean(config.use_idf),
    smoothIdf: Boolean(config.smooth_idf),
    sublinearTf: Boolean(config.sublinear_tf),
    norm: (config.norm ?? null) as 'l1' | 'l2' | null,
    binary: Boolean(config.binary),
    minDf: Number(config.min_df ?? 1),
    maxDf: Number(config.max_df ?? 1),
    tokenPattern:
      typeof config.token_pattern === 'string' ? config.token_pattern : null,
    stopWords: Array.isArray(config.stop_words) ? config.stop_words : null,
    idf: idfValues,
    vocabularySize: Number(config.vocabulary_size ?? idfValues.length),
    documentCount:
      typeof config.document_count === 'number'
        ? config.document_count
        : undefined,
  };
}

export async function loadArtifacts(): Promise<ModelArtifacts> {
  const metadata = metadataJson as any;

  if (!metadata || !metadata.vectorizer) {
    throw new Error(
      'Model metadata is incomplete. Copy the exported JSON bundle into app/assets/model/.',
    );
  }

  const vectorizer = coerceVectorizer(metadata.vectorizer);
  const thresholds =
    (thresholdsJson as Record<string, number>) ??
    (metadata.thresholds as Record<string, number>) ??
    {};
  const labels = Array.isArray(metadata.labels)
    ? (metadata.labels as string[])
    : Object.keys(thresholds);
  const coefficients = (coefficientsJson as number[][]) ?? [];
  const intercepts = (interceptsJson as number[]) ?? [];
  const vocabulary = await loadVocabulary(metadata.vectorizer);

  if (labels.length === 0 || vocabulary.size === 0) {
    console.warn(
      'Model assets appear to be placeholders. Replace files in app/assets/model/ with the exported JSON bundle.',
    );
  }

  if (coefficients.length !== labels.length) {
    throw new Error(
      'Coefficient matrix shape does not match number of labels.',
    );
  }

  if (intercepts.length !== labels.length) {
    throw new Error('Intercept vector shape does not match number of labels.');
  }

  return {
    vectorizer,
    coefficients,
    intercepts,
    vocabulary,
    thresholds,
    labels,
  };
}

async function loadVocabulary(vectorizerMeta: any): Promise<VocabularyMap> {
  const shards: string[] = Array.isArray(vectorizerMeta?.vocabulary_files)
    ? vectorizerMeta.vocabulary_files
    : [];

  if (shards.length === 0) {
    throw new Error(
      'Vocabulary shards missing. Copy vocabulary_001.json through vocabulary_005.json into app/assets/model/.',
    );
  }

  const vocabulary: VocabularyMap = new Map();

  for (const shardName of shards) {
    const loader = vocabularyChunkLoaders[shardName];

    if (!loader) {
      console.warn(
        `Vocabulary shard ${shardName} is not bundled. Ensure the JSON file exists in app/assets/model/.`,
      );
      continue;
    }

    try {
      const chunk = await loader();
      for (const [term, index] of Object.entries(chunk)) {
        if (typeof index === 'number' && Number.isFinite(index)) {
          vocabulary.set(term, index);
        }
      }
    } catch (error) {
      console.warn(`Failed to load vocabulary shard ${shardName}`, error);
    }
  }

  if (vocabulary.size === 0) {
    throw new Error(
      'Vocabulary failed to load from shards. Double-check the JSON assets.',
    );
  }

  return vocabulary;
}
