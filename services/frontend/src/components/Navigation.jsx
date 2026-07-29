
import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { Wallet, ChevronDown } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import NotificationBell from './NotificationBell/NotificationBell';
import '../styles/Navigation.css';

function Navigation() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  // Click-outside-mønsteret er NotificationBell.jsx:27-36's: lytteren
  // hænges kun på mens menuen er åben, og pilles ned igen med den.
  useEffect(() => {
    if (!menuOpen) return undefined;
    const onClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setMenuOpen(false);
      }
    };
    // Escape-lukning, som klokken IKKE har. Den er retrofittet her og
    // ikke dér med vilje — at rette klokken samtidig ville blande to
    // ændringer i én commit; det er sit eget lille item.
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('mousedown', onClickOutside);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onClickOutside);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [menuOpen]);

  const handleLogout = () => {
    setMenuOpen(false);
    logout();
    navigate('/login');
  };

  const handleProfile = () => {
    setMenuOpen(false);
    navigate('/profile');
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
          <li><NavLink to="/rules" end className="nav-link">Regler</NavLink></li>
          <li><NavLink to="/budget" end className="nav-link">Budget</NavLink></li>
          <li><NavLink to="/goals" end className="nav-link">Mål</NavLink></li>
          <li><NavLink to="/chat" end className="nav-link">Finans Chat</NavLink></li>
        </ul>

        <div className="navbar-user">
          <NotificationBell />
          <div className="user-menu" ref={menuRef}>
            <button
              type="button"
              className="user-menu__trigger"
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((v) => !v)}
              data-testid="user-menu-trigger"
            >
              {/* Navnet kommer fra AuthContext's `user`, ikke fra localStorage
                  direkte — det er derfor updateUser() får navigationen til at
                  opdatere sig uden reload efter et brugernavn-skift. */}
              <strong data-testid="user-menu-username">{user?.username}</strong>
              <ChevronDown size={16} aria-hidden="true" />
            </button>

            {menuOpen && (
              <div className="user-menu__dropdown" role="menu">
                <button
                  type="button"
                  role="menuitem"
                  className="user-menu__item"
                  onClick={handleProfile}
                  data-testid="user-menu-profile"
                >
                  Min profil
                </button>
                <button
                  type="button"
                  role="menuitem"
                  className="user-menu__item"
                  onClick={handleLogout}
                  data-testid="user-menu-logout"
                >
                  Log ud
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}

export default Navigation;
