const WIDTHS = { default: "max-w-7xl", narrow: "max-w-5xl" };

export default function PageContainer({ children, className = "", width = "default" }) {
  return <div className={`mx-auto space-y-6 ${WIDTHS[width]} ${className}`}>{children}</div>;
}
