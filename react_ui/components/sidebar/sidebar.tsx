"use client"

import { useState, useEffect } from 'react'
import { useStore } from '@/lib/store'
import { v4 as uuidv4 } from 'uuid'
import ModelSelector from './model-selector'
import ServerList from './server-list'
import AddServerDialog from './add-server-dialog'
import { Switch } from '@/components/ui/switch'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface SidebarProps {
  onClose: () => void
}

export default function Sidebar({ onClose }: SidebarProps) {
  const [activeTab, setActiveTab] = useState<'chat' | 'servers'>('chat')
  const [showAddServer, setShowAddServer] = useState(false)
  const [userIdInput, setUserIdInput] = useState('')
  
  const { 
    systemPrompt, 
    setSystemPrompt, 
    maxTokens, 
    setMaxTokens,
    temperature,
    setTemperature,
    enableThinking,
    setEnableThinking,
    enableStream,
    setEnableStream,
    useMemory,
    setUseMemory,
    useSwarm,
    setUseSwarm,
    clearMessages,
    userId,
    setUserId,
    budgetTokens,
    setBudgetTokens,
    onlyNMostRecentImages,
    setOnlyNMostRecentImages
  } = useStore()
  
  // Initialize user ID input field when component mounts or userId changes
  useEffect(() => {
    if (userId) {
      setUserIdInput(userId)
    }
  }, [userId])
  
  // Function to generate random user ID
  const generateRandomUserId = () => {
    const newId = uuidv4().substring(0, 8)
    setUserId(newId)
    setUserIdInput(newId)
    localStorage.setItem('mcp_chat_user_id', newId)
  }
  
  // Function to save user ID when manually changed
  const saveUserId = () => {
    setUserId(userIdInput)
    localStorage.setItem('mcp_chat_user_id', userIdInput)
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="h-14 border-b border-border flex items-center justify-between px-4">
        <h2 className="font-semibold">Settings</h2>
        <button
          onClick={onClose}
          className="p-2 rounded-md hover:bg-secondary transition-colors"
          aria-label="Collapse sidebar"
          title="Collapse sidebar"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border">
        <button
          className={`flex-1 py-2 text-sm font-medium ${
            activeTab === 'chat' 
              ? 'border-b-2 border-primary text-primary' 
              : 'text-muted-foreground'
          }`}
          onClick={() => setActiveTab('chat')}
        >
          Chat Settings
        </button>
        <button
          className={`flex-1 py-2 text-sm font-medium ${
            activeTab === 'servers' 
              ? 'border-b-2 border-primary text-primary' 
              : 'text-muted-foreground'
          }`}
          onClick={() => setActiveTab('servers')}
        >
          MCP Servers
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'chat' ? (
          <div className="space-y-6">
            {/* User ID */}
            <div className="space-y-2">
              <label htmlFor="user-id" className="text-sm font-medium flex justify-between items-center">
                User ID
                <button
                  onClick={generateRandomUserId}
                  className="text-xs bg-secondary hover:bg-secondary/80 px-2 py-1 rounded-md"
                  title="Generate random user ID"
                >
                  🔄 Randomize
                </button>
              </label>
              <div className="flex gap-2">
                <input
                  id="user-id"
                  type="text"
                  value={userIdInput}
                  onChange={(e) => setUserIdInput(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-md border border-input bg-background"
                  maxLength={32}
                />
                <button
                  onClick={saveUserId}
                  className="px-3 py-1 bg-primary text-primary-foreground rounded-md text-sm"
                >
                  Save
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="model" className="text-sm font-medium">
                Model
              </label>
              <ModelSelector />
            </div>

            <div className="space-y-2">
              <label htmlFor="system-prompt" className="text-sm font-medium">
                System Prompt
              </label>
              <textarea
                id="system-prompt"
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                className="w-full h-36 px-3 py-2 text-sm rounded-md border border-input bg-background"
                placeholder="You are a helpful assistant..."
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="max-tokens" className="text-sm font-medium">
                Max Tokens: {maxTokens}
              </label>
              <input
                id="max-tokens"
                type="range"
                min="100"
                max="64000"
                step="100"
                value={maxTokens}
                onChange={(e) => setMaxTokens(parseInt(e.target.value))}
                className="w-full"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="budget-tokens" className="text-sm font-medium">
                Thinking Token Budget: {budgetTokens}
              </label>
              <input
                id="budget-tokens"
                type="range"
                min="1024"
                max="16384"
                step="1024"
                value={budgetTokens}
                onChange={(e) => setBudgetTokens(parseInt(e.target.value))}
                className="w-full"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="recent-images" className="text-sm font-medium">
                N Most Recent Images: {onlyNMostRecentImages}
              </label>
              <input
                id="recent-images"
                type="range"
                min="0"
                max="5"
                step="1"
                value={onlyNMostRecentImages}
                onChange={(e) => setOnlyNMostRecentImages(parseInt(e.target.value))}
                className="w-full"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="temperature" className="text-sm font-medium">
                Temperature: {temperature.toFixed(1)}
              </label>
              <input
                id="temperature"
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                className="w-full"
              />
            </div>

            <div className="flex items-center justify-between">
              <label htmlFor="enable-thinking" className="text-sm font-medium">
                Enable Thinking
              </label>
              <Switch
                id="enable-thinking"
                checked={enableThinking}
                onCheckedChange={setEnableThinking}
              />
            </div>

            <div className="flex items-center justify-between">
              <label htmlFor="use-swarm" className="text-sm font-medium">
                Use Swarm(Multi Agents)
              </label>
              <Switch
                id="use-swarm"
                checked={useSwarm}
                onCheckedChange={setUseSwarm}
              />
            </div>

            {/* <div className="flex items-center justify-between">
              <label htmlFor="enable-stream" className="text-sm font-medium">
                Stream Response
              </label>
              <Switch
                id="enable-stream"
                checked={enableStream}
                onCheckedChange={setEnableStream}
              />
            </div> */}

            <div className="flex items-center justify-between">
              <label htmlFor="use-memory" className="text-sm font-medium">
                Use Memory
              </label>
              <Switch
                id="use-memory"
                checked={useMemory}
                onCheckedChange={setUseMemory}
              />
            </div>

            <button
              onClick={clearMessages}
              className="w-full py-2 px-4 bg-destructive text-destructive-foreground rounded-md text-sm font-medium hover:bg-destructive/90 transition-colors"
            >
              Clear Conversation
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <ServerList />
            <button
              onClick={() => setShowAddServer(true)}
              className="w-full py-2 px-4 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              Add MCP Server
            </button>
          </div>
        )}
      </div>

      {showAddServer && (
        <AddServerDialog onClose={() => setShowAddServer(false)} />
      )}
    </div>
  )
}
