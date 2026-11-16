'use client';

import { useEffect } from 'react';
import { useStore } from '@/lib/store';
import { fetchModels, fetchMcpServers } from '@/lib/api/chat';

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const { 
    userId, 
    setModels, 
    setSelectedModel, 
    setMcpServers 
  } = useStore();

  // Initialize app - load models and servers for the signed-in user
  useEffect(() => {
    async function initialize() {
      // The user ID is set by AuthGate from the signed-in Cognito user.
      if (!userId) return;

      // Load models
      try {
        const modelList = await fetchModels();
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
        const servers = await fetchMcpServers();
        if (servers && servers.length > 0) {
          setMcpServers(servers);
        }
      } catch (error) {
        console.error('Failed to load MCP servers:', error);
      }
    }
    
    initialize();
  }, [userId, setModels, setSelectedModel, setMcpServers]);

  return <>{children}</>;
}
