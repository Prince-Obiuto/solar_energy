import { Component } from "react";

import ErrorState from "../components/ui/ErrorState";

export default class AppErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return <main className="grid min-h-screen place-items-center bg-gray-50 p-6"><div className="w-full max-w-lg"><ErrorState description="The interface encountered an unexpected error." onRetry={() => window.location.reload()} title="Unable to display this page" /></div></main>;
    }

    return this.props.children;
  }
}
