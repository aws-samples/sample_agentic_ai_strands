import { NextApiRequest, NextApiResponse } from 'next';
import httpProxy from 'http-proxy';
import { IncomingMessage, ServerResponse, ClientRequest } from 'http';

// Disable certificate validation for WebSocket connections to HTTP backend
// This is safe because we're making the request from the server side
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

// This is required for WebSocket proxying
export const config = {
  api: {
    bodyParser: false,
  },
};

// Create a proxy server instance
const proxy = httpProxy.createProxyServer();

// This handler will proxy WebSocket connections to the backend server
export default function handler(req: NextApiRequest, res: NextApiResponse) {
  // Get the target URL from environment variable, same as other API routes
  // Use the protocol specified in SERVER_MCP_BASE_URL
  const baseTarget = process.env.SERVER_MCP_BASE_URL || 'http://localhost:7002';
  
  // Get the WebSocket path from query parameters
  const wsPath = req.query.path as string || '/ws/user-audio';
  
  // Since we're extracting the 'path' parameter to build our target URL,
  // we need to create a clean URL for the backend without this parameter
  // but with all other query parameters preserved
  
  // Create a new URL object to handle query parameters properly
  const targetUrl = new URL(wsPath, baseTarget);
  
  // Copy all query parameters except 'path' (which we've already used)
  Object.keys(req.query).forEach(key => {
    if (key !== 'path') {
      // Handle array query parameters correctly
      const value = req.query[key];
      if (Array.isArray(value)) {
        value.forEach(v => targetUrl.searchParams.append(key, v));
      } else if (value) {
        targetUrl.searchParams.append(key, value as string);
      }
    }
  });
  
  // Form the complete target URL
  const target = targetUrl.toString();
  
  // Log proxy attempt
  console.log(`Proxying connection to ${target}`, {
    originalUrl: req.url,
    query: req.query,
    isWebSocket: req.headers['upgrade']?.toLowerCase() === 'websocket'
  });

  return new Promise<void>((resolve, reject) => {
    // Set up error handling
    proxy.once('error', (err: Error) => {
      console.error('Proxy error:', err);
      res.statusCode = 500;
      res.end('Proxy error');
      reject(err);
    });

    // Handle regular HTTP requests
    proxy.on('proxyReq', (proxyReq: ClientRequest, req: IncomingMessage) => {
      // Forward any authentication headers if present
      if (req.headers.authorization) {
        proxyReq.setHeader('Authorization', req.headers.authorization);
      }
    });

    // Proxy the request - will automatically handle WebSocket upgrades
    proxy.web(req, res, {
      target,
      ws: true, // Enable WebSocket support
      changeOrigin: true,
      secure: false, // Allow insecure connections (HTTP backend from HTTPS frontend)
    }, (err: Error | undefined) => {
      if (err) {
        console.error('Failed to proxy request:', err);
        reject(err);
      } else {
        resolve();
      }
    });
  });
}
