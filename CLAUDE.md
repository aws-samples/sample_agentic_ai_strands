# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup and Installation

```bash
# Install Python dependencies
uv sync

# Set up environment variables
cp env.example .env
# Edit .env file with appropriate values
```

### Create Required Infrastructure

```bash
# Create DynamoDB table for user configuration
aws dynamodb create-table \
    --table-name mcp_user_config_table \
    --attribute-definitions AttributeName=userId,AttributeType=S \
    --key-schema AttributeName=userId,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST

# Run setup script to create IAM roles, Cognito UserPool, and AgentCore memory
cd agentcore_scripts/
bash run_setup.sh
```

### Running the Application

```bash
# Start the backend service
bash start_all.sh

# Stop all services
bash stop_all.sh
```

### Testing

```bash
# Test streaming chat API
bash tests/test_chat_api_stream.sh

# Test non-streaming chat API
bash tests/test_chat_api.sh

# Test MCP server addition
bash tests/test_add_mcp_api.sh
```

### Frontend Setup

#### Running in Development Mode

```bash
# Navigate to the React UI directory
cd react_ui

# Create environment variables for frontend
cp .env.example .env.local

# Install dependencies
npm install

# Start development server
npm run dev

# For HTTPS development mode
npm run dev:https
```

#### Docker Setup (Frontend)

```bash
# Navigate to the React UI directory
cd react_ui

# Create environment variables for frontend
cp .env.example .env.local

# Build and start frontend containers
docker-compose up -d --build
```

### Docker Commands

```bash
# View container logs
docker logs -f mcp-bedrock-ui

# Restart containers
docker-compose restart

# Stop containers
docker-compose down

# Rebuild and start (after code updates)
docker-compose up -d --build
```

### AgentCore Runtime Commands

```bash
# Launch AgentCore runtime (requires ARM environment)
uv run agentcore launch

# Run AgentCore runtime locally for testing (port 8080)
uv run src/agentcore_runtime.py
```

## Architecture Overview

This repository contains an Agentic AI application built using Strands Agents SDK that provides integration between large language models and external tool systems through the Model Context Protocol (MCP). The architecture follows a decoupled frontend and backend design, with a React UI for the frontend and a Python FastAPI server for the backend.

### Key Components of the Application

1. **Backend Service (`src/main.py`)**
   - FastAPI server that manages sessions, model interactions, and MCP server connections
   - Handles streaming responses from LLMs via Server-Sent Events (SSE)
   - Manages user sessions and MCP server configurations stored in DynamoDB
   - Two authentication modes: API_KEY for development (DEV_MODE=True), Cognito JWT for production
   - Endpoints: `/v1/chat/completions` (chat), `/v1/mcp/servers` (MCP management), `/health` (health check)

2. **Strands Agent Client (`src/strands_agent_client.py`, `src/strands_agent_client_stream.py`)**
   - Provides integration with various LLM providers (Bedrock, OpenAI)
   - Handles streaming responses and agent interactions
   - Manages tool invocations and results
   - Supports both single-agent mode and Swarm multi-agent mode for deep research

3. **MCP Client (`src/mcp_client_strands.py`)**
   - Implements the Model Context Protocol for tool integration
   - Manages connections to MCP servers
   - Handles tool registration and invocation

4. **AgentCore Wrapper (`src/agentcore_wrapper.py`)**
   - Invokes AgentCore runtime for request processing
   - Bridges between FastAPI endpoints and AgentCore services

5. **Frontend (React UI)**
   - Next.js 15 based web interface for interacting with the agent
   - Displays streaming responses and tool results with markdown rendering
   - Manages MCP server configurations
   - Features a resizable tool usage panel for viewing tool calls and results
   - Supports dark/light mode themes with Tailwind CSS and Shadcn UI
   - AWS Amplify integration for Cognito authentication

### React UI Components

1. **ChatInterface (`components/chat/ChatInterface.tsx`)**
   - Main chat interface with messaging and tool panel
   - Handles resizable sidebar for tool usage display
   - Manages user sessions and message history

2. **Server Management (`components/sidebar/`)**
   - Model selector for choosing LLM models
   - Server list for managing MCP servers
   - Add server dialog for configuring new MCP servers

3. **Tool Integration (`components/chat/ToolUsagePanel.tsx`)**
   - Displays tool calls and their results
   - Provides detailed view of tool usage in modal dialogs
   - Handles displaying images from tool results

### Data Flow

