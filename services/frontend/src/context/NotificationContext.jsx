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

  return (
    <NotificationContext.Provider value={{ showError, showSuccess, clearMessages }}>
      {children}
      {notifications.length > 0 && (
        <div className="notification-container" role="status" aria-live="polite">
          {notifications.map((n) => (
            <div key={n.id} className={`notification notification--${n.type}`}>
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
      )}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error('useNotifications must be used within NotificationProvider');
  return ctx;
}
