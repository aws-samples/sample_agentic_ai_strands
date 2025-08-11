'use client';

import React from 'react';
import { Button } from '@/components/ui/button';
import { Monitor, ExternalLink } from 'lucide-react';
import { 
  extractPresignedUrl, 
  validatePresignedUrl, 
  createDCVViewerUrl,
  parseBrowserInitResult 
} from '@/lib/dcv/dcv-utils';

interface DCVButtonProps {
  toolResult: string;
  className?: string;
}

export function DCVButton({ toolResult, className }: DCVButtonProps) {
  const result = parseBrowserInitResult(toolResult);

  if (!result.success || !result.presignedUrl) {
    return (
      <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
        <Monitor className="h-4 w-4 text-red-600" />
        <span className="text-sm text-red-600 dark:text-red-400">
          {result.message || 'No live view available'}
        </span>
      </div>
    );
  }

  const handleOpenLiveView = () => {
    try {
      const viewerUrl = createDCVViewerUrl(result.presignedUrl);
      window.open(viewerUrl, '_blank', 'noopener,noreferrer');
    } catch (error) {
      console.error('Failed to open DCV viewer:', error);
      // You could add toast notification here
    }
  };

  return (
    <div className="flex flex-col gap-2 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-md">
      <div className="flex items-center gap-2 text-sm text-blue-800 dark:text-blue-200">
        <Monitor className="h-4 w-4" />
        <span>AWS DCV Live View Available</span>
      </div>
      
      {result.sessionId && (
        <div className="text-xs text-blue-600 dark:text-blue-400">
          Session ID: {result.sessionId}
        </div>
      )}
      
      <Button
        onClick={handleOpenLiveView}
        className={`self-start bg-blue-600 hover:bg-blue-700 text-white ${className}`}
        size="sm"
      >
        <Monitor className="h-4 w-4 mr-2" />
        Open Live View
        <ExternalLink className="h-3 w-3 ml-2" />
      </Button>
      
      <div className="text-xs text-blue-600 dark:text-blue-400">
        {result.message}
      </div>
    </div>
  );
}

interface DCVButtonWrapperProps {
  toolName: string;
  toolResult: string;
  className?: string;
}

/**
 * Wrapper component that only renders DCVButton for browser_init tools
 */
export function DCVButtonWrapper({ toolName, toolResult, className }: DCVButtonWrapperProps) {
  // Only render for browser_init tools
  if (!toolName || toolName.toLowerCase() !== 'browser_init') {
    return null;
  }

  // Only render if we have a tool result
  if (!toolResult || typeof toolResult !== 'string') {
    return null;
  }

  // Check if there's actually a presigned URL in the result
  const presignedUrl = extractPresignedUrl(toolResult);
  if (!presignedUrl) {
    return null;
  }

  return <DCVButton toolResult={toolResult} className={className} />;
}

export default DCVButton;