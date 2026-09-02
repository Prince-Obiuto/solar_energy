import ThemeProvider from "./ThemeProvider";
import AuthProvider from "./AuthProvider";

export default function AppProviders({ children }) {
  return <ThemeProvider><AuthProvider>{children}</AuthProvider></ThemeProvider>;
}
