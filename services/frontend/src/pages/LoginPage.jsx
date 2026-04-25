import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import apiClient from '../utils/apiClient';
import { USER_SERVICE_URL } from '../config/serviceUrls';
import '../styles/LoginPage.css';

function LoginPage() {
  const navigate = useNavigate();
  const { login, handleLoginFallback } = useAuth();
  const [formData, setFormData] = useState({ username_or_email: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await apiClient.post(`${USER_SERVICE_URL}/login`, formData);

      if (!response.ok) {
        const errorData = await response.json();
        if (response.status === 403 || errorData.accounts) {
          handleLoginFallback(formData.username_or_email, errorData.accounts || []);
          navigate('/account-selector');
          return;
        }
        throw new Error(errorData.detail || 'Login failed');
      }

      const data = await response.json();
      login(data);
      navigate('/account-selector');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>Finans Tracker</h1>
          <p>Log ind på din konto</p>
        </div>

        {error && <div className="error-message">{error}</div>}

        <form onSubmit={handleLoginSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="username_or_email">Brugernavn eller Email:</label>
            <input
              type="text"
              id="username_or_email"
              name="username_or_email"
              value={formData.username_or_email}
              onChange={handleChange}
              placeholder="Indtast brugernavn eller email"
              required
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Adgangskode:</label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="Indtast adgangskode"
              required
              disabled={loading}
            />
          </div>

          <button type="submit" className="login-button" disabled={loading}>
            {loading ? 'Logger ind...' : 'Log ind'}
          </button>
        </form>

        <div className="login-footer">
          <p>Har du ikke en konto? <Link to="/register">Opret konto her</Link></p>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
