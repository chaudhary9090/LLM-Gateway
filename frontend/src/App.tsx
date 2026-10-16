import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@/lib/theme';
import { ToastProvider } from '@/components/common/Toast';
import { AppLayout } from '@/components/layout/AppLayout';

import { Overview } from '@/pages/Overview';
import { Playground } from '@/pages/Playground';
import { Providers } from '@/pages/Providers';
import { Models } from '@/pages/Models';
import { Logs } from '@/pages/Logs';
import { HealthMetrics } from '@/pages/HealthMetrics';

// Create a single stable QueryClient instance with sane defaults
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 3000,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ToastProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<AppLayout />}>
                <Route index element={<Overview />} />
                <Route path="playground" element={<Playground />} />
                <Route path="providers" element={<Providers />} />
                <Route path="models" element={<Models />} />
                <Route path="logs" element={<Logs />} />
                <Route path="health-metrics" element={<HealthMetrics />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
};

export default App;
