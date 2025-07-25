"use client"

import { useState, useEffect } from 'react'
import { useStore } from '@/lib/store'
import { useAuth } from '@/components/providers/AuthProvider'
import { listMcpServers, removeMcpServer } from '@/lib/api/chat'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Trash2 } from 'lucide-react'

interface ServerListProps {
  onAddServer?: () => void
}

export default function ServerList({ onAddServer }: ServerListProps) {
  const { user } = useAuth()
  const { mcpServers, setMcpServers, toggleServerEnabled, removeMcpServer: removeServerFromStore } = useStore()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleRemoveServer = async (serverId: string) => {
    if (!user?.userId) return

    if (confirm('Are you sure you want to remove this server?')) {
      setIsLoading(true)
      try {
        const result = await removeMcpServer(user.userId, serverId)
        if (result.success) {
          removeServerFromStore(serverId)
        } else {
          setError(`Failed to remove server: ${result.message}`)
        }
      } catch (err) {
        console.error('Failed to remove MCP server:', err)
        setError('Failed to remove server')
      } finally {
        setIsLoading(false)
      }
    }
  }
  
  // Use a ref to track if we've already loaded servers
  const [initialLoadDone, setInitialLoadDone] = useState(false)

  // Load servers once on mount
  useEffect(() => {
    if (!user?.userId) return

    const loadServers = async () => {
      if (initialLoadDone) return
      
      setIsLoading(true)
      setError(null)
      try {
        // Fetch new server list from API
        const servers = await listMcpServers(user.userId)
        
        // Convert API response to the format expected by the store
        const newServerList = servers.map((server: any) => ({
          serverName: server.server_name,
          serverId: server.server_id,
          enabled: false
        }))
        
        // Merge new servers with existing ones, preserving enabled state
        if (mcpServers.length > 0) {
          const updatedServers = newServerList.map((newServer: any) => {
            // Check if this server already exists in our list
            const existingServer = mcpServers.find(
              existing => existing.serverId === newServer.serverId
            )
            
            // If found, preserve its enabled state
            if (existingServer) {
              return {
                ...newServer,
                enabled: existingServer.enabled
              }
            }
            
            // Otherwise, use the new server as is
            return newServer
          })
          
          setMcpServers(updatedServers)
        } else {
          // No existing servers, just set the new ones
          setMcpServers(newServerList)
        }
        setInitialLoadDone(true)
      } catch (err) {
        console.error('Failed to load MCP servers:', err)
        setError('Failed to load MCP servers')
      } finally {
        setIsLoading(false)
      }
    }

    loadServers()
  }, [user?.userId, setMcpServers, mcpServers.length, initialLoadDone])

  if (isLoading) {
    return <div className="text-sm text-muted-foreground py-2">Loading servers...</div>
  }

  if (error) {
    return <div className="text-sm text-destructive py-2">{error}</div>
  }

  return (
    <div className="space-y-2">
      <h2 className="text-base font-bold">MCP Servers</h2>
      
      {mcpServers.length === 0 ? (
        <div className="text-sm text-muted-foreground">
          No MCP servers available
        </div>
      ) : (
        <div className="space-y-2">
          {mcpServers.map((server) => (
            <div 
              key={server.serverId}
              className="flex flex-row items-center gap-2 py-1"
            >
              <Switch
                checked={server.enabled}
                onCheckedChange={() => toggleServerEnabled(server.serverId)}
                aria-label={`Toggle ${server.serverName}`}
                className="data-[state=checked]:bg-blue-500"
              />
              
              <span className="text-sm flex-grow" title={server.serverName}>
                {server.serverName}
              </span>
              
              <Button
                variant="outline"
                size="sm"
                className="ml-2 bg-red-500 hover:bg-red-600 text-white border-0 px-2 py-0 h-6 text-xs"
                onClick={() => handleRemoveServer(server.serverId)}
              >
                <Trash2 className="h-3 w-3 mr-1" />
                Delete
              </Button>
            </div>
          ))}
        </div>
      )}
      
      {onAddServer && (
        <Button 
          className="w-full mt-4 bg-gray-100 hover:bg-gray-200 text-black border border-gray-300 py-2" 
          onClick={onAddServer}
        >
          Add MCP Server
        </Button>
      )}
    </div>
  )
}
