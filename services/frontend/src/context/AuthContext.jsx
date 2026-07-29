// frontend/finans-tracker-frontend/src/context/AuthContext.js
import { createContext, useState, useContext, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { clearAuthStorage } from '../utils/authStorage';
import { isTokenExpired } from '../utils/jwt';
import { handleUnauthorized } from '../utils/handleUnauthorized';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const queryClient = useQueryClient();
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  // Initialize from localStorage on mount
  useEffect(() => {
    const savedToken = localStorage.getItem('access_token');
    const savedUserId = localStorage.getItem('user_id');
    const savedUsername = localStorage.getItem('username');

    if (savedToken && savedUserId && savedUsername) {
      if (isTokenExpired(savedToken)) {
        clearAuthStorage();
      } else {
        setUser({
          id: parseInt(savedUserId),
          username: savedUsername
        });
        setToken(savedToken);
      }
    }

    setLoading(false);
  }, []);

  const login = (response) => {
    queryClient.clear();

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

  // F2-08. `username` i localStorage kommer fra LOGIN-svaret, ikke fra
  // tokenet — så uden dette viser navigationen det gamle navn indtil
  // brugeren logger ind igen. Det er systemets eneste ægte kopi af
  // brugernavnet der kan komme ud af sync (de øvrige er account-services
  // synkrone HTTP-fetch, som er frisk per konstruktion, og JWT-claims
  // som ingen læser). Derfor fixes det her og ikke med et event.
  const updateUser = (partial) => {
    setUser((prev) => (prev ? { ...prev, ...partial } : prev));
    if (partial.username !== undefined) {
      localStorage.setItem('username', partial.username);
    }
  };

  const logout = () => {
    queryClient.clear();
    clearAuthStorage();
    setUser(null);
    setToken(null);
  };

  const isAuthenticated = () => {
    if (!token || !user) return false;

    if (isTokenExpired(token)) {
      // Token outlived its exp claim while the SPA stayed mounted (bootstrap
      // already filters out stale tokens on load). Route through the same
      // cleanup path used for 401 responses.
      handleUnauthorized();
      return false;
    }

    return true;
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
      updateUser,
      isAuthenticated,
      getAuthHeader
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
