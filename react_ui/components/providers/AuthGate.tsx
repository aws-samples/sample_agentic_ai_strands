'use client';

import { useEffect, useState } from 'react';
import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import { configureCognito } from '@/lib/cognito';
import { useStore } from '@/lib/store';

/** Sets the display user ID in the store from the signed-in Cognito user. */
function SignedInUser({ loginId, children }: { loginId: string; children: React.ReactNode }) {
  const { userId, setUserId } = useStore();

  useEffect(() => {
    if (loginId && loginId !== userId) {
      setUserId(loginId);
    }
  }, [loginId, userId, setUserId]);

  if (!userId) return null;
  return <>{children}</>;
}

/**
 * Renders children only for a user signed in to the Cognito user pool.
 * Self sign-up is hidden: administrators create users in the user pool.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<'loading' | 'ready' | 'unconfigured'>('loading');

  useEffect(() => {
    configureCognito().then((ok) => setState(ok ? 'ready' : 'unconfigured'));
  }, []);

  if (state === 'loading') {
    return null;
  }

  if (state === 'unconfigured') {
    return (
      <div className="flex h-screen items-center justify-center p-8 text-center">
        <p className="max-w-md text-sm text-muted-foreground">
          Sign-in is not configured. Set COGNITO_USER_POOL_ID and COGNITO_APP_CLIENT_ID
          for the frontend server and restart it.
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <Authenticator hideSignUp>
        {({ user }) => (
          <SignedInUser loginId={user?.signInDetails?.loginId || user?.username || ''}>
            {children}
          </SignedInUser>
        )}
      </Authenticator>
    </div>
  );
}
