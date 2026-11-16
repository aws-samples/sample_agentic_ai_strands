/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Set up environment variables for server-side code
  env: {
    SERVER_MCP_BASE_URL: process.env.SERVER_MCP_BASE_URL,
  },
  // No CORS headers: the UI calls its own /api routes from the same origin.
  // Configure server settings
  serverRuntimeConfig: {
    // Keep connections alive for streaming
    keepAliveTimeout: 120000*10, // 20 minutes
  }
};

module.exports = nextConfig;
