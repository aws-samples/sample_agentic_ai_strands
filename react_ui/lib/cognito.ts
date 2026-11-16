import { Amplify } from 'aws-amplify';
import { fetchAuthSession, signOut as amplifySignOut } from 'aws-amplify/auth';

let configurePromise: Promise<boolean> | null = null;

/**
 * Load the Cognito settings from /api/auth/config and configure Amplify Auth.
 * Resolves to false when Cognito is not configured on the server.
 */
export function configureCognito(): Promise<boolean> {
  if (!configurePromise) {
    configurePromise = (async () => {
      const res = await fetch('/api/auth/config', { cache: 'no-store' });
      if (!res.ok) return false;
      const { userPoolId, userPoolClientId } = await res.json();
      if (!userPoolId || !userPoolClientId) return false;
      Amplify.configure({
        Auth: {
          Cognito: {
            userPoolId,
            userPoolClientId,
            loginWith: { email: true },
          },
        },
      });
      return true;
    })().catch((error) => {
      console.error('Failed to load Cognito configuration:', error);
      configurePromise = null; // allow a retry
      return false;
    });
  }
  return configurePromise;
}

/**
 * Current Cognito access token (refreshed automatically by Amplify), or
 * undefined when the user is not signed in.
 */
export async function getAccessToken(): Promise<string | undefined> {
  try {
    const session = await fetchAuthSession();
    return session.tokens?.accessToken?.toString();
  } catch (error) {
    console.error('Failed to get Cognito session:', error);
    return undefined;
  }
}

/** Sign out and drop locally cached chat data of the previous user. */
export async function signOut(): Promise<void> {
  await amplifySignOut();
  localStorage.removeItem('mcp-chat-store');
  localStorage.removeItem('mcp_chat_user_id');
  window.location.reload();
}
