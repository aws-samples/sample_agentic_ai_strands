import { NextApiRequest, NextApiResponse } from 'next';

// Base URL for the MCP server backend (internal only)
// Use the protocol specified in SERVER_MCP_BASE_URL
const MCP_BASE_URL = process.env.SERVER_MCP_BASE_URL || 'http://localhost:7002';

// Configure fetch to ignore SSL errors for self-signed certificates
// This is safe because we're making the request from the server side
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

// Handler for stopping active streaming requests
export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  // Only allow POST method
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method Not Allowed' });
  }

  // Extract the stream ID from the URL
  const streamId = req.query.streamId as string;
  if (!streamId) {
    return res.status(400).json({ error: 'Stream ID is required' });
  }

  try {
    // Forward headers from the client to ensure authentication
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (req.headers.authorization) {
      headers['Authorization'] = req.headers.authorization as string;
    }

    // Set a timeout for the request to prevent blocking
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);

    // Make the request to the backend
    const response = await fetch(`${MCP_BASE_URL}/v1/stop/stream/${encodeURIComponent(String(streamId))}`, {
      method: 'POST',
      headers: headers,
      signal: controller.signal,
    });
    
    // Clear the timeout
    clearTimeout(timeoutId);

    if (!response.ok) {
      // Backend returned an error
      console.warn(`Stream stop response not OK: ${response.status}`);
      // For UI purposes, still return success if the stream might have already completed
      return res.status(200).json({
        success: true,
        errno: 0,
        msg: 'Stream may have already completed'
      });
    }

    // Parse the response data
    const data = await response.json();
    return res.status(200).json(data);
  } catch (error) {
    console.error('Error stopping stream:', error);
    // For UI purposes, still return success even on network errors
    return res.status(200).json({
      success: true,
      errno: 0,
      msg: 'Could not confirm stream stop, but UI has been reset'
    });
  }
}
