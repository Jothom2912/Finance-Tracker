import React from 'react';

const MessageDisplay = ({ message, type = 'info' }) => {
  if (!message) return null;

  const styles = {
    padding: '8px 12px',
    marginBottom: '8px',
    borderRadius: '4px',
    fontSize: '14px',
    backgroundColor: type === 'error' ? '#fef2f2' : type === 'success' ? '#f0fdf4' : '#f0f9ff',
    color: type === 'error' ? '#991b1b' : type === 'success' ? '#166534' : '#1e40af',
    border: `1px solid ${type === 'error' ? '#fecaca' : type === 'success' ? '#bbf7d0' : '#bfdbfe'}`,
  };

  return <div style={styles}>{message}</div>;
};

export default MessageDisplay;
