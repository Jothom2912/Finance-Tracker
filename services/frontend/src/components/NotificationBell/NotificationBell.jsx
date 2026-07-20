import { useEffect, useRef, useState } from 'react';
import { Bell, X } from 'lucide-react';
import { useNotificationFeed } from '../../hooks/useNotificationFeed';
import './NotificationBell.css';

function formatRelativeTime(iso) {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const diffMs = Date.now() - then;
  const min = Math.floor(diffMs / 60_000);
  if (min < 1) return 'lige nu';
  if (min < 60) return `for ${min} min. siden`;
  const hours = Math.floor(min / 60);
  if (hours < 24) return `for ${hours} ${hours === 1 ? 'time' : 'timer'} siden`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `for ${days} ${days === 1 ? 'dag' : 'dage'} siden`;
  return new Date(iso).toLocaleDateString('da-DK');
}

function NotificationBell() {
  const { notifications, unreadCount, loading, error, markRead, markAllRead, dismiss } =
    useNotificationFeed();
  const [open, setOpen] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [open]);

  const handleItemClick = (n) => {
    if (!n.isRead) markRead(n.id).catch(() => {});
  };

  return (
    <div className="notification-bell" ref={containerRef}>
      <button
        type="button"
        className="notification-bell__trigger"
        aria-label={`Notifikationer${unreadCount > 0 ? ` (${unreadCount} ulæste)` : ''}`}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        data-testid="notification-bell-trigger"
      >
        <Bell size={20} aria-hidden="true" />
        {unreadCount > 0 && (
          <span className="notification-bell__badge" data-testid="notification-bell-badge">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="notification-bell__dropdown" role="menu">
          <div className="notification-bell__header">
            <span>Notifikationer</span>
            {unreadCount > 0 && (
              <button
                type="button"
                className="notification-bell__mark-all"
                onClick={() => markAllRead().catch(() => {})}
              >
                Markér alle læst
              </button>
            )}
          </div>

          <div className="notification-bell__list">
            {loading && <div className="notification-bell__empty">Loader…</div>}
            {error && !loading && <div className="notification-bell__empty">{error}</div>}
            {!loading && !error && notifications.length === 0 && (
              <div className="notification-bell__empty">Ingen notifikationer</div>
            )}
            {notifications.map((n) => (
              <div
                key={n.id}
                className={`notification-bell__item${
                  n.isRead ? '' : ' notification-bell__item--unread'
                }`}
                onClick={() => handleItemClick(n)}
                data-testid="notification-item"
              >
                <div className="notification-bell__item-main">
                  <div className="notification-bell__item-title">{n.title}</div>
                  <div className="notification-bell__item-body">{n.body}</div>
                  <div className="notification-bell__item-time">
                    {formatRelativeTime(n.createdAt)}
                  </div>
                </div>
                <button
                  type="button"
                  className="notification-bell__dismiss"
                  aria-label="Fjern notifikation"
                  onClick={(event) => {
                    event.stopPropagation();
                    dismiss(n.id).catch(() => {});
                  }}
                >
                  <X size={14} aria-hidden="true" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default NotificationBell;
