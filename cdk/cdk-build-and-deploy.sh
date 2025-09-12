#!/bin/bash

set -e

# Complete CDK build and deployment script
echo "Starting complete CDK build and deployment process..."

# Check if .env file exists
if [ ! -f "../.env" ]; then
    echo "Error: .env file does not exist, please create .env file first"
    exit 1
fi

# Read .env file
set -a
source ../.env
set +a
export NODE_ENV=production
# Configuration variables
REGION="${AWS_REGION:-cn-northwest-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
PREFIX="strands-agentcore"
PLATFORM="${PLATFORM:-linux/arm64}"
# Mem0 configuration - read from environment variables, enabled by default
ENABLE_MEM0="${ENABLE_MEM0:-true}"
export CDK_DEFAULT_REGION=$REGION
export CDK_DEFAULT_ACCOUNT=$ACCOUNT_ID
export ENABLE_MEM0=$ENABLE_MEM0
# Detect if it's China region
if [[ $REGION == cn-* ]]; then
    IS_CHINA_REGION=true
    ECR_DOMAIN="amazonaws.com.cn"
    CONSOLE_DOMAIN="console.amazonaws.cn"
    echo "Detected China region: $REGION"
else
    IS_CHINA_REGION=false
    ECR_DOMAIN="amazonaws.com"
    CONSOLE_DOMAIN="console.aws.amazon.com"
    echo "Detected global region: $REGION"
fi

echo "Using AWS Account: $ACCOUNT_ID"
echo "Using Region: $REGION"
echo "PLATFORM: $PLATFORM"
echo "ECR Domain: $ECR_DOMAIN"
echo "Mem0 Feature: $ENABLE_MEM0"

# 1. Create or get ECR repositories
echo "========================================="
echo "Step 1: Create ECR repositories"
echo "========================================="

# Create frontend ECR repository
echo "Creating frontend ECR repository..."
aws ecr create-repository \
    --repository-name ${PREFIX}-frontend \
    --region $REGION 2>/dev/null || echo "Frontend ECR repository already exists"

# Create backend ECR repository
echo "Creating backend ECR repository..."
aws ecr create-repository \
    --repository-name ${PREFIX}-backend \
    --region $REGION 2>/dev/null || echo "Backend ECR repository already exists"

# Get ECR repository URIs
FRONTEND_ECR="$ACCOUNT_ID.dkr.ecr.$REGION.$ECR_DOMAIN/${PREFIX}-frontend"
BACKEND_ECR="$ACCOUNT_ID.dkr.ecr.$REGION.$ECR_DOMAIN/${PREFIX}-backend"

echo "ECR repositories ready:"
echo "- Frontend ECR: $FRONTEND_ECR"
echo "- Backend ECR: $BACKEND_ECR"

# 2. Build and push Docker images
echo "========================================="
echo "Step 2: Build and push Docker images"
echo "========================================="

# Login to ECR
echo "Logging into ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.$ECR_DOMAIN

# Detect current system architecture
CURRENT_ARCH=$(uname -m)
echo "Current system architecture: $CURRENT_ARCH"
echo "Target platform: $PLATFORM"

# Determine if buildx is needed
USE_BUILDX=true
case "$CURRENT_ARCH" in
    "x86_64"|"amd64")
        if [[ "$PLATFORM" == "linux/amd64" || "$PLATFORM" == "linux/x86" ]]; then
            USE_BUILDX=false
            echo "✅ Current architecture matches target platform, using native docker build"
        fi
        ;;
    "aarch64"|"arm64")
        if [[ "$PLATFORM" == "linux/arm64" ]]; then
            USE_BUILDX=false
            echo "✅ Current architecture matches target platform, using native docker build"
        fi
        ;;
esac

if [[ "$USE_BUILDX" == true ]]; then
    echo "⚠️ Current architecture doesn't match target platform, using docker buildx"
    BUILDER_NAME="mybuilder"
    echo "Checking if Docker buildx builder '$BUILDER_NAME' already exists..."
    # Check if the builder exists
    if docker buildx ls | grep -q "$BUILDER_NAME"; then
        echo "Builder '$BUILDER_NAME' exists. Skip it..."
    else
        echo "Creating new builder '$BUILDER_NAME'..."
        docker buildx create --name "$BUILDER_NAME" --platform "$PLATFORM" --use
    fi
fi

