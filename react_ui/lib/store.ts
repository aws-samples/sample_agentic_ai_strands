import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ContentItem = {
  type: string;
  text?: string;
  image_url?: {
    url: string;
    detail?: string;
  };
  file?: {
    file_id?: string;
    file_data?: string;
    filename?: string;
  };
}

export type ToolCall = {
  id: string;
  name: string;
  arguments: any;
  result?: any;
  status: 'pending' | 'running' | 'completed' | 'error';
  startTime?: number;
  endTime?: number;
}

export type Message = {
  role: 'system' | 'user' | 'assistant'
  content: string | ContentItem[]
  thinking?: string
  isThinking?: boolean
  toolUse?: any[]
  toolName?: any[]
  toolInput?: any[]
  toolCalls?: ToolCall[]
}

export type Model = {
  modelName: string
  modelId: string
}

export type McpServer = {
  serverName: string
  serverId: string
  enabled: boolean
}

interface ChatStore {
  // Messages
  messages: Message[]
  addMessage: (message: Message) => void
  updateLastMessage: (content: string | ContentItem[], thinking?: string, toolUse?: any[],toolName?:any[], toolInput?: any[], toolCalls?: ToolCall[], isThinking?: boolean) => void
  clearMessages: () => void
  
  // Settings
  systemPrompt: string
  setSystemPrompt: (prompt: string) => void
  maxTokens: number
  setMaxTokens: (tokens: number) => void
  temperature: number
  setTemperature: (temp: number) => void
  enableThinking: boolean
  setEnableThinking: (enabled: boolean) => void
  enableStream: boolean
  setEnableStream: (enabled: boolean) => void
  budgetTokens: number
  setBudgetTokens: (tokens: number) => void
  onlyNMostRecentImages: number
  setOnlyNMostRecentImages: (count: number) => void
  useMemory: boolean
  setUseMemory: (enabled: boolean) => void
  useSwarm: boolean
  setUseSwarm: (enabled: boolean) => void
  
  // Models
  models: Model[]
  setModels: (models: Model[]) => void
  selectedModel: string
  setSelectedModel: (modelId: string) => void
  
  // MCP Servers
  mcpServers: McpServer[]
  setMcpServers: (servers: McpServer[]) => void
  toggleServerEnabled: (serverId: string) => void
  addMcpServer: (server: McpServer) => void
  removeMcpServer: (serverId: string) => void
  
  // User
  userId: string
  setUserId: (id: string) => void
}

