export default function Input({ className = "", label, helpText, id, ...props }) {
  const inputId = id ?? props.name;
  return <label className="block"><span className="text-sm font-medium text-gray-700">{label}</span><input className={`mt-1.5 block w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 outline-none transition placeholder:text-gray-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 disabled:cursor-not-allowed disabled:bg-gray-50 ${className}`} id={inputId} {...props} />{helpText && <span className="mt-1 block text-xs text-gray-500">{helpText}</span>}</label>;
}
