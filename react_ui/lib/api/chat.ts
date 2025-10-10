import { Message } from '../store';
import { getAuthHeaders } from '../auth'


// Get environment variables with server/client detection
export const getBaseUrl = () => {
  // Check if we're running on the server or client
  if (typeof window === 'undefined') {
    // Server-side: use internal URL with the protocol specified in SERVER_MCP_BASE_URL
    const baseUrl = process.env.SERVER_MCP_BASE_URL || 'http://localhost:7002';
    return baseUrl;
  } else {
    // Client-side: use public URL with environment-aware path
    const publicUrl = process.env.NEXT_PUBLIC_MCP_BASE_URL || '/api';
    // In production, requests go directly to backend via ALB, so use /v1 directly
    if (process.env.NODE_ENV === 'production') {
      return '/v1';
    }
    // In development, use /api/v1 for Next.js API routes
    return `${publicUrl}/v1`;
  }
};

// Configure fetch to ignore SSL errors for self-signed certificates
// This is safe because we're making the request from the server side
if (typeof window === 'undefined') {
  process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
}

const API_KEY = process.env.NEXT_PUBLIC_API_KEY || '';

// Note: getUserId function removed - user ID should be passed from authentication context

/**
 * Get authentication headers with user ID
 */
// const getAuthHeaders = async (userId: string) => {
//   return {
//     'Authorization': `Bearer ${apiKey}`,
//     'X-User-ID': userId,
//     'Content-Type': 'application/json'
//   }
// }

/**
 * Request list of available models
 */
export async function listModels(userId: string) {
  const baseUrl = getBaseUrl();
  const url = `${baseUrl.replace(/\/$/, '')}/list/models`;
  try {
    const response = await fetch(url, {
      headers: await getAuthHeaders(userId)
    });
    
    if (!response.ok) {
      throw new Error(`Failed to fetch models: ${response.status}`);
    }
    
    const data = await response.json();
    return data.models || [];
  } catch (error) {
    console.error('Error listing models:', error);
    return [];
  }
}

/**
 * Request list of MCP servers
 */
export async function listMcpServers(userId: string) {
  const baseUrl = getBaseUrl();
  const url = `${baseUrl.replace(/\/$/, '')}/list/mcp_server`;
  try {
    const response = await fetch(url, {
      headers: await getAuthHeaders(userId)
    });
    
    if (!response.ok) {
      throw new Error(`Failed to fetch MCP servers: ${response.status}`);
    }
    
    const data = await response.json();
    return data.servers || [];
  } catch (error) {
    console.error('Error listing MCP servers:', error);
    return [];
  }
}

/**
 * Remove an MCP server
 */
export async function removeMcpServer(userId: string, serverId: string): Promise<{ success: boolean; message: string }> {
  try {
    const baseUrl = getBaseUrl();
    const headers = await getAuthHeaders(userId);
    const response = await fetch(`${baseUrl}/remove/mcp_server/${serverId}`, {
      method: 'DELETE',
      headers
    });
    
    const data = await response.json();
    return {
      success: data.errno === 0,
      message: data.msg || 'Unknown error'
    };
  } catch (error) {
    console.error('Error removing MCP server:', error);
    return {
      success: false,
      message: error instanceof Error ? error.message : 'Unknown error'
    };
  }
}

/**
 * Add a new MCP server
 */
export async function addMcpServer(
  userId: string,
  serverId: string,
  serverName: string,
  command: string,
  args: string[] = [],
  env: Record<string, string> | null = null,
  configJson: Record<string, any> = {}
) {
  const baseUrl = getBaseUrl();
  const url = `${baseUrl.replace(/\/$/, '')}/add/mcp_server`;
  
  try {
    const payload: any = {
      server_id: serverId,
      server_desc: serverName,
      command: command,
      args: args,
      config_json: configJson
    };
    
    if (env) {
      payload.env = env;
    }
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        ...await getAuthHeaders(userId),
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    
    const data = await response.json();
    return {
      success: data.errno === 0,
      message: data.msg || 'Unknown error'
    };
  } catch (error) {
    console.error('Error adding MCP server:', error);
    return {
      success: false,
      message: 'Failed to add MCP server due to network error'
    };
  }
}

/**
 * Process streaming response from chat API
 */
