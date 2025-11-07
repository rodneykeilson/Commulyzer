export interface TfidfMetadata {
  ngramRange: [number, number];
  lowercase: boolean;
  useIdf: boolean;
  smoothIdf: boolean;
  sublinearTf: boolean;
  norm: 'l1' | 'l2' | null;
  binary: boolean;
  minDf: number;
  maxDf: number;
  tokenPattern: string | null;
  stopWords: string[] | null;
  idf: number[];
  vocabularySize: number;
  documentCount?: number;
}

export interface ModelArtifacts {
  vectorizer: TfidfMetadata;
  coefficients: number[][];
  intercepts: number[];
  vocabulary: Map<string, number>;
  thresholds: Record<string, number>;
  labels: string[];
}

export interface ToxicityPrediction {
  rawScores: Record<string, number>;
  activeLabels: string[];
  triggered: Record<string, number>;
}
