import React from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import './Modal.css';

/**
 * Accessible modal built on Radix Dialog.
 *
 * Preserves the original API ({ isOpen, onClose, title, children }) so
 * existing call sites do not need changes beyond passing a title.
 *
 * `title` is required: Radix Dialog needs Dialog.Title for screen reader
 * accessibility. A missing title will trigger a Radix dev warning. Every
 * call site must pass an explicit, human-readable title.
 *
 * Behaviour provided for free by Radix (previously missing or partial):
 * - Focus trap within the dialog while open
 * - Esc closes the dialog
 * - Click on overlay closes the dialog
 * - Body scroll lock while open
 * - Correct role="dialog" and aria-modal="true"
 * - Focus returned to the trigger element on close
 *
 * Class names are prefixed `app-modal-` to keep this component's
 * styles isolated from any future page-level CSS that may reuse the
 * generic `.modal-*` class names.
 */
function Modal({ isOpen, onClose, title, children }) {
  return (
    <Dialog.Root
      open={isOpen}
      onOpenChange={(open) => {
        // Radix fires onOpenChange for both open and close transitions.
        // Our legacy API only signals close, so bridge here.
        if (!open) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="app-modal-overlay" />
        <Dialog.Content className="app-modal-content">
          <div className="app-modal-header">
            <Dialog.Title asChild>
              <h2>{title}</h2>
            </Dialog.Title>
            <Dialog.Close asChild>
              <button
                type="button"
                className="app-modal-close-button"
                aria-label="Luk dialog"
              >
                &times;
              </button>
            </Dialog.Close>
          </div>
          <div className="app-modal-body">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export default Modal;
