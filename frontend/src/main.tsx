import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import { AppRoutes } from '@/routes';
import { AuthProvider } from '@/contexts/AuthContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { ToastProvider } from '@/contexts/ToastContext';
import '@/index.css';

const container = document.getElementById('root');

if (!container) {
  throw new Error('The #root element is missing from index.html.');
}

createRoot(container).render(
  <StrictMode>
    {/* The v7 future flags are opted in explicitly: they are behaviour
        compatible with the current routes and they silence the upgrade
        warnings that React Router prints on every navigation. */}
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ThemeProvider>
        <ToastProvider>
          <AuthProvider>
            <AppRoutes />
          </AuthProvider>
        </ToastProvider>
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>,
);
