import { vi, describe, it, expect, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useNotificationFeed } from './useNotificationFeed';
import * as notificationsApi from '../api/notifications';
import { createQueryClientWrapper } from '../test-utils/renderWithQueryClient';

vi.mock('../api/notifications');

beforeEach(() => {
  vi.clearAllMocks();
});

const REST_NOTIFICATION = {
  id: '018f-abc',
  type: 'bank_sync_completed',
  title: 'Banksynkronisering færdig',
  body: '2 transaktioner blev importeret.',
  is_read: false,
  created_at: '2026-07-20T02:00:00Z',
};

describe('useNotificationFeed', () => {
  it('fetches and maps notifications (snake_case -> camelCase)', async () => {
    notificationsApi.fetchNotifications.mockResolvedValue([REST_NOTIFICATION]);
    notificationsApi.fetchUnreadCount.mockResolvedValue({ count: 3 });

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useNotificationFeed(), { wrapper });

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.notifications).toEqual([
      {
        id: '018f-abc',
        type: 'bank_sync_completed',
        title: 'Banksynkronisering færdig',
        body: '2 transaktioner blev importeret.',
        isRead: false,
        createdAt: '2026-07-20T02:00:00Z',
      },
    ]);
    await waitFor(() => expect(result.current.unreadCount).toBe(3));
    expect(result.current.error).toBeNull();
  });

  it('surfaces an error message on fetch failure', async () => {
    notificationsApi.fetchNotifications.mockRejectedValue(new Error('Netværksfejl'));
    notificationsApi.fetchUnreadCount.mockResolvedValue({ count: 0 });

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useNotificationFeed(), { wrapper });

    await waitFor(() => expect(result.current.error).toBe('Netværksfejl'));
  });

  it('markRead invalidates the notifications feed', async () => {
    notificationsApi.fetchNotifications.mockResolvedValue([REST_NOTIFICATION]);
    notificationsApi.fetchUnreadCount.mockResolvedValue({ count: 1 });
    notificationsApi.markRead.mockResolvedValue(undefined);

    const { wrapper, client } = createQueryClientWrapper();
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries');

    const { result } = renderHook(() => useNotificationFeed(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    invalidateSpy.mockClear();

    await result.current.markRead('018f-abc');

    // React Query v5 passes a context object as a 2nd arg — assert the id only.
    expect(notificationsApi.markRead.mock.calls[0][0]).toBe('018f-abc');
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['notifications'] });
  });

  it('still invalidates the feed when a write 404s', async () => {
    // The server now 404s writes against a dismissed notification, so this is
    // the stale-snapshot case: the row was dismissed on another device and the
    // list is only polled every 45s. Refetching on failure is what removes it;
    // on onSuccess alone the dead row stayed on screen and the button looked
    // broken, because the callers swallow the rejection.
    notificationsApi.fetchNotifications.mockResolvedValue([REST_NOTIFICATION]);
    notificationsApi.fetchUnreadCount.mockResolvedValue({ count: 1 });
    notificationsApi.dismissNotification.mockRejectedValue(new Error('404 Not Found'));

    const { wrapper, client } = createQueryClientWrapper();
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries');

    const { result } = renderHook(() => useNotificationFeed(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    invalidateSpy.mockClear();

    await expect(result.current.dismiss('018f-abc')).rejects.toThrow('404');

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['notifications'] });
  });
});