export function processStreamResponse(
  response: Response,
  onContent: (content: string) => void,
  onToolUse: (toolUse: string) => void,
  onThinking: (thinking: string) => void,
  onError: (error: string) => void,
  onDone?: () => void,
  onToolInput?: (toolInput: string) => void,
  onToolName?:(toolName: string) => void
) {
  const reader = response.body?.getReader();
  const decoder = new TextDecoder();
  let aborted = false;
  
  // Buffer for accumulating partial lines
  let lineBuffer = '';
  
  // Buffer for accumulating complete but unparseable events
  // This handles cases where JSON is split across multiple SSE events
  let dataBuffer: {[key: string]: string} = {};
  let currentDataId = '';
  
  if (!reader) {
    onError('Response body is null');
    return { abort: () => {} };
  }
  
  // Create an abort function
  const abort = () => {
    aborted = true;
    // We need to actively cancel the reader to ensure stream processing stops
    reader.cancel().catch(err => console.error('Error canceling reader:', err));
  };
  
  // Process a single data line that may contain JSON
  const processData = (data: string) => {
    if (data === '[DONE]') {
      // Stream is complete from server side
      aborted = true;
      if (onDone) {
        onDone();
      }
      return;
    }
    
    try {
      // Try parsing the JSON
      const jsonData = JSON.parse(data);
      // Skip connection establishment events (added by proxy for dev mode)
      if (jsonData.type === 'connection' && jsonData.status === 'established') {
        return;
      }
      
      // Extract the message ID if available, to help with buffering
      const messageId = jsonData.id || '';
      
      if (messageId && messageId !== currentDataId) {
        // We have a new message ID, reset buffers for a new message
        currentDataId = messageId;
        dataBuffer[currentDataId] = data;
      }
      
      // Process the data normally
      const delta = jsonData.choices?.[0]?.delta || {};
      
      if ('content' in delta) {
        onContent(delta.content);
      }

      if ('reasoning_content' in delta){
        onThinking(delta.reasoning_content);
      }

      if ('toolinput_content' in delta && onToolInput){
        onToolInput(delta.toolinput_content);
      }
      
      const messageExtras = jsonData.choices?.[0]?.message_extras || {};
      if ('tool_use' in messageExtras) {
        onToolUse(JSON.stringify(messageExtras.tool_use));
      }

      if ('tool_name' in messageExtras && onToolName) {
        onToolName(messageExtras.tool_name);
      }
      
      // Extract thinking content if present
      // const content = delta.content || '';
      // const thinkingMatch = content.match(/<thinking>(.*?)<\/thinking>/s);
      // if (thinkingMatch) {
      //   onThinking(thinkingMatch[1]);
      // }
      
      // Extract tool_input content if present
      // const toolInputMatch = content.match(/<tool_input>(.*?)<\/tool_input>/s);
      // if (toolInputMatch && onToolInput) {
      //   onToolInput(toolInputMatch[1]);
      // }
      
      // Check if message_extras contains thinking
      // if (messageExtras && messageExtras.thinking) {
      //   onThinking(messageExtras.thinking);
      // }
      
      // Check if message_extras contains tool_input
      // if (messageExtras && messageExtras.tool_input && onToolInput) {
      //   onToolInput(messageExtras.tool_input);
      // }
      
    } catch (e) {
      // JSON parsing failed
      
      // Check if we have a partial JSON that might be continued in next chunks
      if (data.includes('"choices"') && !data.endsWith('}}')) {
        // This looks like a partial JSON message
        // Store in buffer using a generic ID if we don't have one yet
        const bufferId = currentDataId || '_partial';
        dataBuffer[bufferId] = data;
        console.warn('Buffering partial JSON for later processing');
      } else if (currentDataId && dataBuffer[currentDataId]) {
        // Try to append this data to our existing buffer for this message
        dataBuffer[currentDataId] += data;
        
        // Try parsing the combined buffer
        try {
          const combinedData = JSON.parse(dataBuffer[currentDataId]);
          
          // If we get here, parsing succeeded, so process the combined data
          const delta = combinedData.choices?.[0]?.delta || {};
          
          if ('content' in delta) {
            onContent(delta.content);
          }
          
          const messageExtras = combinedData.choices?.[0]?.message_extras || {};
          if ('tool_use' in messageExtras) {
            onToolUse(JSON.stringify(messageExtras.tool_use));
          }
          
          // Clear the buffer now that we've successfully processed it
          delete dataBuffer[currentDataId];
        } catch (e2) {
          // Still can't parse, just log and wait for more data
          console.warn('Failed to parse combined JSON buffer:', e2);
        }
      } else {
        // This doesn't look like a partial JSON or we can't combine it
        console.error('Failed to parse JSON:', e);
        // Don't report the error to the user for every chunk - it makes the UI noisy
        // Only report critical errors that stop the stream
      }
    }
  };
  
  const processChunk = async () => {
    if (aborted) {
      if (onDone) onDone();
      return;
    }
    
    try {
      // If already aborted before trying to read, exit immediately
      if (aborted) {
        if (onDone) onDone();
        return;
      }
      
      const { done, value } = await reader.read();
      
      // Check abort status again after read completes
      if (done || aborted) {
        if (onDone) onDone();
        return;
      }
      
      // Decode the chunk and add to our line buffer
      const chunk = decoder.decode(value, { stream: true });
      lineBuffer += chunk;
      
      // Process complete lines
      let newlineIndex;
      
      // Continue extracting lines until no more newlines are found
      while ((newlineIndex = lineBuffer.indexOf('\n')) !== -1) {
        // Extract the complete line
        const line = lineBuffer.substring(0, newlineIndex);
        // Remove the processed line from the buffer
        lineBuffer = lineBuffer.substring(newlineIndex + 1);
        
        // Process data lines
        if (line.startsWith('data: ')) {
          const data = line.substring(6); // Remove 'data: ' prefix
          processData(data);
        }
      }
      
      // Continue reading if not aborted
      if (!aborted) {
        processChunk();
      } else if (onDone) {
        onDone();
      }
    } catch (error) {
      if (!aborted) {
        console.error('Stream processing error:', error);
        onError(`Error processing stream: ${error}`);
      }
      if (onDone) onDone();
    }
  };
  
  processChunk();
  
  // Return abort function to allow stopping the stream
  return { abort };
}

