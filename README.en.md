# Agentic AI with Bedrock AgentCore and Strands Agents SDK

[English](./README.en.md)

## 1. Overview

This comprehensive Agentic AI application built with Strands Agents SDK demonstrates how to integrate AgentCore Memory, Identity, Code Interpreter, Browser, and MCP/Gateway on the AgentCore Runtime. It implements a versatile personal assistant in both standalone Agent and Swarm modes. Bedrock AgentCore serves as the core engine, providing powerful Agent capabilities and tool integration mechanisms that make the entire system highly extensible and practical.

### 1.1. System Architecture
![system](assets/agentcore_arc.png)

The application consists of a web frontend and backend services, both containerized and deployed to Amazon ECS Fargate with external access provided through an Application Load Balancer (ALB). The backend services support web client operations such as user session creation, model selection, MCP tool selection, and system prompt configuration. These services receive requests from the web client and forward tasks to the Agent Runtime, where Agents determine whether to invoke browsers, code interpreters, MCP tools running on MCP Runtime, or additional MCP tools exposed through Gateway based on user requirements.

### 1.2 Key Features
- **Decoupled Frontend and Backend** - Both MCP Client and Server can be deployed server-side, allowing users to interact directly through web browsers to access LLM and MCP Server capabilities and resources
- **AgentCore Core Capabilities** - Integration with Runtime, Gateway, Memory, Browser, Code Interpreter, Identity, and Observation
- **Authentication** - AWS Cognito User Pool service for unified user registration, authentication, authorization, and secure access to MCP runtime and Gateway
- **React UI** - React-based user interface for model interaction, MCP server management, and display of tool invocation results and reasoning processes
- **Multiple Model Providers** - Support for Bedrock, OpenAI, and compatible models
- **Multi-user Session Management** - Maintenance of multiple user sessions
- **Strands Agents SDK** - Support for single-agent and Swarm multi-agent deep research modes

### 1.3 Core Module Descriptions

#### Agent Runtime
1. Runs Strands Agents, using default IAM for inbound authentication through backend services
2. Uses AgentCore memory for both short and long-term memory storage
3. Includes two Python tools for direct access to AgentCore's browser and code interpreter
4. Supports custom MCP server installation within the runtime
5. Can connect to MCP runtime or Gateway

#### MCP Runtime
1. Customizable implementation or adaptation of local code into MCP runtime
2. OAuth-based inbound authentication using Cognito UserPool
3. Outbound authentication via OAuth or API Key Credential Provider (e.g., OAuth for Google Calendar, API Key for EXA search)

#### Gateway
1. Implementation of Lambda functions as gateway targets
2. OpenAPI/Smithy description documents for API-based gateway targets
3. OAuth-based inbound authentication using Cognito UserPool
4. IAM-based outbound authentication for Lambda targets
5. API Key Credential Provider for API-based targets

### Memory
1. Strands Agent SDK hook functions to monitor AfterInvocationEvent for storing conversation messages as short-term memories
2. Strands Agent SDK hook functions to monitor AgentInitializedEvent for restoring short-term memories when creating Agents
3. Long-term memory retrieval implemented as an Agent tool, allowing Agents to autonomously decide when to access long-term memories

### Browser
1. Browser runtime CDP protocol passed to browser agent as a tool

### Identity
Unified identity provider through Cognito UserPool using the same pool and client ID for:
1. Web frontend user authentication
2. Gateway and MCP runtime OAuth authentication

## 2. Installation (Requires Arm64 Linux architecture, e.g., Mac or Graviton EC2)
### 2.1. Dependencies

Most MCP Servers are developed using NodeJS or Python and run on users' PCs, requiring these dependencies.

### 2.1 NodeJS