# Build frontend image
echo "Building frontend image..."
cd ../react_ui
# cp .env.example .env.local

if [[ "$USE_BUILDX" == true ]]; then
    # Use buildx for cross-architecture build
    if [[ $IS_CHINA_REGION == true ]]; then
        echo "Building frontend image with China mirror (buildx)..."
        docker buildx build --platform "$PLATFORM" \
            --build-arg USE_CHINA_MIRROR=true \
            --build-arg PLATFORM="$PLATFORM" \
            --build-arg COGNITO_USER_POOL_ID="${COGNITO_USER_POOL_ID}" \
            --build-arg COGNITO_CLIENT_ID="${COGNITO_CLIENT_ID}" \
            --build-arg AWS_REGION="${AWS_REGION}" \
            --load -t ${PREFIX}-frontend:latest .
    else
        echo "Building frontend image (buildx)..."
        docker buildx build --platform "$PLATFORM" \
            --build-arg PLATFORM="$PLATFORM" \
            --build-arg COGNITO_USER_POOL_ID="${COGNITO_USER_POOL_ID}" \
            --build-arg COGNITO_CLIENT_ID="${COGNITO_CLIENT_ID}" \
            --build-arg AWS_REGION="${AWS_REGION}" \
            --load -t ${PREFIX}-frontend:latest .
    fi
else
    # Use native docker build
    if [[ $IS_CHINA_REGION == true ]]; then
        echo "Building frontend image with China mirror (native)..."
        docker build --build-arg USE_CHINA_MIRROR=true \
            --build-arg PLATFORM="$PLATFORM" \
            --build-arg COGNITO_USER_POOL_ID="${COGNITO_USER_POOL_ID}" \
            --build-arg COGNITO_CLIENT_ID="${COGNITO_CLIENT_ID}" \
            --build-arg AWS_REGION="${AWS_REGION}" \
            -t ${PREFIX}-frontend:latest .
    else
        echo "Building frontend image (native)..."
        docker build --build-arg PLATFORM="$PLATFORM" \
            --build-arg COGNITO_USER_POOL_ID="${COGNITO_USER_POOL_ID}" \
            --build-arg COGNITO_CLIENT_ID="${COGNITO_CLIENT_ID}" \
            --build-arg AWS_REGION="${AWS_REGION}" \
            -t ${PREFIX}-frontend:latest .
    fi
fi

docker tag ${PREFIX}-frontend:latest $FRONTEND_ECR:latest
docker push $FRONTEND_ECR:latest
cd ..

echo "Frontend image push completed: $FRONTEND_ECR:latest"

# Build backend image
echo "Building backend image..."

if [[ "$USE_BUILDX" == true ]]; then
    # Use buildx for cross-architecture build
    if [[ $IS_CHINA_REGION == true ]]; then
        echo "Building backend image with China mirror (buildx)..."
        docker buildx build --platform "$PLATFORM" \
            --build-arg USE_CHINA_MIRROR=true \
            --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
            --build-arg PLATFORM="$PLATFORM" \
            --build-arg AWS_REGION="${AWS_REGION}" \
            --build-arg AWS_DEFAULT_REGION="${AWS_REGION}" \
            --load -t ${PREFIX}-backend:latest -f Dockerfile.backend .
    else
        echo "Building backend image (buildx)..."
        docker buildx build --platform "$PLATFORM" \
            --build-arg PLATFORM="$PLATFORM" \
            --build-arg AWS_REGION="${AWS_REGION}" \
            --build-arg AWS_DEFAULT_REGION="${AWS_REGION}" \
            --load -t ${PREFIX}-backend:latest -f Dockerfile.backend .
    fi
else
    # Use native docker build
    if [[ $IS_CHINA_REGION == true ]]; then
        echo "Building backend image with China mirror (native)..."
        docker build --build-arg USE_CHINA_MIRROR=true \
            --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
            --build-arg PLATFORM="$PLATFORM" \
            --build-arg AWS_REGION="${AWS_REGION}" \
            --build-arg AWS_DEFAULT_REGION="${AWS_REGION}" \
            -t ${PREFIX}-backend:latest -f Dockerfile.backend .
    else
        echo "Building backend image (native)..."
        docker build --build-arg PLATFORM="$PLATFORM" \
            --build-arg AWS_REGION="${AWS_REGION}" \
            --build-arg AWS_DEFAULT_REGION="${AWS_REGION}" \
            -t ${PREFIX}-backend:latest -f Dockerfile.backend .
    fi
