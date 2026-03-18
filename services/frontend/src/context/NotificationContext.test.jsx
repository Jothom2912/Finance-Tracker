import React from 'react';
import { vi, describe, it, expect } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import { NotificationProvider, useNotifications } from './NotificationContext';

function TestConsumer() {
  const { showError, showSuccess, clearMessages } = useNotifications();
  return (
    <div>
      <button onClick={() => showError('Something went wrong')}>Show Error</button>
      <button onClick={() => showSuccess('Saved!')}>Show Success</button>
      <button onClick={clearMessages}>Clear</button>
    </div>
  );
}

function renderWithProvider() {
  return render(
    <NotificationProvider>
      <TestConsumer />
    </NotificationProvider>,
  );
}

describe('NotificationContext', () => {
  it('throws when useNotifications is used outside provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => render(<TestConsumer />)).toThrow(
      'useNotifications must be used within NotificationProvider',
    );

    spy.mockRestore();
  });

  it('shows an error notification', () => {
    renderWithProvider();

    fireEvent.click(screen.getByText('Show Error'));

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('shows a success notification', () => {
    renderWithProvider();

    fireEvent.click(screen.getByText('Show Success'));

    expect(screen.getByText('Saved!')).toBeInTheDocument();
  });

  it('auto-dismisses success notifications after timeout', () => {
    vi.useFakeTimers();
    renderWithProvider();

    fireEvent.click(screen.getByText('Show Success'));
    expect(screen.getByText('Saved!')).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(4000);
    });

    expect(screen.queryByText('Saved!')).not.toBeInTheDocument();
    vi.useRealTimers();
  });

  it('does not auto-dismiss error notifications', () => {
    vi.useFakeTimers();
    renderWithProvider();

    fireEvent.click(screen.getByText('Show Error'));

    act(() => {
      vi.advanceTimersByTime(10000);
    });

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    vi.useRealTimers();
  });

  it('clears all notifications', () => {
    renderWithProvider();

    fireEvent.click(screen.getByText('Show Error'));
    fireEvent.click(screen.getByText('Show Success'));

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText('Saved!')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Clear'));

    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
    expect(screen.queryByText('Saved!')).not.toBeInTheDocument();
  });

  it('dismisses individual notifications via close button', () => {
    renderWithProvider();

    fireEvent.click(screen.getByText('Show Error'));
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Luk besked'));

    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
  });

  it('renders notification container with correct a11y attributes', () => {
    renderWithProvider();

    fireEvent.click(screen.getByText('Show Error'));

    const container = screen.getByRole('status');
    expect(container).toHaveAttribute('aria-live', 'polite');
  });
});
