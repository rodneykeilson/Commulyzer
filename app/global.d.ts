declare module 'react' {
  export type ReactNode = unknown;
  export interface FC<P = Record<string, unknown>> {
    (props: P & { children?: ReactNode }): any;
  }
  export const createContext: (...args: any[]) => any;
  export const useContext: (...args: any[]) => any;
  export const useState: (...args: any[]) => any;
  export const useMemo: (...args: any[]) => any;
  export const useCallback: (...args: any[]) => any;
  export const useRef: (...args: any[]) => any;
  const React: { createElement: (...args: any[]) => any };
  export default React;
}

declare module 'expo-status-bar' {
  import type { FC } from 'react';
  export const StatusBar: FC<{ style?: 'auto' | 'light' | 'dark' }>;
}

declare module 'react-native' {
  export const SafeAreaView: any;
  export const ScrollView: any;
  export const View: any;
  export const Text: any;
  export const TextInput: any;
  export const Pressable: any;
  export const StyleSheet: any;
}

declare module 'react/jsx-runtime' {
  export const jsx: any;
  export const jsxs: any;
  export const Fragment: any;
  export default any;
}

declare module '*.json' {
  const value: any;
  export default value;
}

declare namespace JSX {
  type Element = unknown;
  interface ElementClass {
    render?: (...args: unknown[]) => unknown;
  }
  interface IntrinsicElements {
    [elemName: string]: any;
  }
}
