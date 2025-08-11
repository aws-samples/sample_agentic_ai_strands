// TypeScript types for AWS DCV integration

export interface DCVConnection {
  presignedUrl: string;
  sessionId?: string;
  authToken?: string;
  connection?: any;
}

export interface DCVDisplayLayout {
  width: number;
  height: number;
  label: string;
}

export interface DCVError {
  code: string;
  message: string;
  statusCode?: number;
}

export interface DCVCallbacks {
  firstFrame?: () => void;
  error?: (error: DCVError) => void;
  displayLayout?: (width: number, height: number, heads: any[]) => void;
  httpExtraSearchParams?: (method: string, url: string, body: any, returnType: string) => URLSearchParams;
}

export interface DCVConnectOptions {
  url: string;
  sessionId: string;
  authToken: string;
  divId: string;
  baseUrl?: string;
  callbacks?: DCVCallbacks;
}

export interface DCVAuthResult {
  sessionId: string;
  authToken: string;
}

export interface DCVStatus {
  isConnected: boolean;
  isConnecting: boolean;
  error?: DCVError;
  sessionId?: string;
}

// Tool-related types
export interface BrowserInitToolResult {
  presignedUrl: string;
  sessionId?: string;
  success: boolean;
  message?: string;
}

// DCV SDK global interface
declare global {
  interface Window {
    dcv?: {
      version?: string;
      setLogLevel?: (level: any) => void;
      LogLevel?: {
        DEBUG: any;
        INFO: any;
        WARN: any;
        ERROR: any;
      };
      authenticate: (
        url: string,
        callbacks: {
          promptCredentials?: () => void;
          error?: (auth: any, error: any) => void;
          success?: (auth: any, result: DCVAuthResult[]) => void;
          httpExtraSearchParams?: (method: string, url: string, body: any, returnType: string) => URLSearchParams;
        }
      ) => void;
      connect: (options: DCVConnectOptions) => Promise<any>;
      setWorkerPath?: (path: string) => void;
    };
    dcvWorkerPath?: string;
  }
}