export const useStore = create<ChatStore>()(
  persist(
    (set) => ({
      // Messages
      messages: [{ role: 'system', 
        content: `You are a deep researcher
Please use the maximum computational power and token limit available in a single response. Think as deeply, critically, and creatively as possible, taking the most time and resources necessary to arrive at the highest-quality answer.` }],
      addMessage: (message) => set((state) => ({ 
        messages: [...state.messages, message] 
      })),
      updateLastMessage: (content, thinking, toolUse,toolName, toolInput, toolCalls, isThinking) => set((state) => {
        const messages = [...state.messages]
        const lastMessage = messages[messages.length - 1]
        if (lastMessage && lastMessage.role === 'assistant') {
          messages[messages.length - 1] = {
            ...lastMessage,
            content,
            ...(thinking !== undefined && { thinking }),
            ...(toolUse !== undefined && { toolUse }),
            ...(toolName !== undefined && { toolName }),
            ...(toolInput !== undefined && { toolInput }),
            ...(toolCalls !== undefined && { toolCalls }),
            ...(isThinking !== undefined && { isThinking })
          }
        }
        return { messages }
      }),
      clearMessages: () => {
        const state = useStore.getState();
        
        // Call the API to remove server-side history
        if (state.userId) {
          import('./api/history').then(({ removeHistory }) => {
            removeHistory(state.userId).then((result) => {
              if (!result.success) {
                console.error('Failed to remove history on server:', result.message);
              }
            }).catch((error) => {
              console.error('Error removing history:', error);
            });
          });
        }
        
        // Reset local messages in any case
        set((state) => ({ 
          messages: [{ role: 'system', content: state.systemPrompt }] 
        }));
      },
      
      // Settings
      systemPrompt: 'You are a helpful assistant.',
      setSystemPrompt: (prompt) => set({ systemPrompt: prompt }),
      maxTokens: 8192,
      setMaxTokens: (tokens) => set({ maxTokens: tokens }),
      temperature: 0.7,
      setTemperature: (temp) => set({ temperature: temp }),
      enableThinking: true,
      setEnableThinking: (enabled) => set({ enableThinking: enabled }),
      enableStream: true,
      setEnableStream: (enabled) => set({ enableStream: enabled }),
      budgetTokens: 8192,
      setBudgetTokens: (tokens) => set({ budgetTokens: tokens }),
      onlyNMostRecentImages: 1,
      setOnlyNMostRecentImages: (count) => set({ onlyNMostRecentImages: count }),
      useMemory: true,
      setUseMemory: (enabled) => set({ useMemory: enabled }),
      useSwarm: false,
      setUseSwarm: (enabled) => set({ useSwarm: enabled }),
      
      // Models
      models: [],
      setModels: (models) => set({ models }),
      selectedModel: '',
      setSelectedModel: (modelId) => set({ selectedModel: modelId }),
      
      // MCP Servers
      mcpServers: [],
      setMcpServers: (servers) => set({ mcpServers: servers }),
      toggleServerEnabled: (serverId) => set((state) => ({
        mcpServers: state.mcpServers.map(server => 
          server.serverId === serverId 
            ? { ...server, enabled: !server.enabled } 
            : server
        )
      })),
      addMcpServer: (server) => set((state) => ({
        mcpServers: [...state.mcpServers, server]
      })),
      removeMcpServer: (serverId) => set((state) => ({
        mcpServers: state.mcpServers.filter(server => server.serverId !== serverId)
      })),
      
      // User
      userId: '',
      setUserId: (id) => set({ userId: id })
    }),
    {
      name: 'mcp-chat-store',
      partialize: (state) => {
        // Create a copy of messages without base64 images to stay under localStorage quota
        const messagesForStorage = state.messages.map(message => {
          // Clean up message content for image data
          let cleanContent = message.content;
          
          // If content is an array (likely contains images), clean up large base64 data
          if (Array.isArray(message.content)) {
            cleanContent = message.content.map((item: ContentItem) => {
              // If it's an image_url item with base64 data, replace the data
              if (item.type === 'image_url' && 
                  item.image_url?.url && 
                  item.image_url.url.startsWith('data:')) {
                return {
                  ...item,
                  image_url: {
                    ...item.image_url,
                    url: '[BASE64_IMAGE_DATA_REMOVED]'
                  }
                };
              }
              
              // If it's a file item with base64 data, replace the data
              if (item.type === 'file' && item.file?.file_data) {
                return {
                  ...item,
                  file: {
                    ...item.file,
                    file_data: '[BASE64_FILE_DATA_REMOVED]'
                  }
                };
              }
              
              return item;
            });
          }
          
          // Clean up tool use data
          const { toolUse, ...rest } = message;
          
          // If there's no tool use data, return the message with clean content
          if (!toolUse) return { ...rest, content: cleanContent };
          
          // Otherwise clean up the tool use data to remove any large base64 images
          const cleanToolUse = toolUse.map(tool => {
            // Clone the tool to avoid modifying the original
            const cleanTool = { ...tool };
            
            // Handle tool results with content array
            if (cleanTool.content) {
              cleanTool.content = cleanTool.content.map((block: any) => {
                // Remove base64 image data but keep reference that image existed
                if (block.image?.source?.base64) {
                  return {
                    ...block,
                    image: {
                      ...block.image,
                      source: { base64: "[BASE64_IMAGE_DATA_REMOVED]" }
                    }
                  };
                }
                return block;
              });
            }
            
            return cleanTool;
          });
          
          return { ...rest, content: cleanContent, toolUse: cleanToolUse };
        });
        
        // Return a filtered state object for localStorage
        return {
          ...state,
          // Only store the latest 20 messages to prevent quota issues
          messages: messagesForStorage.slice(-20)
        };
      }
    }
  )
)
