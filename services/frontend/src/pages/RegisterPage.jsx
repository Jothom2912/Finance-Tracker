import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import apiClient from '../utils/apiClient';
import '../styles/RegisterPage.css';

const USER_SERVICE_URL =
  import.meta.env.VITE_USER_SERVICE_URL || 'http://localhost:8001/api/v1/users';

function RegisterPage() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    password_confirm: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');

    if (formData.password !== formData.password_confirm) {
      setError('Adgangskoderne matcher ikke');
      return;
    }
    if (formData.password.length < 8) {
      setError('Adgangskode skal være mindst 8 tegn');
      return;
    }

    setLoading(true);

    try {
      const response = await apiClient.post(`${USER_SERVICE_URL}/register`, {
        username: formData.username,
        email: formData.email,
        password: formData.password,
      });

      if (!response.ok) {
        let errorMessage = 'Registration failed';
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch {
          errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        }
        throw new Error(errorMessage);
      }

      navigate('/login', { state: { message: 'Konto oprettet! Log ind nu.' } });
    } catch (err) {
      if (err.name === 'AbortError') {
        setError('Request timeout - serveren svarer ikke. Prøv igen.');
      } else {
        setError(err.message || 'Der opstod en fejl ved oprettelse af konto');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="register-container">
      <div className="register-card">
        <div className="register-header">
          <h1>Finans Tracker</h1>
          <p>Opret din konto</p>
        </div>

        {error && <div className="error-message">{error}</div>}

        <form onSubmit={handleRegister} className="register-form">
          <div className="form-group">
            <label htmlFor="username">Brugernavn:</label>
            <input type="text" id="username" name="username" data-cy="username-input" value={formData.username} onChange={handleChange} placeholder="Vælg et brugernavn (3-20 tegn)" required disabled={loading} minLength="3" maxLength="20" />
          </div>

          <div className="form-group">
            <label htmlFor="email">Email:</label>
            <input type="email" id="email" name="email" data-cy="email-input" value={formData.email} onChange={handleChange} placeholder="Indtast din email" required disabled={loading} />
          </div>

          <div className="form-group">
            <label htmlFor="password">Adgangskode:</label>
            <input type="password" id="password" name="password" data-cy="password-input" value={formData.password} onChange={handleChange} placeholder="Mindst 8 tegn" required disabled={loading} minLength="8" />
          </div>

          <div className="form-group">
            <label htmlFor="password_confirm">Bekræft adgangskode:</label>
            <input type="password" id="password_confirm" name="password_confirm" data-cy="password-confirm-input" value={formData.password_confirm} onChange={handleChange} placeholder="Gentag adgangskode" required disabled={loading} />
          </div>

          <button type="submit" className="register-button" data-cy="register-button" disabled={loading}>
            {loading ? 'Opretter konto...' : 'Opret konto'}
          </button>
        </form>

        <div className="register-footer">
          <p>Har du allerede en konto? <Link to="/login">Log ind her</Link></p>
        </div>
      </div>
    </div>
  );
}

export default RegisterPage;
