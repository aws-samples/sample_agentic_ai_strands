import { NextApiRequest, NextApiResponse } from 'next';

/**
 * Public Amazon Cognito settings for the browser sign-in flow.
 *
 * The user pool ID and app client ID are public identifiers, not secrets
 * (the app client has no client secret). They are read at runtime so the same
 * container image works with any user pool.
 */
export default function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return res.status(405).json({ error: 'Method not allowed' });
  }
  const userPoolId = process.env.COGNITO_USER_POOL_ID || '';
  const userPoolClientId = process.env.COGNITO_APP_CLIENT_ID || '';
  res.setHeader('Cache-Control', 'no-store');
  res.status(200).json({ userPoolId, userPoolClientId });
}
