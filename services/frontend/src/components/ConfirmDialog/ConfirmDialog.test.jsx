import React, { useState } from 'react';
import { vi, describe, it, expect } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ConfirmDialogProvider, useConfirm } from './ConfirmDialog';

function TestConsumer({ options, onResult }) {
  const confirm = useConfirm();
  const [busy, setBusy] = useState(false);

  const handleClick = async () => {
    setBusy(true);
    const ok = await confirm(options);
    setBusy(false);
    onResult(ok);
  };

  return (
    <button type="button" onClick={handleClick} disabled={busy}>
      Trigger
    </button>
  );
}

function renderWithProvider(options = {}, onResult = vi.fn()) {
  const utils = render(
    <ConfirmDialogProvider>
      <TestConsumer options={options} onResult={onResult} />
    </ConfirmDialogProvider>,
  );
  return { ...utils, onResult };
}

describe('ConfirmDialog', () => {
  it('throws when useConfirm is used outside provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() =>
      render(<TestConsumer options={{}} onResult={() => {}} />),
    ).toThrow('useConfirm must be used within ConfirmDialogProvider');

    spy.mockRestore();
  });

  it('renders the supplied title, message and labels', async () => {
    renderWithProvider({
      title: 'Slet kategori?',
      message: 'Transaktioner mister deres kategori.',
      confirmLabel: 'Slet',
      cancelLabel: 'Behold',
    });

    fireEvent.click(screen.getByText('Trigger'));

    expect(await screen.findByText('Slet kategori?')).toBeInTheDocument();
    expect(
      screen.getByText('Transaktioner mister deres kategori.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Slet' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Behold' })).toBeInTheDocument();
  });

  it('uses default labels when none are provided', async () => {
    renderWithProvider({ message: 'Sikker?' });

    fireEvent.click(screen.getByText('Trigger'));

    expect(await screen.findByText('Bekræft handling')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Bekræft' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Annullér' })).toBeInTheDocument();
  });

  it('resolves true when confirm is clicked', async () => {
    const onResult = vi.fn();
    renderWithProvider({ message: 'OK?' }, onResult);

    fireEvent.click(screen.getByText('Trigger'));
    fireEvent.click(await screen.findByRole('button', { name: 'Bekræft' }));

    await waitFor(() => expect(onResult).toHaveBeenCalledWith(true));
  });

  it('resolves false when cancel is clicked', async () => {
    const onResult = vi.fn();
    renderWithProvider({ message: 'OK?' }, onResult);

    fireEvent.click(screen.getByText('Trigger'));
    fireEvent.click(await screen.findByRole('button', { name: 'Annullér' }));

    await waitFor(() => expect(onResult).toHaveBeenCalledWith(false));
  });

  it('resolves false when the dialog is dismissed via Esc', async () => {
    const onResult = vi.fn();
    renderWithProvider({ message: 'OK?' }, onResult);

    fireEvent.click(screen.getByText('Trigger'));
    await screen.findByRole('button', { name: 'Bekræft' });

    fireEvent.keyDown(document.activeElement || document.body, {
      key: 'Escape',
      code: 'Escape',
    });

    await waitFor(() => expect(onResult).toHaveBeenCalledWith(false));
  });

  it('applies the danger class to the confirm button for variant=danger', async () => {
    renderWithProvider({ message: 'Slet?', variant: 'danger' });

    fireEvent.click(screen.getByText('Trigger'));

    const confirmBtn = await screen.findByRole('button', { name: 'Bekræft' });
    expect(confirmBtn).toHaveClass('danger');
  });

  it('does not apply the danger class for default variant', async () => {
    renderWithProvider({ message: 'OK?' });

    fireEvent.click(screen.getByText('Trigger'));

    const confirmBtn = await screen.findByRole('button', { name: 'Bekræft' });
    expect(confirmBtn).not.toHaveClass('danger');
  });

  it('cancels a pending confirm if a new one is opened on top', async () => {
    function DoubleConsumer({ onResult }) {
      const confirm = useConfirm();
      const trigger = async () => {
        const [first, second] = await Promise.all([
          confirm({ message: 'First' }),
          // Microtask delay so the second confirm queues after the first.
          Promise.resolve().then(() => confirm({ message: 'Second' })),
        ]);
        onResult({ first, second });
      };
      return (
        <button type="button" onClick={trigger}>
          Trigger
        </button>
      );
    }

    const onResult = vi.fn();
    render(
      <ConfirmDialogProvider>
        <DoubleConsumer onResult={onResult} />
      </ConfirmDialogProvider>,
    );

    fireEvent.click(screen.getByText('Trigger'));

    fireEvent.click(await screen.findByRole('button', { name: 'Bekræft' }));

    await waitFor(() =>
      expect(onResult).toHaveBeenCalledWith({ first: false, second: true }),
    );
  });
});
