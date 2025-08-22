'use client';

import { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { ChevronDown, ChevronRight, Search, Code, Database, Globe, FileText, Settings, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { DCVButtonWrapper } from '@/components/dcv/DCVButton';

interface ToolCall {
  id: string;
  name: string;
  arguments: any;
  result?: any;
  status: 'pending' | 'running' | 'completed' | 'error';
  startTime?: number;
  endTime?: number;
}

interface ToolCallDisplayProps {
  toolCall: ToolCall;
  className?: string;
}

// Tool icon mapping
const getToolIcon = (toolName: string) => {
  const name = toolName.toLowerCase();
  if (name.includes('search') || name.includes('search')) return Search;
  if (name.includes('code') || name.includes('execute')) return Code;
  if (name.includes('database') || name.includes('sql')) return Database;
  if (name.includes('web') || name.includes('http')) return Globe;
  if (name.includes('file') || name.includes('read') || name.includes('write')) return FileText;
  return Settings;
};

// Loading dots animation component
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

// Animated progress bar
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

export function ToolCallDisplay({ toolCall, className }: ToolCallDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [showResult, setShowResult] = useState(false);
  
  const IconComponent = getToolIcon(toolCall.name);
  const isRunning = toolCall.status === 'running' || toolCall.status === 'pending';
  const isCompleted = toolCall.status === 'completed';
  const hasError = toolCall.status === 'error';
  
  // Auto-expand when running or completed
  useEffect(() => {
    if (toolCall.status === 'running' || toolCall.status === 'completed') {
      setIsExpanded(true);
    }
  }, [toolCall.status]);

  // Auto-expand result section for browser_init tools to show DCV button immediately
  useEffect(() => {
    if (toolCall.name.toLowerCase() === 'browser_init' && toolCall.status === 'completed' && toolCall.result) {
      setShowResult(true);
    }
  }, [toolCall.name, toolCall.status, toolCall.result]);
  
  // Calculate execution time
  const executionTime = toolCall.startTime && toolCall.endTime 
    ? ((toolCall.endTime - toolCall.startTime) / 1000).toFixed(2)
    : null;
  
  return (
    <div className={cn(
      "border rounded-lg overflow-hidden transition-all duration-300 ease-in-out",
      isRunning && "border-blue-300 bg-blue-50/50 dark:border-blue-600 dark:bg-blue-900/20 shadow-lg shadow-blue-500/20",
      isCompleted && "border-green-300 bg-green-50/50 dark:border-green-600 dark:bg-green-900/20 shadow-lg shadow-green-500/20",
      hasError && "border-red-300 bg-red-50/50 dark:border-red-600 dark:bg-red-900/20 shadow-lg shadow-red-500/20",
      !isRunning && !isCompleted && !hasError && "border-gray-200 bg-gray-50/50 dark:border-gray-700 dark:bg-gray-800/50 shadow-lg shadow-gray-500/10",
      className
    )}>
      {/* Tool header */}
      <div
        className="flex items-center gap-2 p-3 cursor-pointer hover:bg-gray-100/50 dark:hover:bg-gray-700/50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        {/* Tool icon with status indicator */}
        <div className="relative">
          <div className={cn(
            "p-1.5 rounded-md transition-colors",
            isRunning && "bg-blue-100 text-blue-600 dark:bg-blue-900/50 dark:text-blue-400",
            isCompleted && "bg-green-100 text-green-600 dark:bg-green-900/50 dark:text-green-400",
            hasError && "bg-red-100 text-red-600 dark:bg-red-900/50 dark:text-red-400",
            !isRunning && !isCompleted && !hasError && "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
          )}>
            {isRunning ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <IconComponent className="h-3.5 w-3.5" />
            )}
          </div>
          
          {/* Status dot */}
          <div className={cn(
            "absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border border-white dark:border-gray-800",
            isRunning && "bg-blue-500 animate-pulse",
            isCompleted && "bg-green-500",
            hasError && "bg-red-500",
            !isRunning && !isCompleted && !hasError && "bg-gray-400"
          )} />
        </div>
        
        {/* Tool info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h4 className="font-medium text-sm truncate">
              {toolCall.name}
            </h4>
            {isRunning && (
              <span className="text-xs text-blue-600 dark:text-blue-400 font-medium">
                Running<LoadingDots />
              </span>
            )}
            {isCompleted && executionTime && (
              <span className="text-xs text-green-600 dark:text-green-400">
                {/* {executionTime}s */}
              </span>
            )}
            {hasError && (
              <span className="text-xs text-red-600 dark:text-red-400 font-medium">
                Error
              </span>
            )}
          </div>
          
          {/* Progress bar for running tools */}
          {isRunning && (
            <div className="mt-2">
              <ProgressBar isActive={isRunning} />
            </div>
          )}
        </div>
        
        {/* Expand/collapse icon */}
        <div className="text-gray-400">
          {isExpanded ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
        </div>
      </div>
      
      {/* Tool details (expandable) */}
      {isExpanded && (
        <div className="border-t border-gray-200 dark:border-gray-700">
          {/* Tool arguments */}
          {toolCall.arguments && Object.keys(toolCall.arguments).length > 0 && (
            <div className="p-3 border-b border-gray-200 dark:border-gray-700">
              <button
                onClick={() => setShowDetails(!showDetails)}
                className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 mb-2 transition-colors"
              >
                {showDetails ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                Parameters
              </button>
              
              {showDetails && (
                <div className="bg-gray-50 dark:bg-gray-800 rounded p-2.5 text-xs">
                  <SyntaxHighlighter
                    language="json"
                    style={oneLight}
                    customStyle={{
                      margin: '0',
                      padding: '0',
                      background: 'transparent',
                      fontSize: '10px'
                    } as any}
                  >
                    {/* {JSON.stringify(toolCall.arguments, null, 2)} */}
                    {toolCall.arguments}
                  </SyntaxHighlighter>
                </div>
              )}
            </div>
          )}
          
          {/* Tool result */}
          {toolCall.result && (
            <div className="p-3 border-b border-gray-200 dark:border-gray-700">
              <button
                onClick={() => setShowResult(!showResult)}
                className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 mb-2 transition-colors"
              >
                {showResult ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                Result
              </button>
              
              {showResult && (
                <div className="space-y-3">
                  {/* DCV Button for browser_init tools */}
                  <DCVButtonWrapper
                    toolName={toolCall.name}
                    toolResult={typeof toolCall.result === 'string' ? toolCall.result : JSON.stringify(toolCall.result)}
                    className="mb-3"
                  />
                  
                  <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded p-2.5 text-sm max-h-80 overflow-auto">
                    {typeof toolCall.result === 'string' ? (
                      <ReactMarkdown
                        className="prose prose-sm max-w-none dark:prose-invert"
                        remarkPlugins={[remarkGfm]}
                        components={{
                          code(props) {
                            const { children, className, ...rest } = props;
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
                                customStyle={{ fontSize: '11px' } as any}
                                {...rest}
                              >
                                {String(children).replace(/\n$/, '')}
                              </SyntaxHighlighter>
                            );
                          }
                        }}
                      >
                      {toolCall.result}
                      </ReactMarkdown>
                    ) : (
                      <SyntaxHighlighter
                        language="json"
                        // @ts-ignore - styles typing issue in react-syntax-highlighter
                        style={oneLight}
                        customStyle={{
                          margin: '0',
                          padding: '0',
                          background: 'transparent',
                          fontSize: '11px'
                        } as any}
                      >
                        {JSON.stringify(toolCall.result, null, 2)}
                      </SyntaxHighlighter>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
          
          {/* Loading state for running tools */}
          {isRunning && !toolCall.result && (
            <div className="p-3">
              <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Executing tool...</span>
              </div>
            </div>
          )}
          
          {/* Error state */}
          {hasError && (
            <div className="p-3">
              <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded p-2.5">
                Tool execution failed
                {toolCall.result && (
                  <>
                    <button
                      onClick={() => setShowResult(!showResult)}
                      className="flex items-center gap-2 text-xs text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-200 mt-2 transition-colors"
                    >
                      {showResult ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                      Error Details
                    </button>
                    {showResult && (
                      <div className="mt-2 text-xs font-mono">
                        {typeof toolCall.result === 'string' ? toolCall.result : JSON.stringify(toolCall.result)}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
