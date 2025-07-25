'use client';

import { useEffect } from 'react';
import { useStore } from '@/lib/store';
import { listModels, listMcpServers } from '@/lib/api/chat';
import { useAuth } from '@/components/providers/AuthProvider';

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const {
    setUserId,
    setModels,
    setSelectedModel,
    setMcpServers
  } = useStore();

  // Initialize app - load models, servers, and set userId from auth
  useEffect(() => {
    if (!user?.userId) {
      // Don't initialize if user is not authenticated
      return;
    }

    async function initialize() {
      // Set user ID from authenticated user
      if (user?.userId) {
        setUserId(user.userId);
        
        // Load models
        try {
          const modelList = await listModels(user.userId);
          if (modelList && modelList.length > 0) {
            // Convert API response to the format expected by the store
            const mappedModels = modelList.map((model: any) => ({
              modelName: model.model_name || '',
              modelId: model.model_id || ''
            })).filter((model: any) => model.modelName && model.modelId);
            
            setModels(mappedModels);
            
            // If no model is selected yet, select the first one
            if (mappedModels.length > 0) {
              setSelectedModel(mappedModels[0].modelId);
            }
          }
        } catch (error) {
          console.error('Failed to load models:', error);
        }
        
        // Load MCP servers
        try {
          const servers = await listMcpServers(user.userId);
          if (servers && servers.length > 0) {
            // Convert API response to the format expected by the store
            const mappedServers = servers.map((server: any) => ({
              serverName: server.server_name,
              serverId: server.server_id,
              enabled: false
            }));
            setMcpServers(mappedServers);
          }
        } catch (error) {
          console.error('Failed to load MCP servers:', error);
        }
      }
    }
    
    initialize();
  }, [user?.userId, setUserId, setModels, setSelectedModel, setMcpServers]);

  return <>{children}</>;
}
