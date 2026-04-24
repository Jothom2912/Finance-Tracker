import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import './App.css';

import { AuthProvider, useAuth } from './context/AuthContext';
import { NotificationProvider } from './context/NotificationContext';
import { ConfirmDialogProvider } from './components/ConfirmDialog/ConfirmDialog';
import ErrorBoundary from './components/ErrorBoundary/ErrorBoundary';
import Navigation from './components/Navigation';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import AccountSelector from './pages/AccountSelector';

import DashboardPage from './pages/DashboardPage';
import TransactionsPage from './pages/TransactionsPage';
import CategoriesPage from './pages/CategoriesPage';
import BudgetPage from './pages/BudgetPage/BudgetPage';
import GoalPage from './pages/GoalPage/GoalPage';
import BankCallbackPage from './pages/BankCallbackPage';

function AppContent() {
  return (
    <div className="App">
      <Navigation />
      <main>
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/transactions" element={<TransactionsPage />} />
            <Route path="/categories" element={<CategoriesPage />} />
            <Route path="/budget" element={<BudgetPage />} />
            <Route path="/goals" element={<GoalPage />} />
          </Routes>
        </ErrorBoundary>
      </main>
    </div>
  );
}

function App() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <div style={{ padding: '20px', textAlign: 'center' }}>Loader...</div>;
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/bank/callback" element={<BankCallbackPage />} />
      <Route
        path="/account-selector"
        element={isAuthenticated() ? <AccountSelector /> : <Navigate to="/login" replace />}
      />
      <Route
        path="/*"
        element={isAuthenticated() ? <AppContent /> : <Navigate to="/login" replace />}
      />
    </Routes>
  );
}

function AppWithAuth() {
  return (
    <AuthProvider>
      <NotificationProvider>
        <ConfirmDialogProvider>
          <App />
        </ConfirmDialogProvider>
      </NotificationProvider>
    </AuthProvider>
  );
}

export default AppWithAuth;
