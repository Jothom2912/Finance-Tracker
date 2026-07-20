import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as notificationsApi from '../api/notifications';

// NB: distinct from the transient toast `useNotifications` (NotificationContext).
// This hook backs the persistent, server-side notification *feed*.

const FEED_KEY = ['notifications'];
const LIST_KEY = ['notifications', 'list'];
const COUNT_KEY = ['notifications', 'unread-count'];
const POLL_MS = 45_000;

export function mapNotification(n) {
  return {
    id: n.id,
    type: n.type,
    title: n.title,
    body: n.body,
    isRead: n.is_read,
    createdAt: n.created_at,
  };
}

export function useNotificationFeed() {
  const queryClient = useQueryClient();

  const listQuery = useQuery({
    queryKey: LIST_KEY,
    queryFn: () => notificationsApi.fetchNotifications({ limit: 50 }),
    select: (rows) => (rows ?? []).map(mapNotification),
    refetchInterval: POLL_MS,
  });

  const countQuery = useQuery({
    queryKey: COUNT_KEY,
    queryFn: notificationsApi.fetchUnreadCount,
    select: (data) => data?.count ?? 0,
    refetchInterval: POLL_MS,
  });

  // Both list and count live under the FEED_KEY prefix, so one invalidation
  // refreshes the badge and the dropdown together.
  const invalidate = () => queryClient.invalidateQueries({ queryKey: FEED_KEY });

  const markReadMutation = useMutation({
    mutationFn: notificationsApi.markRead,
    onSuccess: invalidate,
  });
  const markAllReadMutation = useMutation({
    mutationFn: notificationsApi.markAllRead,
    onSuccess: invalidate,
  });
  const dismissMutation = useMutation({
    mutationFn: notificationsApi.dismissNotification,
    onSuccess: invalidate,
  });

  return {
    notifications: listQuery.data ?? [],
    unreadCount: countQuery.data ?? 0,
    loading: listQuery.isLoading,
    error: listQuery.error ? listQuery.error.message || 'Kunne ikke hente notifikationer.' : null,
    markRead: markReadMutation.mutateAsync,
    markAllRead: markAllReadMutation.mutateAsync,
    dismiss: dismissMutation.mutateAsync,
  };
}
