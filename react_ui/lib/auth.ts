import { fetchAuthSession } from 'aws-amplify/auth';

// Cache for API key to avoid repeated requests
let cachedApiKey: string | null = null;
let apiKeyPromise: Promise<string> | null = null;

/**
 * Get the API key, either from cache, environment, or server endpoint
 */
export async function getApiKey(): Promise<string> {
  // If we have a cached key, return it
  if (cachedApiKey) {
    return cachedApiKey;
  }

  // If there's already a request in flight, wait for it
  if (apiKeyPromise) {
    return apiKeyPromise;
  }

  // Check if API key is available in environment (client-side)
  const envApiKey = process.env.NEXT_PUBLIC_API_KEY;
  if (envApiKey && !envApiKey.startsWith('arn:aws')) {
    // It's a direct API key, not an ARN
    cachedApiKey = envApiKey;
    return envApiKey;
  }

  // If it's an ARN or not available, fetch from server
  apiKeyPromise = fetchApiKeyFromServer();
  
  try {
    const apiKey = await apiKeyPromise;
    cachedApiKey = apiKey;
    return apiKey;
  } finally {
    apiKeyPromise = null;
  }
}

/**
 * Get authentication headers with Cognito JWT token
 */
export const getAuthHeaders = async (userId?: string) => {
  try {
    // Try to get JWT token from Cognito first
    const session = await fetchAuthSession();
    const jwtToken = session.tokens?.accessToken?.toString();
    
    if (jwtToken) {
      return {
        'Authorization': `Bearer ${jwtToken}`,
        'X-User-ID': userId || 'cognito-user',
        'Content-Type': 'application/json'
      };
    }
  } catch (error) {
    console.log('No Cognito session found, falling back to API key');
  }
  
  // Fallback to API key if no JWT token
  const apiKey = await getApiKey();
  return {
    'Authorization': `Bearer ${apiKey}`,
    'X-User-ID': userId || 'api-user',
    'Content-Type': 'application/json'
  };
}

/**
 * Get authentication headers with fallback support
 */
export const getAuthHeadersWithFallback = async (userId?: string) => {
  try {
    return await getAuthHeaders(userId);
  } catch (error) {
    console.error('Error getting auth headers:', error);
    // Return basic headers as last resort
    return {
      'Authorization': `Bearer ${process.env.NEXT_PUBLIC_API_KEY || '123456'}`,
      'X-User-ID': userId || 'fallback-user',
      'Content-Type': 'application/json'
    };
  }
}

/**
 * Fetch API key from server endpoint
 */
async function fetchApiKeyFromServer(): Promise<string> {
  try {
    const response = await fetch('/api/v1/auth/api-key');
    
    if (!response.ok) {
      throw new Error(`Failed to fetch API key: ${response.status}`);
    }
    
    const data = await response.json();
    
    if (!data.api_key) {
      throw new Error('No API key returned from server');
    }
    
    // Ensure the API key is a string, not an object
    let apiKey = data.api_key;
    
    // If the API key is an object (e.g., from nested JSON), extract the actual key
    if (typeof apiKey === 'object' && apiKey !== null) {
      if (apiKey.api_key) {
        apiKey = apiKey.api_key;
      } else {
        // If it's an object but doesn't have api_key field, stringify it for debugging
        console.error('API key is an object:', apiKey);
        throw new Error('API key returned as object instead of string');
      }
    }
    
    // Final check to ensure it's a string
    if (typeof apiKey !== 'string') {
      console.error('API key is not a string:', typeof apiKey, apiKey);
      throw new Error('API key must be a string');
    }
    
    return apiKey;
  } catch (error) {
    console.error('Error fetching API key from server:', error);
    throw new Error('Failed to obtain API key');
  }
}

/**
 * Clear the cached API key (useful for testing or when key rotation occurs)
 */
export function clearApiKeyCache(): void {
  cachedApiKey = null;
  apiKeyPromise = null;
}

/**
 * Check if the API key looks like an AWS ARN
 */
export function isAwsArn(value: string): boolean {
  return value.startsWith('arn:aws:');
}
