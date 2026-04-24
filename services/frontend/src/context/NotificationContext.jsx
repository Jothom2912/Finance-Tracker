import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';

const NotificationContext = createContext(null);

const AUTO_DISMISS_MS = 4000;

export function NotificationProvider({ children }) {
  const [notifications, setNotifications] = useState([]);
  const timersRef = useRef({});

  useEffect(() => {
    const timers = timersRef.current;
    return () => Object.values(timers).forEach(clearTimeout);
  }, []);

  const dismiss = useCallback((id) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
    if (timersRef.current[id]) {
      clearTimeout(timersRef.current[id]);
      delete timersRef.current[id];
    }
  }, []);

  const addNotification = useCallback((message, type) => {
    if (!message || !String(message).trim()) {
      return null;
    }

    const id = Date.now() + Math.random();
    setNotifications((prev) => [...prev, { id, message, type }]);

    if (type === 'success') {
      timersRef.current[id] = setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
    }
    return id;
  }, [dismiss]);

  const showError = useCallback((message) => addNotification(message, 'error'), [addNotification]);
  const showSuccess = useCallback((message) => addNotification(message, 'success'), [addNotification]);

  const clearMessages = useCallback(() => {
    Object.values(timersRef.current).forEach(clearTimeout);
    timersRef.current = {};
    setNotifications([]);
  }, []);

  const successNotifications = notifications.filter((n) => n.type === 'success');
  const errorNotifications = notifications.filter((n) => n.type === 'error');

  return (
    <NotificationContext.Provider value={{ showError, showSuccess, clearMessages }}>
      {children}
      {/*
        Two permanent live regions. Screen readers attach their observer to the
        region at the moment it enters the accessibility tree -- if the region
        only exists when a message is present, the message is considered
        pre-existing content and never announced. Rendering both containers
        unconditionally guarantees announcements for every subsequent update.

        Split by priority: role=status/aria-live=polite waits for idle for
        success confirmations, while role=alert/aria-live=assertive interrupts
        for errors. The split cannot be expressed per-message; it must live on
        the region itself.
      */}
      <div className="notification-container">
        <div
          className="notification-group"
          role="status"
          aria-live="polite"
          aria-atomic="true"
          data-testid="notification-polite"
        >
          {successNotifications.map((n) => (
            <div key={n.id} className="notification notification--success">
              <span className="notification__message">{n.message}</span>
              <button
                className="notification__dismiss"
                onClick={() => dismiss(n.id)}
                aria-label="Luk besked"
              >
                &times;
              </button>
            </div>
          ))}
        </div>
        <div
          className="notification-group"
          role="alert"
          aria-live="assertive"
          aria-atomic="true"
          data-testid="notification-assertive"
        >
          {errorNotifications.map((n) => (
            <div key={n.id} className="notification notification--error">
              <span className="notification__message">{n.message}</span>
              <button
                className="notification__dismiss"
                onClick={() => dismiss(n.id)}
                aria-label="Luk besked"
              >
                &times;
              </button>
            </div>
          ))}
        </div>
      </div>
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error('useNotifications must be used within NotificationProvider');
  return ctx;
}
