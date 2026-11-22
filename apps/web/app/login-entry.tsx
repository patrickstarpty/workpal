import type {ReactNode} from 'react';
import { WorkpalIcon } from '@workpal/ui/components/common/workpal-icon';
import { WorkpalWordmark } from '@workpal/ui/components/common/workpal-wordmark';
import './login-entry.css';

export function LoginEntry({children}: {children: ReactNode}) {
  return (
    <main className="login-entry" aria-labelledby="welcome-title">
      <section className="login-entry-card">
        <div className="login-entry-brand" aria-label="Workpal" role="img" translate="no">
          <WorkpalIcon className="login-entry-mark" size={32} aria-hidden="true" />
          <WorkpalWordmark className="login-entry-wordmark" aria-hidden="true" />
        </div>
        <header className="login-entry-heading">
          <h1 id="welcome-title">Let’s work together.</h1>
        </header>
        {children}
      </section>
    </main>
  );
}
