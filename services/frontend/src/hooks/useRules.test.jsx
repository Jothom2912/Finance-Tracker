import { vi, describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useRules } from './useRules';
import * as rulesApi from '../api/rules';
import { createQueryClientWrapper } from '../test-utils/renderWithQueryClient';

vi.mock('../api/rules');

beforeEach(() => {
  vi.clearAllMocks();
});

const RULE = {
  id: 1,
  pattern_type: 'keyword',
  pattern_value: 'netto',
  subcategory_id: 3,
  subcategory_name: 'Dagligvarer',
  category_id: 1,
  category_name: 'Mad & drikke',
  priority: 50,
  active: true,
  is_learned: false,
};

describe('useRules', () => {
  it('fetches rules on mount', async () => {
    rulesApi.fetchRules.mockResolvedValue([RULE]);

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useRules(), { wrapper });

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.rules).toEqual([RULE]);
    expect(result.current.error).toBeNull();
  });

  it('sets error message on fetch failure', async () => {
    rulesApi.fetchRules.mockRejectedValue(new Error('Netværksfejl'));

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useRules(), { wrapper });

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('Netværksfejl');
  });

  it('create invalidates both rules and transaction views', async () => {
    rulesApi.fetchRules.mockResolvedValue([]);
    rulesApi.createRule.mockResolvedValue(RULE);

    const { wrapper, client } = createQueryClientWrapper();
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries');

    const { result } = renderHook(() => useRules(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    invalidateSpy.mockClear();

    await act(async () => {
      await result.current.create({ pattern_value: 'netto', subcategory_id: 3 });
    });

    expect(rulesApi.createRule).toHaveBeenCalledWith({ pattern_value: 'netto', subcategory_id: 3 });
    const invalidatedKeys = invalidateSpy.mock.calls.map(([arg]) => arg.queryKey[0]);
    expect(invalidatedKeys).toContain('rules');
    expect(invalidatedKeys).toContain('transactions');
  });

  it('remove invalidates rules', async () => {
    rulesApi.fetchRules.mockResolvedValue([RULE]);
    rulesApi.deleteRule.mockResolvedValue();

    const { wrapper, client } = createQueryClientWrapper();
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries');

    const { result } = renderHook(() => useRules(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    invalidateSpy.mockClear();

    await act(async () => {
      await result.current.remove(1);
    });

    expect(rulesApi.deleteRule).toHaveBeenCalledWith(1);
    expect(invalidateSpy.mock.calls.map(([arg]) => arg.queryKey[0])).toContain('rules');
  });

  it('update sends id and data', async () => {
    rulesApi.fetchRules.mockResolvedValue([RULE]);
    rulesApi.updateRule.mockResolvedValue({ ...RULE, active: false });

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useRules(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.update({ id: 1, data: { active: false } });
    });

    expect(rulesApi.updateRule).toHaveBeenCalledWith(1, { active: false });
  });
});
