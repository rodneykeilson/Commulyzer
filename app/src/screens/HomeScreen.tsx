import React, { useState } from 'react';
import { StyleSheet, Text, TextInput, View } from 'react-native';

import { PrimaryButton } from '../components/PrimaryButton';
import { useModel } from '../context/ModelContext';

export const HomeScreen = () => {
  const { status, ensureLoaded, predict, errorMessage } = useModel();
  const [sample, setSample] = useState('');
  const [result, setResult] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleAnalyze = async () => {
    if (!sample.trim()) {
      setResult('Enter a comment to analyze.');
      return;
    }

    try {
      setIsSubmitting(true);
      await ensureLoaded();
      const prediction = await predict({ text: sample });
      const formattedScores = Object.entries(prediction.rawScores)
        .map(([label, score]) => `${label}: ${Number(score).toFixed(3)}`)
        .join('\n');
      const formattedActive =
        prediction.activeLabels.length > 0
          ? prediction.activeLabels.join(', ')
          : 'none';
      const combined = [
        `Active labels: ${formattedActive}`,
        formattedScores || 'Model returned no scores.',
      ]
        .filter(Boolean)
        .join('\n');
      setResult(combined);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to analyze sample.';
      setResult(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Commulyzer</Text>
      <Text style={styles.status}>Model status: {status}</Text>
      {errorMessage ? (
        <Text
          style={status === 'error' ? styles.errorText : styles.warningText}
        >
          {errorMessage}
        </Text>
      ) : null}

      <TextInput
        multiline
        value={sample}
        onChangeText={setSample}
        placeholder="Paste a comment to analyze"
        style={styles.input}
        placeholderTextColor="#94a3b8"
      />

      <PrimaryButton
        label={isSubmitting ? 'Analyzing…' : 'Analyze'}
        onPress={handleAnalyze}
        disabled={isSubmitting || status === 'loading'}
      />

      <View style={styles.resultBox}>
        <Text style={styles.resultLabel}>Scores</Text>
        <Text style={styles.resultBody}>
          {result || 'Results will appear here.'}
        </Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 24,
    backgroundColor: '#0f172a',
  },
  heading: {
    fontSize: 24,
    fontWeight: '700',
    color: '#e2e8f0',
    marginBottom: 8,
  },
  status: {
    color: '#94a3b8',
    marginBottom: 16,
  },
  errorText: {
    color: '#f87171',
    marginBottom: 16,
  },
  warningText: {
    color: '#fbbf24',
    marginBottom: 16,
  },
  input: {
    minHeight: 160,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#334155',
    padding: 16,
    color: '#e2e8f0',
    backgroundColor: '#1e293b',
  },
  resultBox: {
    marginTop: 24,
    padding: 16,
    borderRadius: 12,
    backgroundColor: '#1e293b',
  },
  resultLabel: {
    color: '#e2e8f0',
    fontWeight: '600',
    marginBottom: 8,
  },
  resultBody: {
    color: '#cbd5f5',
    lineHeight: 20,
  },
});
