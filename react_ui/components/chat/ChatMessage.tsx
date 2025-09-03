'use client';

import { useState, useEffect } from 'react';
import { Message, ToolCall } from '@/lib/store';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { FileText, ChevronDown, ChevronRight, Lightbulb, Loader2, Check, ClipboardCopy } from 'lucide-react';
import { ToolCallDisplay } from './ToolCallDisplay';
import { Button } from '@/components/ui/button';

interface ChatMessageProps {
  message: Message;
  isRunning?: boolean;
}

// Loading dots animation component (same as ToolCallDisplay)
const LoadingDots = () => {
  const [dots, setDots] = useState('');
  
  useEffect(() => {
    const interval = setInterval(() => {
      setDots(prev => {
        if (prev === '...') return '';
        return prev + '.';
      });
    }, 500);
    
    return () => clearInterval(interval);
  }, []);
  
  return <span className="inline-block w-6">{dots}</span>;
};

// Animated progress bar (same as ToolCallDisplay)
const ProgressBar = ({ isActive }: { isActive: boolean }) => {
  return (
    <div className="w-full h-1 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
      <div
        className={cn(
          "h-full bg-blue-500 transition-all duration-1000 ease-in-out",
          isActive ? "w-full animate-pulse" : "w-0"
        )}
      />
    </div>
  );
};

// Convert toolName, toolInput and toolUse data to ToolCall format
// 数据流：toolNameArray -> toolInputArray -> toolUseArray
const convertToToolCalls = (toolNameArray?: any[], toolInputArray?: any[], toolUseArray?: any[]): ToolCall[] => {
  const toolCalls: ToolCall[] = [];
  
  // 解析各个数据源
  const toolNames = toolNameArray || [];
  const toolInputs = toolInputArray || [];
  
  // 解析toolUse数据（工具结果）
  let toolResults: any[] = [];
  if (toolUseArray && toolUseArray.length > 0) {
    try {
      toolResults = toolUseArray.map(item =>
        typeof item === 'string' ? JSON.parse(item) : item
      );
    } catch (e) {
      console.warn('Failed to parse toolUseArray:', toolUseArray);
    }
  }

  // 确定最大工具数量
  const maxToolCount = Math.max(toolNames.length, toolInputs.length, toolResults.length);
  
  // 为每个工具创建ToolCall对象
  for (let index = 0; index < maxToolCount; index++) {
    const toolName = toolNames[index];
    const toolInput = toolInputs[index];
    const toolResult = toolResults[index];
    
    // 确定工具状态和内容
    let status: 'pending' | 'running' | 'completed' | 'error' = 'pending';
    let name = 'unknown_tool';
    let toolArguments = {};
    let result: any = undefined;
    let endTime: number | undefined = undefined;
    
    // 根据当前接收到的数据确定状态
    // 阶段1：只有toolName - 工具开始执行
    if (toolName && !toolInput && !toolResult) {
      status = 'running';
      name = toolName;
      toolArguments = {};
    }
    // 阶段2：有toolName和toolInput - 工具正在执行，显示参数
    else if (toolName && toolInput && !toolResult) {
      status = 'running';
      name = toolName;
      toolArguments = toolInput;
    }
    // 阶段3：有toolResult - 工具执行完成
    else if (toolResult) {
      status = toolResult.tool_result?.status === 'success' ? 'completed' : 'error';
      name = toolResult.tool_name || toolName || 'unknown_tool';
      toolArguments = toolInput || toolResult.input || {};
      result = toolResult.tool_result?.content?.[0]?.text || 'No result content';
      endTime = Date.now() - (index * 500);
    }
    // 其他情况的fallback处理
    else if (toolInput) {
      status = 'running';
      name = toolName || 'unknown_tool';
      toolArguments = toolInput;
    }
    else if (toolName) {
      status = 'running';
      name = toolName;
      toolArguments = {};
    }
    
    // 创建ToolCall对象
    const toolCall: ToolCall = {
      id: toolResult?.toolUseId || `tool-${index}`,
      name,
      arguments: toolArguments,
      status,
      startTime: Date.now() - (index * 1000),
      ...(endTime && { endTime }),
      ...(result && { result })
    };
    
    toolCalls.push(toolCall);
  }
  
  return toolCalls;
};

