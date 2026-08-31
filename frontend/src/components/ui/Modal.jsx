import useOverlayA11y from "../../hooks/useOverlayA11y";

export default function Modal({ children, isOpen, onClose, title }) {
  const modalRef = useOverlayA11y(isOpen, onClose);
  if (!isOpen) return null;
  return <div aria-labelledby="shared-modal-title" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center bg-gray-950/50 p-4" role="dialog"><button aria-label="Close modal" className="absolute inset-0" onClick={onClose} type="button" /><section className="relative z-10 w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl" ref={modalRef}><div className="flex items-center justify-between gap-4"><h2 className="text-lg font-semibold text-gray-900" id="shared-modal-title">{title}</h2><button aria-label="Close modal" className="rounded-md px-2 py-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700" onClick={onClose} type="button">×</button></div><div className="mt-5">{children}</div></section></div>;
}
