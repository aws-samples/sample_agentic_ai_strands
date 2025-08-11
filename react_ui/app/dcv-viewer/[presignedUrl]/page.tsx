'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Monitor, Settings, RefreshCw, AlertCircle, ExternalLink } from 'lucide-react';
import {
  loadDCVSDK,
  validatePresignedUrl,
  getStaticDCVContainerId,
  formatDCVError,
  extractAuthParams,
  DISPLAY_LAYOUTS,
  getDefaultDisplayLayout,
  parseBrowserInitResult
} from '@/lib/dcv/dcv-utils';
import { DCVDisplayLayout, DCVStatus, DCVError } from '@/lib/dcv/types';

export default function DCVViewerPage() {
  const params = useParams();
  const containerRef = useRef<HTMLDivElement>(null);
  const dcvConnectionRef = useRef<any>(null);
  const containerId = useRef<string>(getStaticDCVContainerId());
  const [isClient, setIsClient] = useState(false);
  
  // Decode the presigned URL from the route parameter
  const presignedUrl = params?.presignedUrl ? decodeURIComponent(params.presignedUrl as string) : '';
  
  // Extract session ID from the presigned URL
  const extractedSessionId = React.useMemo(() => {
    const result = parseBrowserInitResult(`<presigned_url>${presignedUrl}</presigned_url>`);
    return result.sessionId || 'unknown-session';
  }, [presignedUrl]);
  
  // State management
  const [status, setStatus] = useState<DCVStatus>({
    isConnected: false,
    isConnecting: false
  });
  const [selectedLayout, setSelectedLayout] = useState<DCVDisplayLayout>(getDefaultDisplayLayout());
  const [hasControl, setHasControl] = useState(false);
  const [sdkLoaded, setSdkLoaded] = useState(false);
  const [debugInfo, setDebugInfo] = useState<string[]>([]);

  // Debug logging function
  const addDebugLog = (message: string) => {
    if (!isClient) return; // Avoid hydration issues
    const timestamp = new Date().toLocaleTimeString();
    const logMessage = `[${timestamp}] ${message}`;
    console.log(logMessage);
    setDebugInfo(prev => [...prev.slice(-19), logMessage]); // Keep last 20 messages
  };

  // Handle client-side hydration
  useEffect(() => {
    setIsClient(true);
  }, []);

  // Validate URL on mount (client-side only)
  useEffect(() => {
    if (!isClient) return;

    if (!presignedUrl) {
      setStatus({
        isConnected: false,
        isConnecting: false,
        error: { code: 'INVALID_URL', message: 'No presigned URL provided' }
      });
      return;
    }

    if (!validatePresignedUrl(presignedUrl)) {
      setStatus({
        isConnected: false,
        isConnecting: false,
        error: { code: 'INVALID_URL', message: 'Invalid presigned URL format' }
      });
      return;
    }

    addDebugLog('Valid presigned URL detected');
    addDebugLog(`URL: ${presignedUrl.substring(0, 100)}...`);
  }, [presignedUrl, isClient]);

  // Load DCV SDK on mount (client-side only)
  useEffect(() => {
    if (!isClient || !presignedUrl || !validatePresignedUrl(presignedUrl)) {
      return;
    }

    const loadSDK = async () => {
      try {
        addDebugLog('Loading DCV SDK...');
        
        // Set worker path globally before loading DCV SDK (like the Python implementation)
        const workerPath = `${window.location.origin}/dcvjs/dcv/`;
        (window as any).dcvWorkerPath = workerPath;
        addDebugLog(`Global DCV worker path set to: ${workerPath}`);
        
        await loadDCVSDK();
        setSdkLoaded(true);
        addDebugLog('DCV SDK loaded successfully');
        
        if (window.dcv?.version) {
          addDebugLog(`DCV SDK version: ${window.dcv.version}`);
        }
        
        // Set log level to INFO for production
        if (window.dcv?.setLogLevel && window.dcv?.LogLevel) {
          window.dcv.setLogLevel(window.dcv.LogLevel.INFO);
          addDebugLog('DCV log level set to INFO');
        }

        // Ensure worker path is set correctly with absolute URL (redundant but safe)
        if (window.dcv?.setWorkerPath) {
          window.dcv.setWorkerPath(workerPath);
          addDebugLog(`DCV worker path confirmed: ${workerPath}`);
        }
      } catch (error) {
        addDebugLog(`Failed to load DCV SDK: ${formatDCVError(error)}`);
        setStatus({
          isConnected: false,
          isConnecting: false,
          error: { code: 'SDK_LOAD_ERROR', message: formatDCVError(error) }
        });
      }
    };

    loadSDK();
  }, [presignedUrl, isClient]);

  // Auto-connect when SDK is loaded (client-side only)
  useEffect(() => {
    if (isClient && sdkLoaded && presignedUrl && !status.isConnecting && !status.isConnected) {
      connectToSession();
    }
  }, [sdkLoaded, presignedUrl, isClient]);

  const connectToSession = async () => {
    if (!window.dcv || !presignedUrl) {
      addDebugLog('DCV SDK not available or no presigned URL');
      return;
    }

    setStatus(prev => ({ ...prev, isConnecting: true, error: undefined }));
    addDebugLog('Starting DCV authentication...');

    try {
      // Create authentication callback
      const authCallbacks = {
        promptCredentials: () => {
          addDebugLog('DCV requested credentials (unexpected for presigned URL)');
        },
        error: (auth: any, error: any) => {
          addDebugLog(`DCV auth error: ${formatDCVError(error)}`);
          setStatus({
            isConnected: false,
            isConnecting: false,
            error: { code: 'AUTH_ERROR', message: formatDCVError(error) }
          });
        },
        success: (auth: any, result: any[]) => {
          addDebugLog('DCV authentication successful');
          if (result && result[0]) {
            const { sessionId, authToken } = result[0];
            addDebugLog(`Session ID: ${sessionId}`);
            setStatus(prev => ({ ...prev, sessionId }));
            connectToSessionWithAuth(sessionId, authToken);
          } else {
            addDebugLog('No session data in auth result');
            setStatus({
              isConnected: false,
              isConnecting: false,
              error: { code: 'AUTH_ERROR', message: 'No session data received' }
            });
          }
        },
        httpExtraSearchParams: (method: string, url: string, body: any, returnType: string) => {
          return extractAuthParams(presignedUrl);
        }
      };

      window.dcv.authenticate(presignedUrl, authCallbacks);
    } catch (error) {
      addDebugLog(`Authentication failed: ${formatDCVError(error)}`);
      setStatus({
        isConnected: false,
        isConnecting: false,
        error: { code: 'CONNECTION_ERROR', message: formatDCVError(error) }
      });
    }
  };

  const connectToSessionWithAuth = async (sessionId: string, authToken: string) => {
    if (!window.dcv) return;

    addDebugLog(`Connecting to session: ${sessionId}`);

    const connectOptions = {
      url: presignedUrl,
      sessionId,
      authToken,
      divId: containerId.current,
      baseUrl: `${window.location.origin}/dcvjs`,
      callbacks: {
        firstFrame: () => {
          addDebugLog('First frame received - connection established!');
          setStatus({
            isConnected: true,
            isConnecting: false,
            sessionId
          });
          requestDisplayLayout();
        },
        error: (error: any) => {
          addDebugLog(`Connection error: ${formatDCVError(error)}`);
          setStatus({
            isConnected: false,
            isConnecting: false,
            error: { code: 'CONNECTION_ERROR', message: formatDCVError(error) }
          });
        },
        httpExtraSearchParams: () => extractAuthParams(presignedUrl),
        displayLayout: (serverWidth: number, serverHeight: number, heads: any[]) => {
          addDebugLog(`Display layout callback: ${serverWidth}x${serverHeight}`);
          if (containerRef.current) {
            containerRef.current.style.width = `${selectedLayout.width}px`;
            containerRef.current.style.height = `${selectedLayout.height}px`;
          }
        }
      }
    };

    try {
      const connection = await window.dcv.connect(connectOptions);
      dcvConnectionRef.current = connection;
      addDebugLog('DCV connection object created');
    } catch (error) {
      addDebugLog(`Connect failed: ${formatDCVError(error)}`);
      setStatus({
        isConnected: false,
        isConnecting: false,
        error: { code: 'CONNECTION_ERROR', message: formatDCVError(error) }
      });
    }
  };

  const requestDisplayLayout = () => {
    if (dcvConnectionRef.current && dcvConnectionRef.current.requestDisplayLayout) {
      addDebugLog(`Requesting display layout: ${selectedLayout.width}x${selectedLayout.height}`);
      dcvConnectionRef.current.requestDisplayLayout([{
        name: "Main Display",
        rect: {
          x: 0,
          y: 0,
          width: selectedLayout.width,
          height: selectedLayout.height
        },
        primary: true
      }]);
    }
  };

  const handleDisplaySizeChange = (layout: DCVDisplayLayout) => {
    setSelectedLayout(layout);
    addDebugLog(`Changed display size to: ${layout.label}`);
    
    if (containerRef.current) {
      containerRef.current.style.width = `${layout.width}px`;
      containerRef.current.style.height = `${layout.height}px`;
    }

    // Request layout change if connected
    if (status.isConnected && dcvConnectionRef.current) {
      dcvConnectionRef.current.requestDisplayLayout([{
        name: "Main Display",
        rect: {
          x: 0,
          y: 0,
          width: layout.width,
          height: layout.height
        },
        primary: true
      }]);
    }
  };

  const handleReconnect = () => {
    addDebugLog('Reconnecting...');
    setStatus({
      isConnected: false,
      isConnecting: false,
      error: undefined
    });
    
    // Disconnect existing connection
    if (dcvConnectionRef.current && dcvConnectionRef.current.disconnect) {
      dcvConnectionRef.current.disconnect();
      dcvConnectionRef.current = null;
    }

    // Reconnect
    setTimeout(() => connectToSession(), 1000);
  };

  const getStatusMessage = () => {
    if (status.error) {
      return `Error: ${status.error.message}`;
    }
    if (status.isConnecting) {
      return 'Connecting to DCV session...';
    }
    if (status.isConnected) {
      return `Connected - ${selectedLayout.label}`;
    }
    return 'Initializing...';
  };

  const getStatusColor = () => {
    if (status.error) return 'text-red-600 dark:text-red-400';
    if (status.isConnecting) return 'text-blue-600 dark:text-blue-400';
    if (status.isConnected) return 'text-green-600 dark:text-green-400';
    return 'text-gray-600 dark:text-gray-400';
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-3">
              <Monitor className="h-6 w-6 text-blue-600" />
              <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                AWS DCV Live View
              </h1>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                Session: {extractedSessionId}
              </span>
            </div>
            
            <div className="flex items-center space-x-4">
              <span className={`text-sm ${getStatusColor()}`}>
                {getStatusMessage()}
              </span>
              
              {status.error && (
                <Button onClick={handleReconnect} size="sm" variant="outline">
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Retry
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Error Alert */}
        {status.error && (
          <Alert className="mb-6 border-red-200 bg-red-50 dark:bg-red-900/20">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              <strong>Connection Error:</strong> {status.error.message}
              <br />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Please check your network connection and try again.
              </span>
            </AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* DCV Display */}
          <div className="lg:col-span-3">
            <Card className="p-4">
              <div className="flex justify-center items-center bg-black rounded-lg overflow-hidden">
                <div
                  id={containerId.current}
                  ref={containerRef}
                  style={{
                    width: `${selectedLayout.width}px`,
                    height: `${selectedLayout.height}px`,
                    maxWidth: '100%',
                    maxHeight: '70vh'
                  }}
                  className="bg-black"
                >
                  {!status.isConnected && !status.isConnecting && (
                    <div className="flex items-center justify-center h-full text-white">
                      <div className="text-center">
                        <Monitor className="h-16 w-16 mx-auto mb-4 opacity-50" />
                        <p className="text-lg mb-2">DCV Session Not Connected</p>
                        <p className="text-sm opacity-75">
                          {status.error ? 'Connection failed' : 'Waiting for connection...'}
                        </p>
                      </div>
                    </div>
                  )}
                  
                  {status.isConnecting && (
                    <div className="flex items-center justify-center h-full text-white">
                      <div className="text-center">
                        <div className="animate-spin rounded-full h-16 w-16 border-4 border-blue-500 border-t-transparent mx-auto mb-4"></div>
                        <p className="text-lg mb-2">Connecting to DCV Session</p>
                        <p className="text-sm opacity-75">Please wait...</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </Card>
          </div>

          {/* Controls Panel */}
          <div className="lg:col-span-1 space-y-6">
            {/* Display Size Controls */}
            <Card className="p-4">
              <h3 className="text-lg font-medium mb-3 flex items-center">
                <Settings className="h-5 w-5 mr-2" />
                Display Size
              </h3>
              
              <div className="space-y-2">
                {DISPLAY_LAYOUTS.map((layout) => (
                  <Button
                    key={`${layout.width}x${layout.height}`}
                    onClick={() => handleDisplaySizeChange(layout)}
                    variant={selectedLayout.width === layout.width && selectedLayout.height === layout.height 
                      ? "default" : "outline"}
                    className="w-full justify-start"
                    size="sm"
                  >
                    {layout.label}
                  </Button>
                ))}
              </div>
            </Card>

            {/* Debug Info */}
            <Card className="p-4">
              <h3 className="text-lg font-medium mb-3">Debug Info</h3>
              <div className="bg-gray-900 text-green-400 p-3 rounded text-xs font-mono max-h-64 overflow-y-auto">
                {debugInfo.map((log, index) => (
                  <div key={index} className="mb-1">
                    {log}
                  </div>
                ))}
                {debugInfo.length === 0 && (
                  <div className="text-gray-500">No debug messages yet...</div>
                )}
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}