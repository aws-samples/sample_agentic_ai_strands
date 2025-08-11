# AWS DCV Live View Integration

This directory contains components for integrating AWS DCV (Desktop Cloud Visualization) live view functionality into the React UI.

## Overview

When the assistant uses the `browser_init` tool, it returns a result containing a presigned URL for accessing an AWS DCV session. This integration automatically detects these responses and provides a user-friendly way to open the live view in a new browser tab.

## Components

### DCVButton.tsx
- **Purpose**: Renders a button to open the DCV live view
- **Usage**: Automatically displayed in tool results for `browser_init` tools
- **Features**:
  - Extracts presigned URL from tool results
  - Validates URL format
  - Opens DCV viewer in new tab
  - Shows session information
  - Error handling for invalid URLs

### DCVButtonWrapper
- **Purpose**: Conditional wrapper that only renders for `browser_init` tools
- **Integration**: Used in `ToolCallDisplay.tsx` to inject DCV functionality

## Pages

### /dcv-viewer/[presignedUrl]
- **Purpose**: Full-screen DCV viewer page
- **Features**:
  - Loads AWS DCV Web Client SDK
  - Handles authentication and connection
  - Display size controls (HD, HD+, Full HD, 2K)
  - Real-time connection status
  - Debug information panel
  - Error handling and retry functionality

## Utilities

### lib/dcv/dcv-utils.ts
- URL extraction and validation
- DCV SDK loading
- Authentication parameter handling
- Display layout management

### lib/dcv/types.ts
- TypeScript interfaces for DCV components
- Global DCV SDK type definitions

## Usage Flow

1. **Tool Execution**: Assistant calls `browser_init` tool
2. **Result Processing**: Tool returns result with `<presigned_url>URL</presigned_url>`
3. **Auto-Detection**: `ToolCallDisplay` detects `browser_init` tool
4. **Button Render**: `DCVButtonWrapper` shows "Open Live View" button
5. **User Action**: User clicks button
6. **New Tab**: Opens `/dcv-viewer/[encodedUrl]` in new tab
7. **Connection**: Page loads DCV SDK and connects to session

## Sample Tool Result

```
Browser session initialized successfully.
Session ID: session-abc123
<presigned_url>https://dcv-gateway.us-east-1.amazonaws.com/session-abc123?token=xyz789&expires=1234567890</presigned_url>
The browser is ready for automation and live viewing.
```

## Error Handling

The integration handles several error scenarios:
- Invalid or missing presigned URLs
- DCV SDK loading failures
- Authentication failures
- Connection timeouts
- Session expiration

## Testing

To test the integration:

1. Create a mock `browser_init` tool result with a valid presigned URL
2. Verify the DCV button appears in the tool result display
3. Click the button to open the DCV viewer
4. Verify the viewer attempts to connect (will fail without real session)
5. Check error handling with invalid URLs

## Dependencies

- AWS DCV Web Client SDK (copied to `/public/dcvjs/`)
- Next.js dynamic routing
- React hooks for state management
- Tailwind CSS for styling

## Browser Support

Supports the same browsers as the AWS DCV Web Client SDK:
- Chrome (latest 3 versions)
- Firefox (latest 3 versions)
- Edge (latest 3 versions)
- Safari for macOS (latest 3 versions)

## Security Considerations

- Presigned URLs are validated before use
- URLs are properly encoded for routing
- DCV SDK loads from local public directory
- No sensitive data is logged in production