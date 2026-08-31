import useOverlayA11y from "../../hooks/useOverlayA11y";

export default function Drawer({ children, isOpen, onClose, side = "right", title }) {
  const drawerRef = useOverlayA11y(isOpen, onClose);
  if (!isOpen) return null;
  const position = side === "left" ? "left-0" : "right-0";
  return <div aria-labelledby="shared-drawer-title" aria-modal="true" className="fixed inset-0 z-50" role="dialog"><button aria-label="Close drawer" className="absolute inset-0 bg-gray-950/40" onClick={onClose} type="button" /><aside className={`absolute inset-y-0 ${position} flex w-full max-w-md flex-col bg-white shadow-2xl`} ref={drawerRef}><div className="flex items-center justify-between border-b border-gray-200 p-5"><h2 className="font-semibold text-gray-900" id="shared-drawer-title">{title}</h2><button aria-label="Close drawer" className="rounded-md px-2 py-1 text-gray-400 hover:bg-gray-100" onClick={onClose} type="button">×</button></div><div className="flex-1 overflow-y-auto p-5">{children}</div></aside></div>;
}
