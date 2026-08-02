export default function Card({ children, className = "", padding = "p-6" }) {
  return <section className={`rounded-xl border border-gray-100 bg-white ${padding} shadow-sm ${className}`}>{children}</section>;
}