1. User queries are sent to the FastAPI backend (`/v1/chat/completions`)
2. Backend creates/retrieves user sessions and either:
   - Forwards requests directly to Strands agent for local development
   - Invokes AgentCore runtime via `agentcore_wrapper.py` for production
3. Agent processes queries and may invoke tools via MCP servers
4. Results are streamed back to the user through SSE (Server-Sent Events)

### AgentCore Architecture

The application integrates with AWS Bedrock AgentCore, providing:

1. **Agent Runtime** - Runs Strands Agents with IAM authentication, includes browser and code interpreter tools
2. **MCP Runtime** - Custom MCP server implementation with OAuth authentication via Cognito
3. **Gateway** - Lambda functions and API-based gateway targets with IAM/OAuth authentication
4. **Memory** - Short-term and long-term memory storage using AgentCore memory
5. **Browser** - Browser runtime CDP protocol for web automation
6. **Identity** - Unified identity via Cognito UserPool for web frontend and service authentication

### Deployment Options

1. **Development Mode**: Local deployment using `start_all.sh`
2. **Production Mode**: AWS ECS Fargate deployment using CDK (`cdk/cdk-build-and-deploy.sh`)

## Configuration

### Backend Configuration

The backend application can be configured through the `.env` file:

- **Model provider**: `STRANDS_MODEL_PROVIDER` (bedrock, openai)
- **AWS credentials**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- **Bedrock-specific credentials**: `BEDROCK_AWS_ACCESS_KEY_ID`, `BEDROCK_AWS_SECRET_ACCESS_KEY`, `BEDROCK_AWS_REGION`
- **OpenAI settings**: `OPENAI_API_KEY`, `OPENAI_BASE_URL`
- **Server settings**: `MCP_SERVICE_HOST`, `MCP_SERVICE_PORT`, `USE_HTTPS`
- **Authentication**: `API_KEY` (dev mode), Cognito settings for production
- **AgentCore**: `AGENTCORE_RUNTIME_ARN`, `MEMORY_ID`, `AGENTCORE_REGION`
- **Session management**: `INACTIVE_TIME` (session timeout in minutes)
- **Observation**: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`
- **Memory**: `ENABLE_MEM0` (enable/disable mem0 features)

See `env.example` for all available configuration options.

### Frontend Configuration

The React UI can be configured through the `.env.local` file in the `react_ui` directory:

- API endpoint configuration
- Server MCP base URL
- API Key for authentication

The UI components are built with:
- Next.js 15 and React 18
- Tailwind CSS for styling
- Shadcn UI component library
- Radix UI primitives
- AWS Amplify for Cognito authentication

## CDK Deployment

### Prerequisites

- Node.js 18+
- AWS CLI configured
- Docker with buildx support (for multi-architecture builds)
- AWS CDK CLI tools

### Quick Deployment

```bash
cd cdk
# Install dependencies (first time only)
npm install -g aws-cdk typescript
npm install
npm i --save-dev @types/node

# Bootstrap CDK (first time only)
npx cdk bootstrap

# Deploy entire stack
./cdk-build-and-deploy.sh
```

The deployment script will:
1. Create ECR repositories for frontend and backend
2. Build and push Docker images (supports ARM64 and AMD64)
3. Update Secrets Manager with credentials from `.env`
4. Deploy ECS Fargate stack with VPC, ALB, services
5. Output ALB DNS name for accessing the application

### CDK Architecture

- **VPC**: 10.0.0.0/16 spanning 2 availability zones with public and private subnets
- **ECS Fargate**: Serverless container runtime with ARM64/AMD64 support
- **Application Load Balancer**: Routes `/v1/*` and `/api/*` to backend, others to frontend
- **DynamoDB**: User configuration storage (pay-per-request)
- **Secrets Manager**: Stores AWS credentials, API keys, and configuration
- **Auto Scaling**: CPU-based scaling for frontend and backend services (minimum 2 tasks each)

### Update Deployed Services

```bash
cd cdk
# Update ECS services with new images
bash update-ecs-services.sh

# Update secrets in Secrets Manager
bash update-secrets.sh
```

## Important Files

- `pyproject.toml` - Python dependencies (requires Python 3.12)
- `env.example` - Environment variable template
- `conf/config.json` - Global MCP server configuration
- `conf/user_mcp_config.json` - User-specific MCP server configuration
- `.bedrock_agentcore.yaml` - AgentCore configuration (generated by setup script)
- `agentcore_scripts/.env_setup` - Generated setup configuration with ECR, Cognito, Memory details
