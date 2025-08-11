// AWS DCV utility functions

import { BrowserInitToolResult, DCVDisplayLayout } from './types';

/**
 * Extract presigned URL from browser_init tool result
 */
export function extractPresignedUrl(toolResult: string): string | null {
  if (!toolResult || typeof toolResult !== 'string') {
    return null;
  }

  // Look for <presigned_url>URL</presigned_url> pattern
  const match = toolResult.match(/<presigned_url>(.*?)<\/presigned_url>/i);
  return match ? match[1].trim() : null;
}

/**
 * Validate if a URL looks like a valid DCV presigned URL
 */
export function validatePresignedUrl(url: string): boolean {
  if (!url || typeof url !== 'string') {
    return false;
  }

  try {
    const parsedUrl = new URL(url);
    
    // Basic validation - should be HTTPS and have required query parameters
    if (parsedUrl.protocol !== 'https:') {
      return false;
    }

    // Check for typical DCV URL patterns
    const hostname = parsedUrl.hostname.toLowerCase();
    if (!hostname.includes('dcv') && !hostname.includes('amazonaws.com')) {
      // Could be a custom DCV server, so we'll be more lenient
      console.warn('URL may not be a standard AWS DCV URL:', hostname);
    }

    // Check for required query parameters (token, expires, etc.)
    const hasToken = parsedUrl.searchParams.has('token') || 
                    parsedUrl.searchParams.has('auth-token') ||
                    parsedUrl.searchParams.has('authToken');
                    
    if (!hasToken) {
      console.warn('Presigned URL may be missing authentication token');
    }

    return true;
  } catch (error) {
    console.error('Invalid URL format:', error);
    return false;
  }
}

/**
 * Create DCV viewer URL for Next.js dynamic route
 */
export function createDCVViewerUrl(presignedUrl: string): string {
  if (!validatePresignedUrl(presignedUrl)) {
    throw new Error('Invalid presigned URL');
  }

  // Encode the presigned URL for use in Next.js dynamic route
  const encodedUrl = encodeURIComponent(presignedUrl);
  return `/dcv-viewer/${encodedUrl}`;
}

/**
 * Parse browser_init tool result into structured data
 */
export function parseBrowserInitResult(toolResult: string): BrowserInitToolResult {
  const presignedUrl = extractPresignedUrl(toolResult);
  
  if (!presignedUrl) {
    return {
      presignedUrl: '',
      success: false,
      message: 'No presigned URL found in tool result'
    };
  }

  if (!validatePresignedUrl(presignedUrl)) {
    return {
      presignedUrl,
      success: false,
      message: 'Invalid presigned URL format'
    };
  }

  // Extract session ID from the presigned URL path
  // URL format: https://bedrock-agentcore.us-west-2.amazonaws.com/browser-streams/aws.browser.v1/sessions/[SESSION_ID]/live-view?...
  let sessionId: string | undefined;
  try {
    const url = new URL(presignedUrl);
    const pathParts = url.pathname.split('/');
    const sessionsIndex = pathParts.findIndex(part => part === 'sessions');
    if (sessionsIndex !== -1 && pathParts[sessionsIndex + 1]) {
      sessionId = pathParts[sessionsIndex + 1];
    }
  } catch (error) {
    console.warn('Failed to extract session ID from URL:', error);
  }
  
  // Fallback: try to extract session ID from the result text if URL parsing fails
  if (!sessionId) {
    const sessionIdMatch = toolResult.match(/session[_\s]*id[:\s]*([a-zA-Z0-9\-_]+)/i);
    sessionId = sessionIdMatch ? sessionIdMatch[1] : undefined;
  }

  return {
    presignedUrl,
    sessionId,
    success: true,
    message: 'Browser session ready for live view'
  };
}

/**
 * Available display layouts for DCV viewer
 */
export const DISPLAY_LAYOUTS: DCVDisplayLayout[] = [
  { width: 1280, height: 720, label: 'HD (1280×720)' },
  { width: 1600, height: 900, label: 'HD+ (1600×900)' },
  { width: 1920, height: 1080, label: 'Full HD (1920×1080)' },
  { width: 2560, height: 1440, label: '2K (2560×1440)' }
];

/**
 * Get default display layout
 */
export function getDefaultDisplayLayout(): DCVDisplayLayout {
  return DISPLAY_LAYOUTS[1]; // HD+ (1600×900)
}

/**
 * Check if DCV SDK is loaded
 */
export function isDCVSDKLoaded(): boolean {
  return typeof window !== 'undefined' && 
         typeof window.dcv !== 'undefined' && 
         typeof window.dcv.authenticate === 'function' &&
         typeof window.dcv.connect === 'function';
}

/**
 * Load DCV SDK dynamically (if not already loaded)
 */
export function loadDCVSDK(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (isDCVSDKLoaded()) {
      resolve();
      return;
    }

    // Check if script is already being loaded
    const existingScript = document.querySelector('script[src="/dcvjs/dcv.js"]');
    if (existingScript) {
      existingScript.addEventListener('load', () => resolve());
      existingScript.addEventListener('error', reject);
      return;
    }

    // Create and load the script
    const script = document.createElement('script');
    script.src = '/dcvjs/dcv.js';
    script.async = true;
    
    script.onload = () => {
      // Set worker path with full URL to avoid relative path issues
      if (window.dcv?.setWorkerPath) {
        const workerPath = `${window.location.origin}/dcvjs/dcv/`;
        window.dcv.setWorkerPath(workerPath);
        console.log('DCV worker path set to:', workerPath);
      }
      resolve();
    };
    
    script.onerror = () => {
      reject(new Error('Failed to load DCV SDK'));
    };

    document.head.appendChild(script);
  });
}

/**
 * Generate unique container ID for DCV display (client-side only)
 */
export function generateDCVContainerId(): string {
  // Use a simple counter with fallback to avoid hydration issues
  if (typeof window === 'undefined') {
    // During SSR, return a predictable ID
    return 'dcv-display-container';
  }
  
  // Client-side: generate unique ID
  const timestamp = Date.now();
  const random = Math.random().toString(36).substr(2, 9);
  return `dcv-display-${timestamp}-${random}`;
}

/**
 * Generate static container ID for SSR compatibility
 */
export function getStaticDCVContainerId(): string {
  return 'dcv-display-container';
}

/**
 * Format error message for display
 */
export function formatDCVError(error: any): string {
  if (typeof error === 'string') {
    return error;
  }

  if (error?.message) {
    return error.message;
  }

  if (error?.code) {
    return `DCV Error (${error.code}): ${error.message || 'Unknown error'}`;
  }

  return 'An unknown DCV error occurred';
}

/**
 * Check if tool call is a browser_init tool
 */
export function isBrowserInitTool(toolName: string): boolean {
  if (!toolName || typeof toolName !== 'string') {
    return false;
  }
  
  return toolName.toLowerCase() === 'browser_init';
}

/**
 * Extract authentication parameters from presigned URL
 */
export function extractAuthParams(presignedUrl: string): URLSearchParams {
  try {
    const url = new URL(presignedUrl);
    return url.searchParams;
  } catch (error) {
    console.error('Failed to extract auth params:', error);
    return new URLSearchParams();
  }
}