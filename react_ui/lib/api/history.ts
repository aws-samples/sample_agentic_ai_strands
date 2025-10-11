import { getBaseUrl } from './chat';
import { getAuthHeaders } from '../auth'



/**
 * Request to remove history from server
 */
export async function removeHistory(userId: string, agentcoreRuntimeArn?: string) {
  const baseUrl = getBaseUrl();
  const url = `${baseUrl.replace(/\/$/, '')}/remove/history`;
  try {
    const headers: Record<string, string> = await getAuthHeaders(userId);

    // Add agentcore runtime ARN header if provided
    if (agentcoreRuntimeArn && agentcoreRuntimeArn.trim() !== '') {
      headers['X-AgentCore-Runtime-ARN'] = agentcoreRuntimeArn;
    }

    const response = await fetch(url, {
      method: 'POST',
      headers
    });
    
    if (!response.ok) {
      throw new Error(`Failed to remove history: ${response.status}`);
    }
    
    const data = await response.json();
    return {
      success: data.errno === 0,
      message: data.msg || 'Successfully cleared conversation history'
    };
  } catch (error) {
    console.error('Error removing history:', error);
    return {
      success: false,
      message: 'Failed to remove history due to network error'
    };
  }
}
