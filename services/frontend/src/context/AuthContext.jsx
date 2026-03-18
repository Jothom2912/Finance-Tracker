// frontend/finans-tracker-frontend/src/context/AuthContext.js
import React, { createContext, useState, useContext, useEffect } from 'react';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  // Initialize from localStorage on mount
  useEffect(() => {
    const savedToken = localStorage.getItem('access_token');
    const savedUserId = localStorage.getItem('user_id');
    const savedUsername = localStorage.getItem('username');

    if (savedToken && savedUserId && savedUsername) {
      setUser({
        id: parseInt(savedUserId),
        username: savedUsername
      });
      setToken(savedToken);
    }
    
    setLoading(false);
  }, []);

  const login = (response) => {
    // response = { access_token, token_type, user_id, username }
    localStorage.setItem('access_token', response.access_token);
    localStorage.setItem('user_id', response.user_id);
    localStorage.setItem('username', response.username);

    setUser({
      id: response.user_id,
      username: response.username
    });
    setToken(response.access_token);
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_id');
    localStorage.removeItem('username');
    localStorage.removeItem('account_id');

    setUser(null);
    setToken(null);
  };

  const handleLoginFallback = (username, accounts) => {
    // Dette bruges hvis login kræver account selection
    // For nu, gemmer vi bare username hvis nødvendigt
    console.log('Login fallback triggered', { username, accounts });
  };

  const isAuthenticated = () => {
    return !!token && !!user;
  };

  const getAuthHeader = () => {
    if (!token) return {};
    return {
      'Authorization': `Bearer ${token}`
    };
  };

  return (
    <AuthContext.Provider value={{
      user,
      token,
      loading,
      login,
      logout,
      isAuthenticated,
      getAuthHeader,
      handleLoginFallback
    }}>
      {children}
    </AuthContext.Provider>
  );
};

// Hook to use auth context
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
