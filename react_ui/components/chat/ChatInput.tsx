'use client';

import { useState, FormEvent, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { useStore, Message, ToolCall } from '@/lib/store';
import { v4 as uuidv4 } from 'uuid';
import { sendChatRequest, processStreamResponse, stopStream } from '@/lib/api/chat';
import { extractThinking, extractToolUse, extractToolInput} from '@/lib/utils';
import { FileUpload, FileItem } from './FileUpload';
import { Paperclip, Mic, MicOff } from 'lucide-react';
import AudioRecorder from './AudioRecorder';

interface ChatInputProps {
  disabled?: boolean;
  onLoadingChange?: (isLoading: boolean) => void;
}

export function ChatInput({ disabled = false, onLoadingChange }: ChatInputProps) {
  const [prompt, setPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStreamId, setCurrentStreamId] = useState<string | null>(null);
  const [files, setFiles] = useState<FileItem[]>([]);
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [isVoiceMode, setIsVoiceMode] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const abortControllerRef = useRef<{ abort: () => void } | null>(null);
  
  const {
    messages,
    addMessage,
    updateLastMessage,
    userId,
    selectedModel,
    models,
    mcpServers,
    enableStream,
    enableThinking,
    maxTokens,
    temperature,
    budgetTokens,
    onlyNMostRecentImages,
    useMemory,
    useSwarm,
    useCodeInterpreter,
    useBrowser
  } = useStore();
  
  // Get selected server IDs from mcpServers
  const selectedServers = mcpServers
    .filter(server => server.enabled)
    .map(server => server.serverId);
    
  // Get model ID from selected model name
  const modelId = selectedModel;
  
  // Clean up when component unmounts
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const handleStopGeneration = async () => {
    // First try local abort to stop the stream processing
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    
    // Then call server-side stop to terminate the stream
    if (!currentStreamId || !userId) {
      // Even if we don't have streamId/userId, make sure UI is reset
      setIsStreaming(false);
      setCurrentStreamId(null);
      return;
    }
    
    try {
      const result = await stopStream(userId, currentStreamId);
      if (result.success) {
        console.log('Stream stopped successfully');
      } else {
        console.error('Failed to stop stream:', result.message);
      }
    } catch (error) {
      console.error('Error stopping stream:', error);
    } finally {
      setIsStreaming(false);
      setCurrentStreamId(null);
      onLoadingChange?.(false);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    
    if ((!prompt.trim() && files.length === 0) || isLoading || !selectedModel) return;
    
    // Prepare user message content
    let userMessage: Message;
    
    if (files.length > 0) {
      // Create structured message with files
      const messageContent = [];
      
      // Add text content if present
      if (prompt.trim()) {
        messageContent.push({
          type: 'text',
          text: prompt
        });
      }
      
      // Add file content
      files.forEach(file => {
        if (file.type.startsWith('image/')) {
          // For images, use image_url type
          messageContent.push({
            type: 'image_url',
            image_url: {
              url: `data:${file.type};base64,${file.data}`,
              detail: 'auto'
            }
          });
        } else {
          // For other files, use file type
          messageContent.push({
            type: 'file',
            file: {
              file_data: file.data,
              filename: file.name
            }
          });
        }
      });
      
      userMessage = { 
        role: 'user', 
        content: messageContent
      };
    } else {
      // Simple text-only message
      userMessage = { role: 'user', content: prompt };
    }
    
    // Add message with storage optimization for multiple images
    try {
      addMessage(userMessage);
    } catch (error) {
      console.error('Error adding message:', error);
      // If localStorage quota exceeded, clear old messages first
      if (error instanceof DOMException && error.name === 'QuotaExceededError') {
        // Clear all messages except system message and try again
        const systemMessage = messages.find(msg => msg.role === 'system');
        useStore.setState({ 
          messages: systemMessage ? [systemMessage] : [] 
        });
        
        // Now add the user message again
        addMessage(userMessage);
      }
    }
    
    // Clear input and files
    setPrompt('');
    setFiles([]);
    setShowFileUpload(false);
    setIsLoading(true);
    onLoadingChange?.(true);
    
    try {
      // We already have the modelId from our store
      
      // Prepare messages for API
      let apiMessages;
      
      if (useMemory) {
        // When useMemory is enabled, only send the system message and current user message
        const systemMessage = messages.find(msg => msg.role === 'system');
        apiMessages = systemMessage 
          ? [systemMessage, userMessage] 
          : [userMessage];
      } else {
        // When useMemory is disabled, send all messages
        apiMessages = [...messages, userMessage];
      }
      
      // Extra parameters
      const extraParams = {
        only_n_most_recent_images: onlyNMostRecentImages,
        budget_tokens: budgetTokens,
        enable_thinking: enableThinking
      };
      
      // Send chat request
      if (enableStream) {
        // Handle streaming response
        const { response, streamId } = await sendChatRequest({
          messages: apiMessages,
          modelId,
          mcpServerIds: selectedServers,
          userId,
          stream: true,
          maxTokens,
          temperature,
          useMemory,
          useSwarm,
          useCodeInterpreter,
          useBrowser,
          extraParams
        });
        
        if (response) {
          let fullResponse = '';
          let fullThinking = '';
          let toolUseData: any[] = [];
          let fullToolInput:any[] = [];
          let fullInputContent = '';
          
          // Set streaming state and save stream ID
          setIsStreaming(true);
          setCurrentStreamId(streamId);
          // Keep loading state true during streaming
          onLoadingChange?.(true);
          
          // Add initial empty assistant message that will be updated with streaming content
          addMessage({ role: 'assistant', content: '' });
          
          // Process streaming response
          // Store abort controller reference
          const controller = processStreamResponse(
            response,
            // Content handler
            (content) => {
              // Stop thinking when we start receiving content
              if (isThinking) {
                setIsThinking(false);
              }
              
              fullResponse += content;
              updateLastMessage(
                fullResponse || '',
                undefined,
                undefined,
                undefined,
                undefined,
                undefined,
                false );
            },
            // Tool use handler
            (toolUse) => {
              try {
                const toolUseJson = JSON.parse(JSON.parse(toolUse));
                console.log(`ontoolUseData:${toolUseJson}`);
 
                toolUseData = toolUseJson[1];


                  // Update last assistant message with tool use data
                // Update last message with tool use data
                // Keep existing content but add tool use
                const { messages } = useStore.getState();
                const lastMessageIndex = messages.length - 1;
                if (lastMessageIndex >= 0 && messages[lastMessageIndex].role === 'assistant') {
                  const currentContent = messages[lastMessageIndex].content;
                  updateLastMessage(
                    currentContent || '',
                    undefined,
                    [ ...messages[lastMessageIndex].toolUse || [], toolUseData],
                    undefined,
                    undefined,
                    undefined,
                    false);
                }
                  // console.log("messages:", messages);

              } catch (error) {
                console.error('Failed to parse tool use data:', error);
              }
            },
              // Thinking handler - directly sent from server, not extracted from content
              (thinking) => {
                if (thinking && thinking.trim()) {
                  // Set thinking state to true when we start receiving thinking content
                  if (!isThinking) {
                    setIsThinking(true);
                  }
                  
                  // Accumulate thinking content
                  fullThinking += thinking;
                  const { messages } = useStore.getState();
                  const lastMessageIndex = messages.length - 1;
                  if (lastMessageIndex >= 0 && messages[lastMessageIndex].role === 'assistant') {
                    const currentContent = messages[lastMessageIndex].content;
                    updateLastMessage(currentContent, fullThinking, undefined, undefined,undefined,undefined, true);
                  }
                }
              },
            // Error handler
            (error) => {
              console.error('Stream error:', error);
              addMessage({
                role: 'assistant',
                content: 'An error occurred while processing your request.'
              });
              setIsStreaming(false);
              setCurrentStreamId(null);
              onLoadingChange?.(false);
              abortControllerRef.current = null;
            },
            // Done handler
            () => {
              setIsStreaming(false);
              setCurrentStreamId(null);
              setIsThinking(false);
              onLoadingChange?.(false);
              abortControllerRef.current = null;
            },
            // Tool input handler - directly sent from server
            (toolInput) => {
              // console.log(`ontoolInput:${toolInput}`)
              if (toolInput !== '<END>'){
                  fullInputContent += toolInput;
              }else{
                  fullToolInput = [...fullToolInput,fullInputContent]
                  fullInputContent = ''
              }
              const { messages } = useStore.getState();
              const lastMessageIndex = messages.length - 1;
              if (lastMessageIndex >= 0 && messages[lastMessageIndex].role === 'assistant') {
                const currentContent = messages[lastMessageIndex].content;
                const currentToolInput = messages[lastMessageIndex].toolInput;
                updateLastMessage(
                  currentContent || '',
                  undefined,
                  undefined,
                  undefined,
                  fullToolInput.length ? fullToolInput:undefined ,
                  undefined,
                  false
                );
              }

            },
            (toolName) => {
              // Stop thinking when we start receiving tool names
              if (isThinking) {
                setIsThinking(false);
              }
              
              console.log(`ontoolName:${toolName}`);
                const { messages } = useStore.getState();
                const lastMessageIndex = messages.length - 1;
                if (lastMessageIndex >= 0 && messages[lastMessageIndex].role === 'assistant') {
                  const currentContent = messages[lastMessageIndex].content;
                  const currentToolName = messages[lastMessageIndex].toolName;
                  updateLastMessage(
                    currentContent || '',
                    undefined,
                    undefined,
                    [ ...currentToolName || [], toolName],
                    undefined,
                    undefined,
                    false
                  );
                }

            }
          );
          
          // Store the abort controller
          abortControllerRef.current = controller;
        }
      } else {
        // Handle non-streaming response
        const { message, messageExtras } = await sendChatRequest({
          messages: apiMessages,
          modelId,
          mcpServerIds: selectedServers,
          userId,
          stream: false,
          maxTokens,
          temperature,
          useMemory,
          useSwarm,
          useCodeInterpreter,
          useBrowser,
          extraParams
        });
        // Extract thinking from message
        const { thinking, cleanContent: contentAfterThinking } = extractThinking(message);
        
        // Extract tool use from content
        const { toolUse: extractedToolUse, cleanContent: contentAfterToolUse } = extractToolUse(contentAfterThinking);
        
        // Extract tool input from content
        const { toolInput, cleanContent } = extractToolInput(contentAfterToolUse);
        
        
        // Combine extracted tool use with any from messageExtras
        let toolUseData = extractedToolUse ? 
          (Array.isArray(extractedToolUse) ? extractedToolUse : [extractedToolUse]) : 
          [];
          
        // Add tool use from messageExtras if available
        if (messageExtras && messageExtras.tool_use) {
          try {
            const extraToolUse = messageExtras.tool_use;
            if (Array.isArray(extraToolUse) && extraToolUse.length > 0) {
              toolUseData = [...toolUseData, ...extraToolUse];
            }
          } catch (error) {
            console.error('Failed to parse tool use data:', error);
          }
        }
        
        // Add assistant message with tool use data and tool input if available
        addMessage({
          role: 'assistant',
          content: cleanContent,
          thinking: thinking || undefined,
          toolUse: toolUseData,
          toolName: toolUseData,
          toolInput: toolInput ? [toolInput] : undefined
        });
      }
    } catch (error) {
      console.error('Chat error:', error);
      addMessage({ 
        role: 'assistant', 
        content: 'An error occurred while processing your request.' 
      });
    } finally {
      setIsLoading(false);
      // Only reset loading state for non-streaming requests
      if (!enableStream) {
        onLoadingChange?.(false);
        setIsStreaming(false);
        setCurrentStreamId(null);
        abortControllerRef.current = null;
      }
      // For streaming requests, loading state will be reset in the done/error handlers
    }
  };
  
  const handleAddFiles = (newFiles: FileItem[]) => {
    setFiles([...files, ...newFiles]);
  };
  
  const handleRemoveFile = (fileId: string) => {
    setFiles(files.filter(file => file.id !== fileId));
  };
  
  const handleTranscription = (text: string, isUser?: boolean) => {
    // Add the message with the appropriate role based on the isUser flag
    addMessage({
      role: isUser ? 'user' : 'assistant',
      content: text
    });
  };

  // Handle tool use data from WebSocket
  const handleToolUse = (toolUseData: any) => {
    console.log('Tool use data received:', toolUseData);
    return
  };
  
  // Handle tool result data from WebSocket
  const handleToolResult = (toolResultData: any) => {
    console.log('Tool result data received:', toolResultData);
  };
  
  const toggleVoiceMode = () => {
    setIsVoiceMode(!isVoiceMode);
  };
  
  return (
    <div className="p-4">
      {showFileUpload && (
        <FileUpload
          files={files}
          onAddFiles={handleAddFiles}
          onRemoveFile={handleRemoveFile}
        />
      )}
      
      <form onSubmit={handleSubmit} className="flex items-center space-x-2">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className={`h-10 w-10 ${showFileUpload ? 'bg-gray-200 dark:bg-gray-700' : ''}`}
          onClick={() => setShowFileUpload(!showFileUpload)}
          disabled={isLoading}
        >
          <Paperclip className="h-5 w-5" />
        </Button>
        
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className={`h-10 w-10 ${isVoiceMode ? 'bg-blue-200 dark:bg-blue-700' : ''}`}
          onClick={toggleVoiceMode}
          disabled={isLoading || disabled}
        >
          {isVoiceMode ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
        </Button>
        
        <div className="relative flex-1">
          {isVoiceMode ? (
            <div className="w-full min-h-[60px] border border-gray-300 rounded-md">
              <AudioRecorder
                apiKey={process.env.NEXT_PUBLIC_API_KEY || ''}
                userId={userId}
                mcpServerIds={selectedServers}
                onTranscription={handleTranscription}
                onToolUse={handleToolUse}
                onToolResult={handleToolResult}
              />
            </div>
          ) : (
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={disabled ? "Loading MCP servers..." : files.length > 0 ? "Add a message or send files..." : "Type your message..."}
              className="w-full p-3 pr-12 rounded-md border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none min-h-[60px]"
              rows={1}
              disabled={isLoading || disabled}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
            />
          )}
        </div>
        
        {isStreaming ? (
          <Button
            type="button"
            onClick={handleStopGeneration}
            className="h-10 bg-red-500 hover:bg-red-600"
          >
            Stop
          </Button>
        ) : (
          <Button
            type="submit"
            disabled={isLoading || disabled || (!prompt.trim() && files.length === 0) || !selectedModel}
            className="h-10"
          >
            {isLoading ? 'Sending...' : disabled ? 'Loading...' : 'Send'}
          </Button>
        )}
      </form>
    </div>
  );
}
