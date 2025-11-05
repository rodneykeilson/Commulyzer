import { StatusBar } from 'expo-status-bar';
import React from 'react';
import { SafeAreaView } from 'react-native';

import { ModelProvider } from './src/context/ModelContext';
import { HomeScreen } from './src/screens/HomeScreen';

export default function App(): JSX.Element {
  return (
    <ModelProvider>
      <SafeAreaView style={{ flex: 1, backgroundColor: '#0f172a' }}>
        <StatusBar style="light" />
        <HomeScreen />
      </SafeAreaView>
    </ModelProvider>
  );
}
