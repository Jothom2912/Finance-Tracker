import React from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { Wallet } from 'lucide-react';
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
            <Wallet className="brand-icon" aria-hidden="true" size={20} />
            Finans Tracker
          </Link>
        </div>

        <ul className="navbar-menu">
          <li><NavLink to="/dashboard" end className="nav-link">Dashboard</NavLink></li>
          <li><NavLink to="/transactions" end className="nav-link">Transaktioner</NavLink></li>
          <li><NavLink to="/categories" end className="nav-link">Kategorier</NavLink></li>
          <li><NavLink to="/budget" end className="nav-link">Budget</NavLink></li>
          <li><NavLink to="/goals" end className="nav-link">Mål</NavLink></li>
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
