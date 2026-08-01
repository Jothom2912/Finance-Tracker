import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { renderWithQueryClient } from '../test-utils/renderWithQueryClient';
import AccountSelector from './AccountSelector';
import { createAccount, fetchAccounts } from '../api/accounts';

const navigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => navigate };
});

vi.mock('../context/AuthContext', () => {
  const user = { id: 7, username: 'alice' };
  return { useAuth: () => ({ user }) };
});

vi.mock('../api/accounts', () => ({
  fetchAccounts: vi.fn(),
  createAccount: vi.fn(),
  updateAccount: vi.fn(),
}));

describe('AccountSelector account creation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchAccounts.mockResolvedValue([]);
  });

  it('shows a retryable 503 message without resubmitting or clearing the form', async () => {
    const user = userEvent.setup();
    createAccount.mockRejectedValue({ status: 503, message: 'user-service er utilgængelig' });

    renderWithQueryClient(<AccountSelector />);

    await screen.findByText('Du har ingen konti endnu. Opret en for at komme i gang!');
    await user.click(screen.getByRole('button', { name: '+ Opret ny konto' }));
    const input = screen.getByRole('textbox');
    await user.type(input, 'Ferie');
    await user.click(screen.getByRole('button', { name: 'Opret konto' }));

    expect(
      await screen.findByText(
        'Kontotjenesten kan ikke bekræfte din bruger lige nu. Prøv igen om et øjeblik.'
      )
    ).toBeInTheDocument();
    expect(createAccount).toHaveBeenCalledTimes(1);
    expect(createAccount).toHaveBeenCalledWith({ name: 'Ferie' });
    expect(input).toHaveValue('Ferie');
    expect(navigate).not.toHaveBeenCalled();

    await waitFor(() => expect(fetchAccounts).toHaveBeenCalledTimes(1));
  });

  it('preserves a 400 detail from the API', async () => {
    const user = userEvent.setup();
    createAccount.mockRejectedValue({ status: 400, message: 'Bruger med dette ID findes ikke.' });

    renderWithQueryClient(<AccountSelector />);

    await screen.findByText('Du har ingen konti endnu. Opret en for at komme i gang!');
    await user.click(screen.getByRole('button', { name: '+ Opret ny konto' }));
    await user.type(screen.getByRole('textbox'), 'Ferie');
    await user.click(screen.getByRole('button', { name: 'Opret konto' }));

    expect(await screen.findByText('Bruger med dette ID findes ikke.')).toBeInTheDocument();
    expect(createAccount).toHaveBeenCalledTimes(1);
  });
});
