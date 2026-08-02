const VARIANTS = {
  danger: "bg-rose-600 text-white hover:bg-rose-700 focus:ring-rose-200",
  ghost: "bg-transparent text-gray-700 hover:bg-gray-100 focus:ring-gray-200",
  outline: "border border-gray-200 bg-white text-gray-700 hover:border-emerald-300 hover:bg-emerald-50 focus:ring-emerald-100",
  primary: "bg-emerald-600 text-white hover:bg-emerald-700 focus:ring-emerald-200",
};

const SIZES = { sm: "px-3 py-1.5 text-xs", md: "px-4 py-2 text-sm", lg: "px-5 py-2.5 text-sm" };

export default function Button({ children, className = "", size = "md", type = "button", variant = "primary", ...props }) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-50 ${SIZES[size]} ${VARIANTS[variant]} ${className}`}
      type={type}
      {...props}
    >
      {children}
    </button>
  );
}
