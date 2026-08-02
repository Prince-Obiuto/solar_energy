import Button from "./Button";
import Modal from "./Modal";

export default function Dialog({ confirmLabel = "Confirm", children, isOpen, onClose, onConfirm, title }) {
  return <Modal isOpen={isOpen} onClose={onClose} title={title}><div className="text-sm text-gray-600">{children}</div><div className="mt-6 flex justify-end gap-3"><Button onClick={onClose} variant="ghost">Cancel</Button><Button onClick={onConfirm}>{confirmLabel}</Button></div></Modal>;
}