/**
 * Stop an active streaming response
 */
export async function stopStream(userId: string, streamId: string, agentcoreRuntimeArn?: string) {
  // Don't attempt to stop if stream ID is empty
  if (!streamId) {
    console.warn('No stream ID provided to stop');
    return {
      success: false,
      message: 'No stream ID provided'
    };
  }

  const baseUrl = getBaseUrl();
  const url = `${baseUrl.replace(/\/$/, '')}/stop/stream/${streamId}`;

  try {
    const controller = new AbortController();
    // Set a timeout to prevent the stop request from hanging
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    const headers: Record<string, string> = await getAuthHeaders(userId);

    // Add agentcore runtime ARN header if provided
    if (agentcoreRuntimeArn && agentcoreRuntimeArn.trim() !== '') {
      headers['X-AgentCore-Runtime-ARN'] = agentcoreRuntimeArn;
    }

    const response = await fetch(url, {
      method: 'POST',
      headers,
      signal: controller.signal
    });
    
    clearTimeout(timeoutId);
    
    if (!response.ok) {
      console.warn(`Stream stop response not OK: ${response.status}`);
      // Still consider it a "success" for UI purposes, as we want to reset UI state
      return {
        success: true,
        message: 'Stream may have already completed'
      };
    }
    
    const data = await response.json();
    return {
      success: data.errno === 0 || data.msg === 'Stream may have already completed',
      message: data.msg || 'Unknown error'
    };
  } catch (error) {
    console.error('Error stopping stream:', error);
    // If there's a timeout or network error, still consider it a "success" for UI state
    return {
      success: true,
      message: 'Could not confirm stream stop, but UI has been reset'
    };
  }
}

// Deprecated wrapper functions - these should not be used anymore
// Use listModels(userId) and listMcpServers(userId) directly instead

/**
 * Send chat request to API
 */
export async function sendChatRequest({
  messages,
  modelId,
  mcpServerIds,
  userId,
  stream = true,
  maxTokens = 1024,
  temperature = 0.6,
  useMemory = false,
  useSwarm = false,
  useCodeInterpreter = false,
  useBrowser = false,
  extraParams = {},
  agentcoreRuntimeArn
}: {
  messages: Message[];
  modelId: string;
  mcpServerIds: string[];
  userId: string;
  stream?: boolean;
  maxTokens?: number;
  temperature?: number;
  useMemory?: boolean;
  useSwarm?: boolean;
  useCodeInterpreter?: boolean;
  useBrowser?: boolean;
  extraParams?: Record<string, any>;
  agentcoreRuntimeArn?: string;
}) {
  const baseUrl = getBaseUrl();

  const payload: any = {
    messages,
    model: modelId,
    mcp_server_ids: mcpServerIds,
    extra_params: {
      ...extraParams,
      use_mem: useMemory,
      use_swarm: useSwarm,
      use_code_interpreter: useCodeInterpreter,
      use_browser: useBrowser
    },
    stream,
    temperature,
    max_tokens: maxTokens
  };

  // Add agentcore_runtime_arn if provided
  if (agentcoreRuntimeArn && agentcoreRuntimeArn.trim() !== '') {
    payload.agentcore_runtime_arn = agentcoreRuntimeArn;
  }
  
  try {
      if (stream) {
        // For streaming responses, use the same endpoint as non-streaming
        const streamUrl = `${baseUrl.replace(/\/$/, '')}/chat/completions`;
        
        const headers = {
          ...await getAuthHeaders(userId),
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream'
        };
        
        const response = await fetch(streamUrl, {
          method: 'POST',
          headers,
          body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
          throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        // Get the stream ID from the response headers (provided by backend)
        // Fall back to a generated ID if the header isn't present
        let streamId = response.headers.get('X-Stream-ID');
        if (!streamId) {
          console.warn('X-Stream-ID header not found in response, generating local ID');
          streamId = `stream_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
        } else {
          console.log('Using server-provided stream ID:', streamId);
        }
        
        return { response, messageExtras: {}, streamId };
    } else {
      // For non-streaming responses, use the same endpoint
      const url = `${baseUrl.replace(/\/$/, '')}/chat/completions`;
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          ...await getAuthHeaders(userId),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      
      const data = await response.json();
      const message = data.choices[0].message.content;
      const messageExtras = data.choices[0].message_extras || {};
      
      return { message, messageExtras };
    }
  } catch (error) {
    console.error('Error sending chat request:', error);
    return {
      message: 'An error occurred when calling the Converse operation: The system encountered an unexpected error during processing. Try your request again.',
      messageExtras: {}
    };
  }
}