fi

docker tag ${PREFIX}-backend:latest $BACKEND_ECR:latest
docker push $BACKEND_ECR:latest

echo "Backend image push completed: $BACKEND_ECR:latest"

# 3. Prepare CDK environment
echo "========================================="
echo "Step 3: Prepare CDK environment"
echo "========================================="

cd cdk

# Install dependencies
echo "Installing CDK dependencies..."
# npm install -g typescript
# npm install
# npm i --save-dev @types/node
# Build TypeScript
echo "Building TypeScript..."
npm run build

# Bootstrap CDK (if needed)
echo "Checking CDK Bootstrap..."
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region $REGION &>/dev/null; then
    echo "Bootstrapping CDK environment..."
    npx cdk bootstrap --region $REGION
else
    echo "CDK already bootstrapped"
fi

cd ..

# 4. Update Secrets Manager
echo "========================================="
echo "Step 4: Update Secrets Manager configuration"
echo "========================================="

echo "Updating Secrets Manager from .env file..."

# Create or update AWS credentials
if [ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "Using AWS credentials from environment variables"
    aws secretsmanager create-secret \
        --name "${PREFIX}/aws-credentials" \
        --description "AWS Access Credentials" \
        --secret-string "{\"AccessKeyId\":\"${AWS_ACCESS_KEY_ID}\",\"SecretAccessKey\":\"${AWS_SECRET_ACCESS_KEY}\"}" \
        --region $REGION 2>/dev/null || \
    aws secretsmanager update-secret \
        --secret-id "${PREFIX}/aws-credentials" \
        --secret-string "{\"AccessKeyId\":\"${AWS_ACCESS_KEY_ID}\",\"SecretAccessKey\":\"${AWS_SECRET_ACCESS_KEY}\"}" \
        --region $REGION
fi
# Create or update Bedrock AWS credentials
# Create or update AWS credentials
if [ -n "$BEDROCK_AWS_ACCESS_KEY_ID" ] && [ -n "$BEDROCK_AWS_SECRET_ACCESS_KEY" ]; then
    aws secretsmanager create-secret \
        --name "${PREFIX}/bedrock-aws-credentials" \
        --description "Bedrock AWS Access Credentials" \
        --secret-string "{\"AccessKeyId\":\"${BEDROCK_AWS_ACCESS_KEY_ID}\",\"SecretAccessKey\":\"${BEDROCK_AWS_SECRET_ACCESS_KEY}\"}" \
        --region $REGION 2>/dev/null || \
    aws secretsmanager update-secret \
        --secret-id "${PREFIX}/bedrock-aws-credentials" \
        --secret-string "{\"AccessKeyId\":\"${BEDROCK_AWS_ACCESS_KEY_ID}\",\"SecretAccessKey\":\"${BEDROCK_AWS_SECRET_ACCESS_KEY}\"}" \
        --region $REGION
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️ OPENAI_API_KEY not set or empty"
    # Create or update OpenAI compatible API Key
    aws secretsmanager create-secret \
        --name "${PREFIX}/strands-api-key" \
        --description "Strands API Key" \
        --secret-string "dummy" \
        --region $REGION 2>/dev/null || \
    aws secretsmanager update-secret \
        --secret-id "${PREFIX}/strands-api-key" \
        --secret-string "dummy" \
        --region $REGION
else
    # Create or update OpenAI compatible API Key
    aws secretsmanager create-secret \
        --name "${PREFIX}/strands-api-key" \
        --description "Strands API Key" \
        --secret-string "${OPENAI_API_KEY}" \
        --region $REGION 2>/dev/null || \
    aws secretsmanager update-secret \
        --secret-id "${PREFIX}/strands-api-key" \
        --secret-string "${OPENAI_API_KEY}" \
        --region $REGION
fi

if [ -z "$OPENAI_BASE_URL" ]; then
    echo "⚠️ OPENAI_BASE_URL not set or empty"
    # Create or update OpenAI compatible API Base
    aws secretsmanager create-secret \
        --name "${PREFIX}/strands-api-base" \
        --description "Strands API Base URL" \
        --secret-string "dummy" \
        --region $REGION 2>/dev/null || \
    aws secretsmanager update-secret \
        --secret-id "${PREFIX}/strands-api-base" \
        --secret-string "dummy" \
        --region $REGION
else
    # Create or update OpenAI compatible API Base
    aws secretsmanager create-secret \
        --name "${PREFIX}/strands-api-base" \
        --description "Strands API Base URL" \
        --secret-string "${OPENAI_BASE_URL}" \
        --region $REGION 2>/dev/null || \
    aws secretsmanager update-secret \
        --secret-id "${PREFIX}/strands-api-base" \
        --secret-string "${OPENAI_BASE_URL}" \
        --region $REGION
fi

echo "Secrets Manager configuration completed"

# 5. Deploy CDK Stack (images are now ready)
echo "========================================="
echo "Step 5: Deploy CDK Stack"
echo "========================================="

cd cdk
echo "Deploying CDK Stack (images are ready)..."
echo "Mem0 feature setting: $ENABLE_MEM0"
export AWS_ACCOUNT_ID=$ACCOUNT_ID
export AWS_REGION=$REGION
export ENABLE_MEM0=$ENABLE_MEM0
npx cdk deploy --require-approval never --region $REGION --context enableMem0=$ENABLE_MEM0 --context namePrefix=$PREFIX

# 获取输出
STACK_NAME="StrandsAgentsEcsFargateStack"

# Wait for Stack deployment to complete
echo "Waiting for Stack deployment to complete..."
aws cloudformation wait stack-create-complete --stack-name $STACK_NAME --region $REGION 2>/dev/null || \
aws cloudformation wait stack-update-complete --stack-name $STACK_NAME --region $REGION 2>/dev/null || true

# Get deployment outputs
ALB_DNS=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`AlbDnsName`].OutputValue' \
    --output text)

