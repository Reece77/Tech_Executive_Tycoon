import { Alert } from '@mantine/core';
import { Component, type ReactNode } from 'react';

interface State {
  error: Error | null;
}

/** Shows a render error in place of the screen instead of a blank page. */
export class ScreenErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <Alert color="red" title="This screen failed to render" role="alert">
          {this.state.error.message}. Try another screen or reload the page.
        </Alert>
      );
    }
    return this.props.children;
  }
}
