# AWS CDK Deployment Guide

A comprehensive guide for deploying MCP applications to ECS Fargate using AWS CDK (Cloud Development Kit).

## CDK Architecture Overview
![img](../assets/ecs_fargate_architecture.png)
This demonstration deployment architecture adheres to AWS best practices, deploying applications within private subnets, providing public access through load balancers, and utilizing Fargate for serverless container management. The deployment architecture encompasses the following principal Amazon Cloud components:

1. ECS Cluster:
   • Serverless container environment running on Fargate, utilizing ARM architecture
   • Frontend service: Minimum of 2 tasks, auto-scaling based on CPU utilization
   • Backend service: Minimum of 2 tasks, auto-scaling based on CPU utilization

2. VPC:
   • Comprises both public and private subnets spanning 2 availability zones
   • Internet Gateway and NAT Gateway situated within public subnets
   • Private subnets designated for ECS task execution

3. Application Load Balancer:
   • Application Load Balancer (ALB) distributes traffic
   • Routes requests with /v1/* and /api/* paths to backend services
   • Directs all other requests to frontend services

4. Data Storage:
   • DynamoDB tables for user configuration storage

5. Security Components:
   • IAM roles and policies governing access permissions
   • An Amazon Cognito user pool handles user sign-in (administrators create users)
   • Security groups controlling network traffic

6. Container Images:
   • Frontend and backend container images stored in ECR

### Network Architecture
- **VPC**: 10.0.0.0/16 spanning 2 availability zones
- **Public Subnets**: 10.0.1.0/24, 10.0.2.0/24 (ALB)
- **Private Subnets**: 10.0.3.0/24, 10.0.4.0/24 (ECS containers)
- **NAT Gateway**: Provides internet access for private subnets
- **Internet Gateway**: Public network access

### Compute and Storage
- **ECS Fargate Cluster**: ARM64 architecture container runtime
- **DynamoDB Table**: User configuration storage (pay-per-request)
- **ECR Repository**: Frontend and backend Docker image storage

### Security and Configuration
- **Amazon Cognito**: User pool and web app client; the backend verifies the access token on every request
- **Secrets Manager**: Securely stores model and credential configurations
- **IAM Roles**: Principle of least privilege
- **Security Groups**: Network access control

### Load Balancing and Monitoring
- **Application Load Balancer**: HTTP/HTTPS traffic distribution
- **CloudWatch Logs**: Application log collection
- **Auto Scaling**: CPU utilization-based automatic scaling

## Quick Start

### Environment Requirements

1. **Node.js** (version 18+)
2. **AWS CLI** configured
3. **Docker** with buildx support (multi-architecture builds)
4. **AWS CDK** CLI tools

```bash
# Install CDK CLI
npm install -g aws-cdk
npm install -g typescript
npm install
npm i --save-dev @types/node

# Verify installation
cdk --version
```

#### Docker mirror configuration for China regions
Use `sudo vim /etc/docker/daemon.json` to add proxy:
```json
{
"registry-mirrors":["https://mirror-docker.bosicloud.com"],
"insecure-registries":["mirror-docker.bosicloud.com"]
}
```

## Detailed Deployment Steps
### Step 1: Configure AWS credentials
```bash
aws configure
```

### Step 1: Prepare Environment

Ensure the `.env` file contains all necessary configurations:

```bash
# For Bedrock usage in Global Regions, configure as follows
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
STRANDS_MODEL_PROVIDER=bedrock

# For China regions using OpenAI-compatible interfaces, configure Strands as follows
OPENAI_API_KEY=your-model-provider-key
OPENAI_BASE_URL=your-model-provider-base-url(e.g., https://api.siliconflow.cn)
STRANDS_MODEL_PROVIDER=openai
AWS_REGION=cn-northwest-1(deployment region, use cn-north-1 for Beijing region)

# Langfuse Configuration (optional)
LANGFUSE_PUBLIC_KEY=your-public-key
LANGFUSE_SECRET_KEY=your-secret-key
LANGFUSE_HOST=https://your-langfuse-host

# Additional Configuration
CLIENT_TYPE=strands
MAX_TURNS=200
INACTIVE_TIME=1440
```

### Deployment Script
```bash
cd cdk
bash cdk-build-and-deploy.sh
```

### Step 4: Create Users
Self sign-up is disabled. After deployment, create users with the `CognitoUserPoolId` stack output; they set a new password at first sign-in:
```bash
aws cognito-idp admin-create-user --user-pool-id <CognitoUserPoolId> --username you@example.com
```
Cognito user pools are not available in China regions: before deploying, set `COGNITO_USER_POOL_ID` and `COGNITO_APP_CLIENT_ID` to an existing user pool in a global region and an app client without a client secret.

### Step 5: Update Services
```bash
bash update-ecs-services.sh
```

## CDK Command Reference

### Basic Commands

```bash
# View resources to be deployed
cdk diff

# Deploy Stack
cdk deploy

# Destroy Stack
cdk destroy

# List all Stacks
cdk list

# View Stack template
cdk synth
```

### Useful Options

```bash
# Skip confirmation
cdk deploy --require-approval never

# Specify Stack name
cdk deploy McpEcsFargateStack

# Set AWS profile
cdk deploy --profile your-profile

# Output template to file
cdk synth > template.yaml
```

### Multi-environment Deployment
Using CDK context variables:

```bash
# Deploy to different environments
cdk deploy --context env=staging
cdk deploy --context env=production
```

## Resource Cleanup

Complete removal of all created resources:

```bash
# Delete CDK Stack
cdk destroy

# Clean up ECR repositories
aws ecr delete-repository --repository-name mcp-app-frontend --force
aws ecr delete-repository --repository-name mcp-app-backend --force

# Delete CloudWatch log groups
aws logs delete-log-group --log-group-name "/ecs/mcp-app-frontend"
aws logs delete-log-group --log-group-name "/ecs/mcp-app-backend"
```

Note: Some resources (such as DynamoDB tables) may have deletion protection and require manual confirmation to delete.