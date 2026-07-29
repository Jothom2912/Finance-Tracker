import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNotifications } from '../hooks/useNotifications';
import { fetchMe, changePassword, changeUsername } from '../api/users';
import './ProfilePage.css';

/**
 * F2-08: profil & indstillinger — den første skrive-sti til en
 * eksisterende bruger.
 *
 * Email og oprettelsesdato er read-only her med vilje. En email-ændring
 * uden en verifikations-sti er account-takeover-halvdelen af et
 * password-reset uden sikkerheds-halvdelen; den hører i F2-09, hvor
 * verifikationen lander.
 *
 * Formularmønsteret er RulesPage.jsx's: useState per felt, validering i
 * handleSubmit, fejl gennem den globale toast. React Hook Form + Zod er
 * ikke i brug nogen steder i dette repo.
 */
function ProfilePage() {
  const { updateUser } = useAuth();
  const { showError, showSuccess } = useNotifications();

  const [profile, setProfile] = useState(null);
  const [loadError, setLoadError] = useState('');

  // Feltet starter TOMT og udfyldes af serveren, ikke af `user?.username`.
  // Med en optimistisk startværdi ville brugeren kunne taste i feltet mens
  // fetchMe stadig var undervejs, hvorefter svaret overskrev det tastede —
  // og et submit ville så gemme det gamle navn. Målt: e2e-specen var rød på
  // netop den race under fuld suite-belastning. Derfor er inputtet også
  // disabled indtil profilen er hentet.
  const [username, setUsername] = useState('');
  const [savingUsername, setSavingUsername] = useState(false);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [savingPassword, setSavingPassword] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchMe()
      .then((me) => {
        if (cancelled) return;
        setProfile(me);
        // Serveren er kilden til brugernavnet, ikke localStorage — hvis
        // de er uenige, er det localStorage der er forældet.
        setUsername(me.username);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err.message || 'Kunne ikke hente din profil.');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleUsernameSubmit = async (e) => {
    e.preventDefault();
    const trimmed = username.trim();
    if (trimmed.length < 3 || trimmed.length > 50) {
      showError('Brugernavn skal være mellem 3 og 50 tegn.');
      return;
    }
    setSavingUsername(true);
    try {
      const updated = await changeUsername({ username: trimmed });
      setProfile(updated);
      setUsername(updated.username);
      // Uden dette viser navigationen det gamle navn indtil re-login:
      // `username` i localStorage stammer fra login-svaret.
      updateUser({ username: updated.username });
      showSuccess('Brugernavn opdateret.');
    } catch (err) {
      showError(err.message || 'Kunne ikke opdatere brugernavnet.');
    } finally {
      setSavingUsername(false);
    }
  };

  const handlePasswordSubmit = async (e) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      showError('Adgangskoderne matcher ikke.');
      return;
    }
    if (newPassword.length < 8) {
      showError('Adgangskode skal være mindst 8 tegn.');
      return;
    }
    if (newPassword === currentPassword) {
      showError('Den nye adgangskode skal være forskellig fra den nuværende.');
      return;
    }
    setSavingPassword(true);
    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      showSuccess('Adgangskode ændret. Du er stadig logget ind på denne enhed.');
    } catch (err) {
      showError(err.message || 'Kunne ikke ændre adgangskoden.');
    } finally {
      setSavingPassword(false);
    }
  };

  return (
    <div className="profile-page">
      <div className="profile-page-header">
        <h1>Min profil</h1>
        <p className="header-subtitle">Se dine kontooplysninger og skift adgangskode</p>
      </div>

      {loadError && <p className="message-display error">Fejl: {loadError}</p>}

      <section className="profile-section" aria-label="Kontooplysninger">
        <h2>Kontooplysninger</h2>
        <dl className="profile-details">
          <dt>Email</dt>
          <dd data-testid="profile-email">{profile?.email ?? '—'}</dd>
          <dt>Oprettet</dt>
          <dd>
            {profile?.created_at ? new Date(profile.created_at).toLocaleDateString('da-DK') : '—'}
          </dd>
        </dl>
        <p className="profile-section-hint">
          Email kan ikke ændres endnu — det kræver en bekræftelses-mail, så en anden ikke
          kan overtage din konto.
        </p>
      </section>

      <section className="profile-section" aria-label="Brugernavn">
        <h2>Brugernavn</h2>
        <form className="profile-form" onSubmit={handleUsernameSubmit}>
          <div className="form-group">
            <label htmlFor="profile-username">Brugernavn:</label>
            <input
              id="profile-username"
              data-testid="profile-username-input"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              minLength="3"
              maxLength="50"
              required
              disabled={savingUsername || !profile}
            />
          </div>
          <div className="form-actions">
            <button
              type="submit"
              className="button"
              data-testid="profile-username-submit"
              disabled={savingUsername || !profile}
            >
              {savingUsername ? 'Gemmer…' : 'Gem brugernavn'}
            </button>
          </div>
        </form>
      </section>

      <section className="profile-section" aria-label="Adgangskode">
        <h2>Adgangskode</h2>
        <form className="profile-form" onSubmit={handlePasswordSubmit}>
          <div className="form-group">
            <label htmlFor="profile-current-password">Nuværende adgangskode:</label>
            <input
              id="profile-current-password"
              data-testid="profile-current-password"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              disabled={savingPassword}
            />
          </div>
          <div className="form-group">
            <label htmlFor="profile-new-password">Ny adgangskode:</label>
            <input
              id="profile-new-password"
              data-testid="profile-new-password"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Mindst 8 tegn"
              minLength="8"
              required
              disabled={savingPassword}
            />
          </div>
          <div className="form-group">
            <label htmlFor="profile-confirm-password">Bekræft ny adgangskode:</label>
            <input
              id="profile-confirm-password"
              data-testid="profile-confirm-password"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              disabled={savingPassword}
            />
          </div>
          <div className="form-actions">
            <button
              type="submit"
              className="button"
              data-testid="profile-password-submit"
              disabled={savingPassword}
            >
              {savingPassword ? 'Gemmer…' : 'Skift adgangskode'}
            </button>
          </div>
        </form>
        <p className="profile-section-hint">
          Bemærk: et skift logger dig ikke ud af andre enheder. Er du logget ind et sted du
          ikke stoler på, forbliver den session gyldig i op til en time.
        </p>
      </section>
    </div>
  );
}

export default ProfilePage;
