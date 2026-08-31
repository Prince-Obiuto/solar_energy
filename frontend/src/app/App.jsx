import AppErrorBoundary from "./AppErrorBoundary";
import AppProviders from "./providers/AppProviders";
import AppRouter from "./router/AppRouter";

export default function App() {
  return (
    <AppErrorBoundary>
      <AppProviders>
        <AppRouter />
      </AppProviders>
    </AppErrorBoundary>
  );
}