// Copy button component with copied state feedback
const CopyButton = ({ content }: { content: string }) => {
  const [copied, setCopied] = useState(false);
  
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text:', err);
    }
  };
  
  return (
    <Button 
      variant="ghost" 
      size="sm" 
      className="absolute bottom-2 right-2 px-2 opacity-70 hover:opacity-100 transition-opacity flex items-center gap-1"
      onClick={handleCopy}
      title="Copy to clipboard"
    >
      {copied ? (
        <>
          <Check className="h-4 w-4" /> <span className="text-xs">Copied</span>
        </>
      ) : (
        <>
          <ClipboardCopy className="h-4 w-4" /> <span className="text-xs">Copy</span>
        </>
      )}
    </Button>
  );
};

export function ChatMessage({ message, isRunning = false }: ChatMessageProps) {
  const [showThinking, setShowThinking] = useState(false);
  // console.log("isRunning:",isRunning)
  return (
    <div className={cn(
      "flex w-full items-start gap-4 py-4",
      message.role === 'user' ? "justify-start" : "justify-start"
    )}>
      {/* Avatar/Icon */}
      <div className={cn(
        "flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-md border shadow",
        message.role === 'user' 
          ? "bg-blue-100 text-blue-900" 
          : "bg-white"
      )}>
        {message.role === 'user' ? '👤' : (
          <img 
            src="/bedrock.webp" 
            alt="Amazon Bedrock"
            className="h-full w-full object-cover rounded-md"
          />
        )}
      </div>
      
      {/* Message Content */}
      <div className={cn(
        "flex flex-col space-y-3 max-w-4xl flex-1",
        message.role === 'user' ? "items-start" : "items-start"
      )}>
        {/* Role Label */}
        <div className="text-sm text-muted-foreground">
          {message.role === 'user' ? 'You' : 'Assistant'}
        </div>
        
        {/* Thinking Section (if available) */}
        {message.thinking && (
          <div className="w-full">
            <div className="border border-blue-300 bg-blue-50/50 dark:border-blue-600 dark:bg-blue-900/20 shadow-lg shadow-blue-500/20 rounded-lg overflow-hidden transition-all duration-300 ease-in-out">
              {/* Thinking header */}
              <div
                className="flex items-center gap-2 p-3 cursor-pointer hover:bg-blue-100/50 dark:hover:bg-blue-700/50 transition-colors"
                onClick={() => setShowThinking(!showThinking)}
              >
                {/* Thinking icon with status indicator */}
                <div className="relative">
                  <div className={cn(
                    "p-1.5 rounded-md transition-colors",
                    message.isThinking && "bg-blue-100 text-blue-600 dark:bg-blue-900/50 dark:text-blue-400",
                    !message.isThinking && "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
                  )}>
                    {message.isThinking ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Lightbulb className="h-3.5 w-3.5" />
                    )}
                  </div>
                  
                  {/* Status dot */}
                  <div className={cn(
                    "absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border border-white dark:border-gray-800",
                    message.isThinking && "bg-blue-500 animate-pulse",
                    !message.isThinking && "bg-gray-400"
                  )} />
                </div>
                
                {/* Thinking info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h4 className="font-medium text-sm text-blue-800 dark:text-blue-200">
                      Thinking
                    </h4>
                    {message.isThinking && (
                      <span className="text-xs text-blue-600 dark:text-blue-400 font-medium">
                        Thinking<LoadingDots />
                      </span>
                    )}
                  </div>
                </div>
                
                {/* Expand/collapse icon */}
                <div className="text-blue-400">
                  {showThinking ? (
                    <ChevronDown className="h-3.5 w-3.5" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5" />
                  )}
                </div>
              </div>
              
              {/* Thinking content (expandable) */}
              {showThinking && (
                <div className="border-t border-blue-200 dark:border-blue-700">
                  <div className="p-3">
                    <div className="bg-white dark:bg-gray-900 border border-blue-200 dark:border-blue-700 rounded p-2.5 text-sm max-h-80 overflow-auto">
                      <div className="text-blue-800 dark:text-blue-200 whitespace-pre-wrap font-mono leading-relaxed text-xs">
                        {message.thinking}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
            
            {/* Progress bar for thinking state */}
            {message.isThinking && (
              <div className="mt-2">
                <ProgressBar isActive={message.isThinking} />
              </div>
            )}
          </div>
        )}
        
        {/* Tool Calls Section - Enhanced with better data handling */}
        {((message.toolCalls && message.toolCalls.length > 0) ||
          (message.toolUse && message.toolUse.length > 0) ||
          (message.toolName && message.toolName.length > 0) ||
          (message.toolInput && message.toolInput.length > 0)) && (
          <div className="w-full space-y-3">
            {/* Render toolCalls if available */}
            {message.toolCalls && message.toolCalls.length > 0 &&
              message.toolCalls.map((toolCall, index) => (
                <ToolCallDisplay
                  key={toolCall.id || `toolcall-${index}`}
                  toolCall={toolCall}
                  className="animate-in slide-in-from-left-2 duration-300"
                />
              ))
            }
            
            {/* Fallback: Convert toolInput and toolUse to toolCalls format if toolCalls not available */}
            {(!message.toolCalls || message.toolCalls.length === 0) && (message.toolUse || message.toolInput || message.toolName) &&
              convertToToolCalls(
                message.toolName ? message.toolName : undefined,
                message.toolInput ? message.toolInput : undefined,
                message.toolUse
              ).map((toolCall: ToolCall, index: number) => (
                <ToolCallDisplay
                  key={toolCall.id || `converted-${index}`}
                  toolCall={toolCall}
                  className="animate-in slide-in-from-left-2 duration-300"
                />
              ))
            }
          </div>
        )}
        
        {/* Message Bubble */}
        {message.content && (
          <div className={cn(
            "rounded-lg px-4 py-3 shadow-sm w-full relative",
            message.role === 'user' 
              ? "bg-blue-50 text-blue-900 dark:bg-blue-900/20 dark:text-blue-100" 
              : "bg-white border border-gray-200 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
          )}>
            {/* Structured Content or Markdown */}
            {typeof message.content === 'string' ? (
              // Regular markdown content
              <ReactMarkdown
                className="prose prose-sm max-w-none dark:prose-invert"
                remarkPlugins={[remarkGfm]}
                components={{
                  code(props) {
                    const { children, className, node, ...rest } = props;
                    const match = /language-(\w+)/.exec(className || '');
                    const isInline = !match;
                    
                    return isInline ? (
                      <code className={className} {...rest}>
                        {children}
                      </code>
                    ) : (
                      <SyntaxHighlighter
                        // @ts-ignore - styles typing issue in react-syntax-highlighter
                        style={oneLight}
                        language={match?.[1] || 'text'}
                        PreTag="div"
                        {...rest}
                      >
                        {String(children).replace(/\n$/, '')}
                      </SyntaxHighlighter>
                    );
                  }
                }}
              >
                {message.content + ((isRunning && message.role === 'assistant') ? '▌' : '')}
              </ReactMarkdown>
            ) : (
              // Structured content (array of ContentItem)
              <div className="space-y-4">
                {message.content.map((item, index) => (
                  <div key={index}>
                    {/* Text content */}
                    {item.type === 'text' && item.text && (
                      <ReactMarkdown
                        className="prose prose-sm max-w-none dark:prose-invert"
                        remarkPlugins={[remarkGfm]}
                        components={{
                          code(props) {
                            const { children, className, node, ...rest } = props;
                            const match = /language-(\w+)/.exec(className || '');
                            const isInline = !match;
                            
                            return isInline ? (
                              <code className={className} {...rest}>
                                {children}
                              </code>
                            ) : (
                              <SyntaxHighlighter
                                // @ts-ignore - styles typing issue in react-syntax-highlighter
                                style={oneLight}
                                language={match?.[1] || 'text'}
                                PreTag="div"
                                {...rest}
                              >
                                {String(children).replace(/\n$/, '')}
                              </SyntaxHighlighter>
                            );
                          }
                        }}
                      >
                        {item.text}
                      </ReactMarkdown>
                    )}
                    
                    {/* Image content */}
                    {item.type === 'image_url' && item.image_url?.url && (
                      <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden max-w-lg">
                        <img 
                          src={item.image_url.url}
                          alt="Attached image" 
                          className="w-full h-auto object-contain"
                        />
                      </div>
                    )}
                    
                    {/* File content */}
                    {item.type === 'file' && item.file && (
                      <div className="flex items-center gap-2 bg-gray-50 dark:bg-gray-800 p-3 rounded border border-gray-200 dark:border-gray-700">
                        <FileText className="h-5 w-5 text-blue-600" />
                        <div className="flex-1">
                          <div className="text-sm font-medium">{item.file.filename || "Attached file"}</div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">
                            {item.file.file_id ? "File ID: " + item.file.file_id : "File attached"}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
                
                {isRunning && <span className="animate-pulse">▌</span>}
              </div>
            )}
            {/* Copy button for message content */}
            {message.role === 'assistant' && message.content && (
              <CopyButton content={typeof message.content === 'string' ? message.content : message.content.map(item => {
                if (item.type === 'text') return item.text;
                return '';
              }).join('\n')}/>
            )}
          </div>
        )}
        
        {/* Loading indicator for messages without content but with tool calls */}
        {!message.content && isRunning && (
          <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
            <span>Processing...</span>
          </div>
        )}
      </div>
    </div>
  );
}
