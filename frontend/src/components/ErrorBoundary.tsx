import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/Button';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error);
    console.error('Component stack:', errorInfo.componentStack);
    this.setState({ errorInfo });
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    window.location.href = '/';
  };

  private handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  public render() {
    if (this.state.hasError) {
      const isDev = import.meta.env.DEV;
      return (
        <div className="flex min-h-screen items-center justify-center bg-background px-4">
          <div className="w-full max-w-2xl text-center">
            <AlertTriangle className="mx-auto h-12 w-12 text-red-500" />
            <h1 className="mt-4 font-display text-2xl font-bold">Something went wrong</h1>
            <p className="mt-2 text-muted-foreground">
              An unexpected error occurred. Please try again or return to home.
            </p>
            {this.state.error && (
              <details className="mt-4 text-left" open={isDev}>
                <summary className="cursor-pointer text-sm text-muted-foreground">
                  Error details
                </summary>
                <div className="mt-2 space-y-2">
                  <pre className="overflow-auto rounded bg-muted p-2 text-xs">
                    {this.state.error.toString()}
                    {this.state.error.stack ? '\n\n' + this.state.error.stack : ''}
                  </pre>
                  {this.state.errorInfo?.componentStack && isDev && (
                    <pre className="overflow-auto rounded bg-muted p-2 text-xs">
                      Component stack:{this.state.errorInfo.componentStack}
                    </pre>
                  )}
                </div>
              </details>
            )}
            <div className="mt-6 flex gap-3 justify-center">
              <Button onClick={this.handleRetry}>Retry</Button>
              <Button variant="secondary" onClick={() => window.location.reload()}>
                Reload Page
              </Button>
              <Button variant="secondary" onClick={this.handleReset}>
                Return Home
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
