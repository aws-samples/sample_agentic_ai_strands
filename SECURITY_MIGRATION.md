# Security Migration Guide

## Overview

This guide helps you upgrade existing deployments to the new secure architecture that fixes critical security vulnerabilities.

## Critical Changes

### User Authentication with Amazon Cognito (BREAKING)

#### What Changed
- The backend no longer accepts the shared `API_KEY`, and it ignores the `X-User-ID` header.
  Previously any holder of the shared key could set `X-User-ID` to another user's ID and read
  or change that user's chat history and MCP server configurations (CWE-287 / CWE-639).
- Every request must carry the signed-in user's Cognito **access token**
  (`Authorization: Bearer <token>`). The backend verifies the signature (JWKS), issuer, expiry,
  `token_use=access` and `client_id`, and takes the user ID from the `sub` claim.
- The web UI signs users in with Amazon Cognito (Amplify Authenticator). The editable
  "User ID" field is replaced by the signed-in user and a Sign out button.
- The CDK stack creates a Cognito user pool (admin-created users only) and app client, and no
  longer creates or injects the `<prefix>/api-key` secret.

#### Migration Steps
1. Set `COGNITO_USER_POOL_ID` and `COGNITO_APP_CLIENT_ID` for both the backend and the
   frontend (CDK does this for you). If either is missing, the backend rejects every request.
2. Remove `API_KEY` and `NEXT_PUBLIC_API_KEY` from your environment files.
3. Create users: `aws cognito-idp admin-create-user --user-pool-id <id> --username <email>`.
4. Existing chat history and per-user MCP server configurations were stored under the old
   client-generated IDs and are not visible under the new Cognito user IDs.
5. Scripts that call the API directly must send a Cognito access token instead of the API key
   (see `tests/test_chat_api.sh`).


### 1. API Key Handling

**BREAKING CHANGE**: API keys are no longer exposed to clients.

#### What Changed
- Removed endpoint: `GET /api/v1/auth/api-key`
- API keys now handled server-side only
- Frontend authentication flow updated

#### Migration Steps

1. **Update Environment Variables**

   **Backend** (`/.env`):
   ```bash
   # Ensure API_KEY is set securely
   API_KEY=your-secure-api-key-here

   # Add CORS configuration for production
   ALLOWED_ORIGINS=https://your-frontend-domain.com
   ```

   **Frontend** (`/react_ui/.env.local`):
   ```bash
   # Remove NEXT_PUBLIC_API_KEY if present
   # API keys are now server-side only!

   # Set backend URL
   SERVER_MCP_BASE_URL=http://localhost:7002
   ```

2. **For AWS Deployments**

   If using AWS Secrets Manager:
   ```bash
   # Frontend still references the ARN, but it's accessed server-side only
   NEXT_PUBLIC_API_KEY=arn:aws:secretsmanager:region:account:secret:mcp-api-key
   ```

   The Next.js API routes will retrieve the secret server-side.

3. **Update Client Code**

   No client-side code should directly access API keys. All API calls should go through Next.js API routes:

   ```typescript
   // ❌ OLD - Direct backend calls with client-side API key
   const apiKey = await getApiKey();
   fetch('http://backend/api', {
     headers: { 'Authorization': `Bearer ${apiKey}` }
   });

   // ✅ NEW - Through Next.js API routes
   fetch('/api/v1/endpoint', {
     headers: { 'X-User-ID': userId }
   });
   ```

### 2. MCP Server Configuration Validation

**NEW FEATURE**: Strict input validation for MCP server parameters.

#### What Changed
- All MCP server configurations are validated
- Dangerous patterns blocked (command injection, path traversal)
- Whitelist of allowed commands
- Character restrictions on arguments and environment variables

#### Migration Steps

1. **Review Existing MCP Server Configurations**

   Check your `conf/` directory for any server configurations. Example:
   ```bash
   cd /path/to/your/deployment
   find conf/ -name "*.json" -exec cat {} \;
   ```

2. **Update Invalid Configurations**

   **Example of configurations that will NOW BE REJECTED:**

   ```json
   {
     "server_id": "test/../../../etc",  // ❌ Path traversal
     "command": "bash",                  // ❌ Not in whitelist
     "args": ["echo $SECRET; rm -rf /"], // ❌ Dangerous characters
     "env": {
       "PATH": "/malicious/bin"          // ❌ Dangerous env var
     }
   }
   ```

   **Example of valid configurations:**

   ```json
   {
     "server_id": "weather_api",         // ✅ Alphanumeric + hyphen
     "command": "npx",                   // ✅ In whitelist
     "args": ["mcp-server-weather"],     // ✅ Safe characters
     "env": {
       "WEATHER_API_KEY": "abc123"       // ✅ Safe env var
     }
   }
   ```

3. **Test MCP Server Addition**

   After migration, test adding a server:
   ```bash
   # This should succeed
   curl -X POST http://localhost:7002/v1/add/mcp_server \
     -H "Authorization: Bearer your-api-key" \
     -H "Content-Type: application/json" \
     -H "X-User-ID: testuser" \
     -d '{
       "server_id": "test_server",
       "command": "npx",
       "args": ["mcp-server-fetch"]
     }'

   # This should fail with validation error
   curl -X POST http://localhost:7002/v1/add/mcp_server \
     -H "Authorization: Bearer your-api-key" \
     -H "Content-Type: application/json" \
     -H "X-User-ID: testuser" \
     -d '{
       "server_id": "bad",
       "command": "python",
       "args": ["-c", "import os; os.system(\"ls\")"]
     }'
   ```

