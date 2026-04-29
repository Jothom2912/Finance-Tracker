import { createContext, useCallback, useContext, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import './ConfirmDialog.css';

const ConfirmDialogContext = createContext(null);

const DEFAULT_OPTIONS = {
  title: 'Bekræft handling',
  message: '',
  confirmLabel: 'Bekræft',
  cancelLabel: 'Annullér',
  variant: 'default', // 'default' | 'danger'
};

export function ConfirmDialogProvider({ children }) {
  const [state, setState] = useState(null);

  const confirm = useCallback((options) => {
    return new Promise((resolve) => {
      // If a previous confirm is still open we resolve it as cancelled before
      // showing the new one. This prevents leaked promises if a caller fires
      // a second confirm before the first is dismissed.
      setState((prev) => {
        if (prev?.resolve) prev.resolve(false);
        return { ...DEFAULT_OPTIONS, ...options, resolve };
      });
    });
  }, []);

  const handleConfirm = useCallback(() => {
    setState((prev) => {
      prev?.resolve?.(true);
      return null;
    });
  }, []);

  const handleCancel = useCallback(() => {
    setState((prev) => {
      prev?.resolve?.(false);
      return null;
    });
  }, []);

  const handleOpenChange = useCallback(
    (open) => {
      // Radix calls this for both open and close; we only react to close
      // (Esc, overlay click, programmatic close). Treat any close as cancel.
      if (!open) handleCancel();
    },
    [handleCancel]
  );

  return (
    <ConfirmDialogContext.Provider value={confirm}>
      {children}
      <Dialog.Root open={!!state} onOpenChange={handleOpenChange}>
        <Dialog.Portal>
          <Dialog.Overlay className="confirm-dialog-overlay" />
          {/*
            Initial focus is left to Radix' default, which focuses the first
            focusable element in DOM order. Cancel is rendered before
            Confirm so a user pressing Enter immediately on a destructive
            dialog will dismiss it rather than commit -- the safe default.
          */}
          <Dialog.Content
            className={`confirm-dialog-content confirm-dialog-content--${state?.variant ?? 'default'}`}
          >
            <Dialog.Title className="confirm-dialog-title">
              {state?.title}
            </Dialog.Title>
            {state?.message && (
              <Dialog.Description className="confirm-dialog-message">
                {state.message}
              </Dialog.Description>
            )}
            <div className="confirm-dialog-actions">
              <button
                type="button"
                className="button secondary"
                onClick={handleCancel}
              >
                {state?.cancelLabel}
              </button>
              <button
                type="button"
                className={`button ${state?.variant === 'danger' ? 'danger' : ''}`}
                onClick={handleConfirm}
              >
                {state?.confirmLabel}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </ConfirmDialogContext.Provider>
  );
}

export function useConfirm() {
  const ctx = useContext(ConfirmDialogContext);
  if (!ctx) {
    throw new Error('useConfirm must be used within ConfirmDialogProvider');
  }
  return ctx;
}
