import { Component, type ErrorInfo, type ReactNode } from "react";
import { useLayoutStore } from "../../stores/layoutStore";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class DockviewErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.warn("[DockviewErrorBoundary] caught:", error, info);
  }

  reset = () => {
    useLayoutStore.getState().resetLayout();
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-sm text-gray-400">
        <div className="text-base font-medium text-gray-200">
          Layout failed to initialize.
        </div>
        <div className="max-w-md text-center text-xs text-gray-500">
          {this.state.error?.message ?? "Unknown error"}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={this.reset}
            className="rounded bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500"
          >
            Reset Layout
          </button>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded border border-gray-600 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-gray-700"
          >
            Reload
          </button>
        </div>
      </div>
    );
  }
}
