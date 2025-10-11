import { NextApiRequest, NextApiResponse } from 'next';
import { getBaseUrl } from '@/lib/api/chat';
import { getAuthHeaders } from '@/lib/auth';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ errno: 1, msg: 'Method not allowed' });
  }

  try {
    // Get user ID from headers
    const userId = req.headers['x-user-id'] as string;
    if (!userId) {
      return res.status(400).json({ errno: 1, msg: 'User ID is required' });
    }

    // Get auth headers
    const headers: Record<string, string> = await getAuthHeaders(userId);

    // Forward X-AgentCore-Runtime-ARN header if present
    if (req.headers['x-agentcore-runtime-arn']) {
      headers['X-AgentCore-Runtime-ARN'] = req.headers['x-agentcore-runtime-arn'] as string;
    }

    // Get base URL
    const baseUrl = getBaseUrl();
    const url = `${baseUrl.replace(/\/$/, '')}/v1/remove/history`;

    // Make the request to backend
    const response = await fetch(url, {
      method: 'POST',
      headers
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