CLUSTER_NAME=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`ClusterName`].OutputValue' \
    --output text)

cd ..

echo "CDK Stack deployment completed:"
echo "- ALB DNS: $ALB_DNS"
echo "- Cluster Name: $CLUSTER_NAME"
SERVICES=$(aws ecs list-services --cluster $CLUSTER_NAME --region $REGION --query 'serviceArns[*]' --output text)
# Parse service names
FRONTEND_SERVICE=""
BACKEND_SERVICE=""

for service_arn in $SERVICES; do
    service_name=$(basename $service_arn)
    echo "Found service: $service_name"
    
    if [[ $service_name == *"frontend"* ]]; then
        FRONTEND_SERVICE=$service_name
    elif [[ $service_name == *"backend"* ]]; then
        BACKEND_SERVICE=$service_name
    fi
done

# 6. Wait for services to stabilize
echo "========================================="
echo "Step 6: Wait for service updates to complete"
echo "========================================="
echo "Frontend service: $FRONTEND_SERVICE"
echo "Backend service: $BACKEND_SERVICE"
echo "Waiting for frontend service to stabilize..."
aws ecs wait services-stable \
    --cluster $CLUSTER_NAME \
    --services $FRONTEND_SERVICE \
    --region $REGION &

echo "Waiting for backend service to stabilize..."
aws ecs wait services-stable \
    --cluster $CLUSTER_NAME \
    --services $BACKEND_SERVICE \
    --region $REGION &

# Wait for both services to complete
wait

# 7. Deployment completed
echo "========================================="
echo "Deployment completed!"
echo "========================================="

# Save output information
cat > cdk-outputs.env << EOF
ALB_DNS=$ALB_DNS
FRONTEND_ECR=$FRONTEND_ECR
BACKEND_ECR=$BACKEND_ECR
CLUSTER_NAME=$CLUSTER_NAME
STACK_NAME=$STACK_NAME
REGION=$REGION
ACCOUNT_ID=$ACCOUNT_ID
EOF

echo "Deployment information:"
# echo "- ALB DNS: $ALB_DNS"
# echo "- Frontend access URL: http://$ALB_DNS"
# echo "- Backend API URL: http://$ALB_DNS/api"
echo "- ECS Cluster: $CLUSTER_NAME"
echo ""
echo "Monitoring links:"
echo "- ECS Console: https://$REGION.$CONSOLE_DOMAIN/ecs/home?region=$REGION#/clusters/$CLUSTER_NAME"
echo "- CloudWatch Logs: https://$REGION.$CONSOLE_DOMAIN/cloudwatch/home?region=$REGION#logsV2:log-groups"
echo ""
echo "Output information saved to cdk-outputs.env"
echo ""
echo "🎉 Application successfully deployed to AWS ECS Fargate!"
