#!/bin/bash

set -e
# Read .env file
set -a
source ../.env
set +a
# Configure variables
if [ -z "$AWS_REGION" ]; then
    echo "Error: AWS_REGION environment variable is not set."
    echo "Please set AWS_REGION before running this script:"
    echo "  export AWS_REGION=us-west-2"
    echo "  # or your preferred AWS region"
    exit 1
fi
REGION="$AWS_REGION"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
PREFIX="strands-agentcore"

# Detect if it's China region
if [[ $REGION == cn-* ]]; then
    IS_CHINA_REGION=true
    ECR_DOMAIN="amazonaws.com.cn"
    echo "Detected China region: $REGION"
else
    IS_CHINA_REGION=false
    ECR_DOMAIN="amazonaws.com"
    echo "Detected global region: $REGION"
fi

echo "Updating deployed ECS services..."
echo "Using AWS account: $ACCOUNT_ID"
echo "Using region: $REGION"
echo "ECR domain: $ECR_DOMAIN"

# Get ECR repository URI
FRONTEND_ECR="$ACCOUNT_ID.dkr.ecr.$REGION.$ECR_DOMAIN/${PREFIX}-frontend"
BACKEND_ECR="$ACCOUNT_ID.dkr.ecr.$REGION.$ECR_DOMAIN/${PREFIX}-backend"

echo "Frontend ECR: $FRONTEND_ECR"
echo "Backend ECR: $BACKEND_ECR"


# 4. Update ECS services
echo "========================================="
echo "Step 4: Get ECS service names"
echo "========================================="
# cd cdk

CLUSTER_NAME="${PREFIX}-cluster"

# Get all services in the cluster
echo "Getting service list in cluster $CLUSTER_NAME..."
SERVICES=$(aws ecs list-services --cluster $CLUSTER_NAME --region $REGION --query 'serviceArns[*]' --output text)

if [ -z "$SERVICES" ]; then
    echo "Error: No services found in cluster $CLUSTER_NAME"
    exit 1
fi

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

echo "Frontend service: $FRONTEND_SERVICE"
echo "Backend service: $BACKEND_SERVICE"

if [ -z "$FRONTEND_SERVICE" ] || [ -z "$BACKEND_SERVICE" ]; then
    echo "Error: Frontend or backend service not found"
    echo "Found services: $SERVICES"
    exit 1
fi

echo "========================================="
echo "Step 5: Update ECS services"
echo "========================================="

echo "Force updating frontend service: $FRONTEND_SERVICE"
aws ecs update-service \
    --cluster $CLUSTER_NAME \
    --service $FRONTEND_SERVICE \
    --force-new-deployment \
    --region $REGION > /dev/null

echo "Force updating backend service: $BACKEND_SERVICE"
aws ecs update-service \
    --cluster $CLUSTER_NAME \
    --service $BACKEND_SERVICE \
    --force-new-deployment \
    --region $REGION > /dev/null

# 6. Wait for service update to complete
echo "========================================="
echo "Step 6: Wait for service update to complete"
echo "========================================="

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

echo "========================================="
echo "ECS service update completed!"
echo "========================================="

# Get ALB DNS name
ALB_DNS=$(aws cloudformation describe-stacks \
    --stack-name StrandsAgentsEcsFargateStack \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`AlbDnsName`].OutputValue' \
    --output text 2>/dev/null || echo "Unable to get ALB DNS")

echo "Deployment information:"
echo "- Cluster name: $CLUSTER_NAME"
echo "- Frontend service: $FRONTEND_SERVICE"
echo "- Backend service: $BACKEND_SERVICE"
echo "- ALB DNS: $ALB_DNS"
echo ""
echo "Access URLs:"
echo "- Frontend: http://$ALB_DNS/chat"
echo "- Backend API: http://$ALB_DNS/v1/"
echo ""
echo "🎉 ECS service update successful!"
