import { NextApiRequest, NextApiResponse } from 'next';
import { getBaseUrl } from '@/lib/api/chat';
import { getBackendHeaders } from '@/lib/api/utils';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ errno: 1, msg: 'Method not allowed' });
  }

  try {
    // Forward the request to the backend with the caller's own access token.
    // The backend derives the user ID from the verified token.
    const baseUrl = getBaseUrl();
    const url = `${baseUrl.replace(/\/$/, '')}/v1/remove/history`;
    
    const response = await fetch(url, {
      method: 'POST',
      headers: await getBackendHeaders(req)
    });
    
    // Get response from backend
    const data = await response.json();
    
    // Return response to client
    return res.status(response.status).json(data);
    
  } catch (error) {
    console.error('Error removing history:', error);
    return res.status(500).json({ errno: 1, msg: 'Failed to remove history' });
  }
}