Download and install NodeJS from [nodejs.org](https://nodejs.org/en). This project has been thoroughly tested with version `v22.12.0`.

### 2.2 Python

Some MCP Servers are Python-based, requiring [Python installation](https://www.python.org/downloads/). This project's code is also Python-based.

First, install the Python package management tool `uv` by following the [official guide](https://docs.astral.sh/uv/getting-started/installation/).

### 2.3 Docker (Optional)
- Install Docker and Docker Compose: https://docs.docker.com/get-docker/
- Linux Docker installation commands:
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.6/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
ln -s /usr/bin/docker-compose  /usr/local/bin/docker-compose
```

### 2.4 Creating Cognito Resources
After cloning the project, navigate to the `agentcore_scripts/` directory and run the setup script to create IAM roles, Cognito UserPool, and AgentCore memory:
```bash
cd agentcore_scripts/
bash run_setup.sh
```

The script will generate three new files in the `agentcore_scripts/` directory:

From `.env_cognito`, extract the following configurations needed for `.env`:
```
pool_id=us-west-xxx
app_client_id=xxxxxx
m2m_client_id=
m2m_client_secret=
scope_string=
discovery_url=
```

From `iam-role.txt`, find the role ARN for AgentCore runtime creation:
```
Role ARN: arn:aws:iam::xxxx:role/agentcore-strands_agent_role-role
```

From `memory.txt`, find the memory ID for AgentCore runtime creation:
```
✅ Created memory: {memory_id}
```

### 2.5 Creating AgentCore Runtime Configuration
1. Create a Python virtual environment and install dependencies:
```bash
cd ./sample_agentic_ai_strands
uv sync
```

2. Create an ECR repository:
```bash
aws ecr create-repository \
    --repository-name bedrock_agentcore-agent_runtime \
    --region us-west-2
```

3. Copy the template configuration file:
```bash
cp bedrock_agentcore_template.yaml .bedrock_agentcore.yaml
```
Update account, region, ECR repository information, and execution role. Use role information from `iam-role.txt`.

4. Create a DynamoDB table named `agent_user_config_table`:
```bash
aws dynamodb create-table \
    --table-name agent_user_config_table \
    --attribute-definitions AttributeName=userId,AttributeType=S \
    --key-schema AttributeName=userId,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST 
```

### 2.6 Environment Variables
Copy the example environment file and edit as needed:
```bash
cp env.example .env
```

Edit the `.env` file using vim:
⚠️ Note: The `COGNITO_M2M_CLIENT_SCOPE` variable contains spaces and requires double quotes
```bash
# =============================================================================
# COGNITO AUTHENTICATION CONFIGURATION
# AWS Cognito UserPool configuration for JWT token authentication
# =============================================================================
COGNITO_USER_POOL_ID=<pool_id>
COGNITO_CLIENT_ID=<app_client_id>
COGNITO_M2M_CLIENT_ID=<m2m_client_id>
COGNITO_M2M_CLIENT_SECRET=<m2m_client_secret>
COGNITO_M2M_CLIENT_SCOPE="<scope_string>"
# =============================================================================
# AWS Infra CONFIGURATION
# The default ECS platform is amd64, you can choose linux/amd64 or linux/arm64
# =============================================================================
PLATFORM=linux/arm64
AWS_REGION=us-west-2
# =============================================================================
# AGENTCORE CONFIGURATION
# =============================================================================
AGENTCORE_REGION=us-west-2
MEMORY_ID=<your_agentcore_memory_id>
```

### 2.7 Deploying AgentCore Runtime
Launch the AgentCore runtime using the CLI (requires ARM environment):
```bash
agentcore launch
```

After successful deployment, note the `Agent ARN` from the console output and add it to your `.env` file:
```bash
AGENTCORE_RUNTIME_ARN=<your_agentcore_runtime_arn>
```

## 3. Deploying Frontend and Backend to ECS
(Production mode, AWS ECS deployment)
Please refer to the [CDK Deployment Guide](cdk/README-CDK.md)
![img](assets/ecs_fargate_architecture.png)

This demo follows AWS best practices by deploying applications in private subnets with public access through load balancers and serverless container management via Fargate. The architecture includes:

1. ECS Cluster:
   - Serverless container environment running on Fargate using ARM architecture
   - Frontend service: Minimum 2 tasks, auto-scaling based on CPU usage
   - Backend service: Minimum 2 tasks, auto-scaling based on CPU usage

2. VPC:
   - Public and private subnets across two availability zones
   - Internet Gateway and NAT Gateway in public subnets
   - Private subnets for ECS tasks

3. Application Load Balancer:
   - Routes `/v1/*` and `/api/*` paths to backend services
   - Routes other requests to frontend services

4. Data Storage:
   - DynamoDB tables for user configuration storage

5. Security Components:
   - IAM roles and policies for access control
   - Secrets Manager for backend service API key configuration
   - Security groups for network traffic control

6. Container Images:
   - Frontend and backend container images stored in ECR

## 4. Running AgentCore Locally
Launch AgentCore locally with an 8080 service using:
```bash
uv run src/agentcore_runtime.py
```

Test with Postman or similar tools:
Request URL: `http://127.0.0.1:8080/invocations`
Payload example:
```json
{
        "user_id":"a8d153a0-4091-70ee-58ae-b2bd2fa731e6",
        "request_type":"chatcompletion",
        "data" :{
                "model": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                "mcp_server_ids": [],
                "extra_params":{"use_mem":false,"use_swarm":false,"use_code_interpreter":false,"use_browser":false},
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "The impact of AI on software development"
                            }
                        ]
                    }
                ]
            }
    }
```

## 5. Example
### Using Swarm Mode for Deep Research
- Install AWS Knowledge MCP server:
![alt text](assets/add_mcp2.png)

```json
{
    "mcpServers": {
        "aws-knowledge": {
            "url": "https://knowledge-mcp.global.api.aws"
        }
    }
}
```
- Select `Claude 4 Sonnet` or `Claude 3.7 Sonnet` model, adjust `Max Tokens: 30600`

- Enable Swarm mode to deploy a multi-agent team for deep research:
```python
{
    "research_coordinator": research_coordinator,
    "academic_researcher": academic_researcher,
    "industry_analyst": industry_analyst,
    "technical_specialist": technical_specialist,
    "data_analyst": data_analyst,
    "synthesis_writer": synthesis_writer,
    "fact_checker": fact_checker
}
```

- Input: `帮我写一份关于amazon bedrock agentcore的研究报告，使用中文`
![alt text](assets/swarm_deepresearch.png)

## 6. Additional Examples
- [Case Studies](./README_cases.md)