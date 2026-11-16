'use client';

import { useState, useEffect, useRef } from 'react';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { useStore } from '@/lib/store';
import { fetchMcpServers } from '@/lib/api/chat';

export default function ChatInterface() {
  const [isLoadingMcpServers, setIsLoadingMcpServers] = useState(true);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const loadedRef = useRef<boolean>(false);
  
  const { mcpServers, setMcpServers } = useStore();
  
  // The user ID is set by AuthGate from the signed-in Cognito user.
  
  // Fetch MCP servers when component mounts - only run once
  useEffect(() => {
    // Only load servers once
    if (loadedRef.current) return;
    
    const loadMcpServers = async () => {
      setIsLoadingMcpServers(true);
      try {
        const servers = await fetchMcpServers();
        
        // Process servers
        let updatedServers;
        if (mcpServers.length > 0) {
          // Preserve enabled state from existing servers
          updatedServers = servers.map(newServer => {
            const existingServer = mcpServers.find(
              existing => existing.serverId === newServer.serverId
            );
            
            if (existingServer) {
              return {
                ...newServer,
                enabled: existingServer.enabled
              };
            }
            
            return newServer;
          });
        } else {
          updatedServers = servers;
        }
        
        // Update the store
        setMcpServers(updatedServers);
        
        // Mark as loaded
        loadedRef.current = true;
      } catch (error) {
        console.error('Failed to load MCP servers:', error);
      } finally {
        setIsLoadingMcpServers(false);
      }
    };
    
    loadMcpServers();
  }, []); // Empty dependency array to run only once
  
  return (
    <div className="flex flex-col h-full">
      {/* Main chat area - centered with max width */}
      <div className="flex flex-1 overflow-hidden justify-center">
        <div className="flex flex-col w-full max-w-4xl min-w-0 bg-gray-50/80 dark:bg-gray-800/80 shadow-md">
          {/* Message list */}
          <MessageList isLoading={isLoadingMcpServers} isRunning={isChatLoading}/>
        </div>
      </div>
      
      {/* Full width separator line */}
      <div className="border-t border-border"></div>
      
      {/* Chat input - centered with same max width */}
      <div className="flex justify-center">
        <div className="w-full max-w-4xl">
          <ChatInput
            disabled={isLoadingMcpServers}
            onLoadingChange={setIsChatLoading}
          />
        </div>
      </div>
    </div>
  );
}
