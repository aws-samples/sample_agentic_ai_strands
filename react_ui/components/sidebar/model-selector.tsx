"use client"

import { useState, useEffect } from 'react'
import { useStore } from '@/lib/store'
import { useAuth } from '@/components/providers/AuthProvider'
import * as Select from "@radix-ui/react-select"
import { Check, ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"
import { listModels } from '@/lib/api/chat'

interface ModelData {
  model_name?: string;
  model_id?: string;
  modelName?: string;
  modelId?: string;
  [key: string]: any;
}

export default function ModelSelector() {
  const { user } = useAuth()
  const { models, selectedModel, setModels, setSelectedModel } = useStore()
  const [isLoading, setIsLoading] = useState(true)
  
  // Fetch models when component mounts and user is authenticated
  useEffect(() => {
    if (!user?.userId) {
      setIsLoading(false)
      return
    }

    async function loadModels() {
      if (!user?.userId) return
      
      setIsLoading(true)
      try {
        const modelList = await listModels(user.userId)
        if (modelList && modelList.length > 0) {
          // Convert API response to the format expected by the store
          const mappedModels = modelList.map((model: ModelData) => {
            // Handle both API response formats (snake_case or camelCase)
            return {
              modelName: model.model_name || model.modelName || '',
              modelId: model.model_id || model.modelId || ''
            };
          }).filter((model: any) => model.modelName && model.modelId);
          
          setModels(mappedModels)
          
          // If no model is selected yet, select the first one
          if (!selectedModel && mappedModels.length > 0) {
            setSelectedModel(mappedModels[0].modelId)
          }
        }
      } catch (error) {
        console.error('Failed to load models:', error)
      } finally {
        setIsLoading(false)
      }
    }
    
    loadModels()
  }, [user?.userId, setModels, setSelectedModel, selectedModel])

  // Handle model selection change
  const handleValueChange = (value: string) => {
    setSelectedModel(value)
  }
  
  return (
    <Select.Root
      value={selectedModel}
      onValueChange={handleValueChange}
    >
      <Select.Trigger 
        className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Select.Value placeholder="Select a model">
          {selectedModel && models.find(model => model.modelId === selectedModel)?.modelName}
        </Select.Value>
        <Select.Icon className="ml-2 h-4 w-4 opacity-50">
          <ChevronDown className="h-4 w-4" />
        </Select.Icon>
      </Select.Trigger>
      
      <Select.Portal>
        <Select.Content 
          className="relative z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md animate-in fade-in-80"
          position="popper"
          sideOffset={5}
          align="center"
        >
          <Select.ScrollUpButton className="flex items-center justify-center h-6 bg-popover cursor-default">
            <ChevronDown className="h-4 w-4 rotate-180" />
          </Select.ScrollUpButton>
          
          <Select.Viewport className="p-1">
            {isLoading ? (
              <Select.Item value="loading" className="relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground">
                <Select.ItemText>Loading models...</Select.ItemText>
              </Select.Item>
            ) : models.length === 0 ? (
              <Select.Item value="no-models" className="relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground">
                <Select.ItemText>No models available</Select.ItemText>
              </Select.Item>
            ) : (
              models.map((model) => (
                <Select.Item 
                  key={model.modelId} 
                  value={model.modelId}
                  className="relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
                >
                  <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
                    <Select.ItemIndicator>
                      <Check className="h-4 w-4" />
                    </Select.ItemIndicator>
                  </span>
                  <Select.ItemText>{model.modelName}</Select.ItemText>
                </Select.Item>
              ))
            )}
          </Select.Viewport>
          
          <Select.ScrollDownButton className="flex items-center justify-center h-6 bg-popover cursor-default">
            <ChevronDown className="h-4 w-4" />
          </Select.ScrollDownButton>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  )
}
