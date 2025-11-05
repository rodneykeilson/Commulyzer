const universeNative = require('eslint-config-universe/flat/native');

module.exports = [
  {
    ignores: [
      'node_modules',
      'dist',
      'build',
      'coverage',
      '.expo',
      '.expo-shared',
    ],
  },
  ...universeNative,
];