### 3. CORS Configuration

**BREAKING CHANGE**: CORS now requires explicit origin configuration.

#### What Changed
- No longer accepts requests from any origin (`*`)
- Must configure allowed origins explicitly
- Default: localhost only (development)

#### Migration Steps

1. **Development Environment**

   No changes needed. Defaults to:
   - `http://localhost:3000`
   - `http://localhost:3001`
   - `http://127.0.0.1:3000`
   - `http://127.0.0.1:3001`

2. **Production Environment**

   **REQUIRED**: Set `ALLOWED_ORIGINS` in your backend `.env`:

   ```bash
   # Single domain
   ALLOWED_ORIGINS=https://app.yourdomain.com

   # Multiple domains
   ALLOWED_ORIGINS=https://app.yourdomain.com,https://app2.yourdomain.com
   ```

3. **AWS ECS/Fargate Deployment**

   Update your task definition environment variables:
   ```json
   {
     "name": "ALLOWED_ORIGINS",
     "value": "https://your-cloudfront-domain.cloudfront.net"
   }
   ```

4. **Docker Deployment**

   Update `docker-compose.yml`:
   ```yaml
   environment:
     - ALLOWED_ORIGINS=https://your-domain.com
   ```

## Verification Steps

After migration, verify security controls:

### 1. Verify API Key Protection

```bash
# This should fail (endpoint removed)
curl http://localhost:3000/api/v1/auth/api-key

# Expected: 404 Not Found
```

### 2. Verify CORS Protection

```bash
# From unauthorized origin - should fail
curl -H "Origin: https://evil.com" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS http://localhost:7002/v1/add/mcp_server

# Expected: CORS error or no Access-Control-Allow-Origin header
```

### 3. Verify Input Validation

```bash
# Attempt command injection - should fail
curl -X POST http://localhost:7002/v1/add/mcp_server \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: testuser" \
  -d '{
    "server_id": "test",
    "command": "python",
    "args": ["-c", "print(1); import os; os.system(\"id\")"]
  }'

# Expected: 400 Bad Request with "Security validation failed" message
```

## Rollback Procedure

If you need to rollback (NOT RECOMMENDED for security reasons):

1. **Restore Previous Version**
   ```bash
   git checkout <previous-commit>
   ```

2. **Restore Environment Files**
   ```bash
   cp .env.backup .env
   cp react_ui/.env.local.backup react_ui/.env.local
   ```

3. **Restart Services**
   ```bash
   bash stop_all.sh
   bash start_all.sh
   ```

**WARNING**: Rolling back will reintroduce critical security vulnerabilities. Only do this temporarily while planning proper migration.

## Troubleshooting

### Issue: Frontend cannot connect to backend

**Symptoms**: CORS errors in browser console

**Solution**:
1. Check `ALLOWED_ORIGINS` in backend `.env`
2. Ensure it includes your frontend URL exactly
3. Include protocol (http/https) and port if not standard
4. Restart backend after changes

### Issue: MCP server addition fails

**Symptoms**: "Security validation failed" errors

**Solution**:
1. Review validation rules in `src/security.py`
2. Check server configuration for:
   - Dangerous characters (`;`, `|`, `&`, etc.)
   - Path traversal patterns (`../`, `~/`)
   - Disallowed commands
   - Dangerous environment variables
3. Update configuration to comply with validation rules

### Issue: "API key not configured" errors

**Symptoms**: 500 errors when accessing backend through frontend

**Solution**:
1. Ensure `API_KEY` is set in backend `.env`
2. For AWS Secrets Manager:
   - Verify secret exists
   - Check IAM permissions
   - Verify ARN is correct in `NEXT_PUBLIC_API_KEY`
3. Restart both frontend and backend

### Issue: Existing MCP servers not loading

**Symptoms**: Servers configured before migration not connecting

**Solution**:
1. Servers in DynamoDB are validated on reconnection
2. Check logs for validation errors:
   ```bash
   tail -f logs/app.log | grep "Security validation failed"
   ```
3. Update stored configurations to comply with new validation rules
4. Or remove and re-add servers through API

## Getting Help

If you encounter issues during migration:

1. Check logs:
   ```bash
   # Backend logs
   tail -f logs/app.log

   # Frontend logs (if using PM2)
   pm2 logs mcp-ui
   ```

2. Review security documentation:
   - `SECURITY.md` - Complete security guide
   - `src/security.py` - Validation rules

3. Test individual components:
   - Backend health: `curl http://localhost:7002/health`
   - Frontend health: `curl http://localhost:3000/api/health`

## Timeline

Recommended migration timeline:

- **Day 1**: Review this guide and test in development
- **Day 2-3**: Update configurations and test thoroughly
- **Day 4**: Deploy to staging environment
- **Day 5**: Monitor staging, fix any issues
- **Day 6**: Deploy to production during low-traffic period
- **Day 7+**: Monitor production, verify security controls

## Post-Migration

After successful migration:

1. **Update documentation** with new security practices
2. **Train team** on new authentication flow
3. **Set up monitoring** for security events
4. **Schedule regular security audits**
5. **Update incident response procedures**

## Questions?

For questions or concerns about this migration:

1. Review `SECURITY.md` for detailed security information
2. Check GitHub issues for similar problems
3. Contact the security team if you discover vulnerabilities
