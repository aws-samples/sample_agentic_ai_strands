import { getAccessToken } from './cognito';

/**
 * SECURITY NOTE: API keys should NEVER be exposed to the client.
 * This function is deprecated and should not be used in client-side code.
 *
 * @deprecated Requests are authenticated with the signed-in user's Cognito access token.
 */
export async function getApiKey(): Promise<string> {
  throw new Error(
    'SECURITY: Direct API key access is disabled. ' +
    'Requests are authenticated with the Cognito access token instead.'
  );
}

/**
 * Get auth headers for backend API requests.
 *
 * The backend identifies the user ONLY from the verified Cognito access token
 * (its `sub` claim). No client-chosen user ID is sent.
 *
 * @param _userId - Unused; kept so existing call sites compile.
 */
export const getAuthHeaders = async (_userId?: string) => {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json'
  };
  const token = await getAccessToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}
