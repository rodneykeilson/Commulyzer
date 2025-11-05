import React, {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from 'react';

import { runInference } from '../model/inference';
import { loadArtifacts } from '../model/loadArtifacts';
import type {
  ModelArtifacts,
  ToxicityPrediction,
  ToxicitySample,
} from '../model/types';

export type ModelStatus = 'idle' | 'loading' | 'ready' | 'error';

interface ModelContextValue {
  status: ModelStatus;
  errorMessage?: string;
  predict(sample: ToxicitySample): Promise<ToxicityPrediction>;
  ensureLoaded(): Promise<void>;
}

const ModelContext = createContext(undefined as unknown as ModelContextValue);

export function ModelProvider({ children }: { children: any }) {
  const [status, setStatus] = useState('idle' as ModelStatus);
  const [errorMessage, setErrorMessage] = useState(
    undefined as string | undefined,
  );
  const artifactsRef = useRef(undefined as ModelArtifacts | undefined);
  const loadPromiseRef = useRef(undefined as Promise<void> | undefined);

  const ensureLoaded = useCallback(async () => {
    if (status === 'ready' && artifactsRef.current) {
      return;
    }
    if (loadPromiseRef.current) {
      await loadPromiseRef.current;
      return;
    }

    const loadPromise = (async () => {
      try {
        setStatus('loading');
        const loaded = await loadArtifacts();
        artifactsRef.current = loaded;
        const isPlaceholder =
          loaded.labels.length === 1 && loaded.labels[0] === 'placeholder';
        setErrorMessage(
          isPlaceholder
            ? 'Placeholder model assets detected. Replace files in app/assets/model/ with the exported JSON bundle.'
            : undefined,
        );
        setStatus('ready');
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Failed to load model.';
        setErrorMessage(message);
        setStatus('error');
        throw error;
      } finally {
        loadPromiseRef.current = undefined;
      }
    })();

    loadPromiseRef.current = loadPromise;
    await loadPromise;
  }, [status]);

  const predict = useCallback(
    async (sample: ToxicitySample) => {
      if (status !== 'ready' || !artifactsRef.current) {
        await ensureLoaded();
      }

      const currentArtifacts = artifactsRef.current;
      if (!currentArtifacts) {
        throw new Error('Model artifacts unavailable after loading.');
      }

      return runInference(sample, currentArtifacts);
    },
    [status, ensureLoaded],
  );

  const value = useMemo(
    () => ({ status, errorMessage, predict, ensureLoaded }),
    [status, errorMessage, predict, ensureLoaded],
  );

  return (
    <ModelContext.Provider value={value}>{children}</ModelContext.Provider>
  );
}

export const useModel = (): ModelContextValue => {
  const ctx = useContext(ModelContext);
  if (!ctx) {
    throw new Error('useModel must be used inside a ModelProvider.');
  }
  return ctx;
};
