import {LoginEntry} from './login-entry';
import {useEffect, useState} from 'react';
import {useAuthStore} from '../../../packages/core/auth';
import {Button} from '@workpal/ui/components/ui/button';
import {Input} from '@workpal/ui/components/ui/input';

export function VerificationLogin() {
  const expired = useAuthStore(state => state.expired);
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [loading, setLoading] = useState(true);
  const [developmentAuth, setDevelopmentAuth] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setDevelopmentAuth(false);
    fetch('/api/config', {credentials: 'include'})
      .then(response => {if (!response.ok) throw Error(); return response.json();})
      .then(config => {
        if (!active) return;
        const enabled = config.development_auth === true;
        setDevelopmentAuth(enabled);
        if (enabled) setEmail(value => value || 'dev@workpal.local');
        else setError('Email sign-in is not available on this server.');
      })
      .catch(() => {if (active) setError('Unable to load sign-in options. Try again.');})
      .finally(() => {if (active) setLoading(false);});
    return () => {active = false;};
  }, [attempt]);

  return <LoginEntry>
    {expired && <p className="login-entry-notice" role="status">Your session ended. Sign in again.</p>}
    <form className="login-entry-form" onSubmit={async event => {
      event.preventDefault();
      if (!developmentAuth || loading || busy) return;
      setBusy(true); setError('');
      try {
        // The server explicitly enables this local development credential.
        // Keep verification on the backend while temporarily hiding its field.
        await useAuthStore.getState().verifyCode(email, '888888');
      } catch {
        setError('Unable to sign in. Check your email, then try again.');
      } finally {setBusy(false);}
    }}>
      <div className="login-entry-field">
        <label htmlFor="login-email">Email</label>
        <Input id="login-email" name="email" type="email" inputMode="email" autoComplete="email" autoCapitalize="none" spellCheck={false} required aria-describedby={error ? 'login-error' : undefined} value={email} onChange={event => setEmail(event.target.value)}/>
        {error && <p id="login-error" className="login-entry-error" role="alert">{error}</p>}
      </div>
      <Button type="submit" disabled={busy || loading || !developmentAuth}>{busy ? 'Signing in…' : 'Sign in'}</Button>
    </form>
    {error && <Button className="login-entry-retry" type="button" variant="ghost" size="sm" onClick={() => {setError(''); setAttempt(value => value + 1);}}>Retry sign-in options</Button>}
  </LoginEntry>;
}
