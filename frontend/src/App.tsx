import { AppRoutes } from '@/routes';

/**
 * The application root.
 *
 * `main.tsx` mounts the providers (theme, toasts, auth) around this
 * component, so `App` only has to describe the routing table.
 */
export function App() {
  return <AppRoutes />;
}

export default App;
