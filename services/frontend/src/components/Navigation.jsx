// frontend/finans-tracker-frontend/src/components/Navigation.js
import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import '../styles/Navigation.css';

function Navigation() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <nav className="navbar">
      <div className="navbar-container">
        <div className="navbar-brand">
          <Link to="/dashboard" className="brand-link">
            💰 Finans Tracker
          </Link>
        </div>

        <ul className="navbar-menu">
          <li><Link to="/dashboard" className="nav-link" data-cy="nav-dashboard">Dashboard</Link></li>
          <li><Link to="/transactions" className="nav-link" data-cy="nav-transactions">Transaktioner</Link></li>
          <li><Link to="/categories" className="nav-link" data-cy="nav-categories">Kategorier</Link></li>
          <li><Link to="/budget" className="nav-link" data-cy="nav-budget">Budget</Link></li>
          <li><Link to="/goals" className="nav-link" data-cy="nav-goals">Mål</Link></li>
        </ul>

        <div className="navbar-user">
          <span className="user-info">
            Logget ind som: <strong>{user?.username}</strong>
          </span>
          <button onClick={handleLogout} className="logout-button">
            Log ud
          </button>
        </div>
      </div>
    </nav>
  );
}

export default Navigation;
