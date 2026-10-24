// Wireframe fonts, self-hosted (no network needed): the weights the tokens use.
import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-sans/600.css';
import '@fontsource/ibm-plex-sans/700.css';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource/ibm-plex-mono/500.css';
import '@fontsource/ibm-plex-mono/600.css';
import '@mantine/core/styles.css';
import './styles/tokens.css';

import { MantineProvider, createTheme } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';

// Mantine palettes mapped onto the wireframe tokens (src/styles/tokens.css).
const theme = createTheme({
  fontFamily: 'var(--tst-font)',
  fontFamilyMonospace: 'var(--tst-font-mono)',
  headings: { fontFamily: 'var(--tst-font)' },
  primaryColor: 'accent',
  primaryShade: 5,
  autoContrast: true,
  defaultRadius: 'md',
  colors: {
    // text, text-2, muted, (unused), border, rule, panel, bg, ...
    dark: [
      '#E8ECF1',
      '#C9D1DB',
      '#9BA7B6',
      '#6B7685',
      '#2A3442',
      '#222B37',
      '#151B23',
      '#0E1217',
      '#0B0E12',
      '#080A0D',
    ],
    accent: [
      '#EAF3FF',
      '#CFE3FF',
      '#A9CEFF',
      '#7DB6FF',
      '#6AABFF',
      '#5AA2FF',
      '#4A8FE6',
      '#3B7BCC',
      '#2D67B3',
      '#1F5499',
    ],
    warn: [
      '#FFF3E8',
      '#FDE1C8',
      '#FACBA3',
      '#F8B67F',
      '#F6AB6D',
      '#F5A25D',
      '#DB8C4A',
      '#C0773A',
      '#A6622B',
      '#6A4426',
    ],
  },
});

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

const root = document.getElementById('root');
if (!root) throw new Error('Missing #root element');

createRoot(root).render(
  <StrictMode>
    <MantineProvider theme={theme} defaultColorScheme="dark" forceColorScheme="dark">
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </MantineProvider>
  </StrictMode>,
);
