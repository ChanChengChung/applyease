import { Component, type ErrorInfo, type ReactNode } from "react";

type AppErrorBoundaryProps = {
  children: ReactNode;
  title: string;
  message: string;
  reloadLabel: string;
  /** Injected by tests; production defaults to a cache-busting full reload. */
  onReload?: () => void;
};

type AppErrorBoundaryState = { hasError: boolean };

/**
 * Keeps a failed lazy-loaded route from turning the whole workspace into a
 * blank screen. A cache-busting reload fetches the current deployment
 * manifest, even when an old entry document still points at a removed chunk.
 */
export class AppErrorBoundary extends Component<
  AppErrorBoundaryProps,
  AppErrorBoundaryState
> {
  state: AppErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(_error: Error, _info: ErrorInfo) {
    // Do not render or transmit error contents here: route errors can contain
    // application data. Production observability can attach a privacy-reviewed
    // reporter at the deployment boundary if required.
  }

  private reload = () => {
    if (this.props.onReload) {
      this.props.onReload();
      return;
    }
    // `reload()` can still reuse an intermediary/browser entry document after
    // a code-split deployment. Replacing the URL with a one-use cache buster
    // forces Nginx to serve the current index and preserves the language path.
    const target = new URL(window.location.href);
    target.searchParams.set("ae_reload", String(Date.now()));
    window.location.replace(target.toString());
  };

  render() {
    if (this.state.hasError) {
      return (
        <main>
          <section
            className="card dashboard-state"
            role="alert"
            aria-live="assertive"
          >
            <h1>{this.props.title}</h1>
            <p>{this.props.message}</p>
            <button
              className="button-primary"
              type="button"
              onClick={this.reload}
            >
              {this.props.reloadLabel}
            </button>
          </section>
        </main>
      );
    }

    return this.props.children;
  }
}
