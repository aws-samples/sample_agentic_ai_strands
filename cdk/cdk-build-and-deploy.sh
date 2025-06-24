#!/bin/bash

set -e

# 完整的 CDK 构建和部署脚本
echo "开始完整的 CDK 构建和部署流程..."

# 检查.env文件是否存在
if [ ! -f "../.env" ]; then
    echo "错误: .env 文件不存在，请先创建 .env 文件"
    exit 1
fi

# 读取.env文件
set -a
source ../.env
set +a
export NODE_ENV=production
# 配置变量
REGION="${AWS_REGION:-cn-northwest-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
PREFIX="strands-mcp-app"
PLATFORM="linux/arm64"
# Mem0 配置 - 从环境变量读取，默认启用
ENABLE_MEM0="${ENABLE_MEM0:-true}"
export CDK_DEFAULT_REGION=$REGION
export CDK_DEFAULT_ACCOUNT=$ACCOUNT_ID
export ENABLE_MEM0=$ENABLE_MEM0
# 检测是否为中国区域
if [[ $REGION == cn-* ]]; then
    IS_CHINA_REGION=true
    ECR_DOMAIN="amazonaws.com.cn"
    CONSOLE_DOMAIN="console.amazonaws.cn"
    echo "检测到中国区域: $REGION"
else
    IS_CHINA_REGION=false
    ECR_DOMAIN="amazonaws.com"
    CONSOLE_DOMAIN="console.aws.amazon.com"
    echo "检测到全球区域: $REGION"
fi

echo "使用 AWS 账户: $ACCOUNT_ID"
echo "使用区域: $REGION"
echo "ECR 域名: $ECR_DOMAIN"
echo "Mem0 功能: $ENABLE_MEM0"

# 1. 创建或获取 ECR 仓库
echo "========================================="
echo "步骤 1: 创建 ECR 仓库"
echo "========================================="

# 创建前端 ECR 仓库
echo "创建前端 ECR 仓库..."
aws ecr create-repository \
    --repository-name ${PREFIX}-frontend \
    --region $REGION 2>/dev/null || echo "前端 ECR 仓库已存在"

# 创建后端 ECR 仓库
echo "创建后端 ECR 仓库..."
aws ecr create-repository \
    --repository-name ${PREFIX}-backend \
    --region $REGION 2>/dev/null || echo "后端 ECR 仓库已存在"

# 获取 ECR 仓库 URI
FRONTEND_ECR="$ACCOUNT_ID.dkr.ecr.$REGION.$ECR_DOMAIN/${PREFIX}-frontend"
BACKEND_ECR="$ACCOUNT_ID.dkr.ecr.$REGION.$ECR_DOMAIN/${PREFIX}-backend"

echo "ECR 仓库准备完成："
echo "- 前端 ECR: $FRONTEND_ECR"
echo "- 后端 ECR: $BACKEND_ECR"

# 2. 构建和推送 Docker 镜像
echo "========================================="
echo "步骤 2: 构建和推送 Docker 镜像"
echo "========================================="

# 登录到 ECR
echo "登录到 ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.$ECR_DOMAIN


BUILDER_NAME="mybuilder"
echo "检查Docker buildx builder '$BUILDER_NAME' 是否以及存在..."
# Check if the builder exists
if docker buildx ls | grep -q "$BUILDER_NAME"; then
    echo "Builder '$BUILDER_NAME' exists. Skip it..."
else
    echo "Creating new builder '$BUILDER_NAME'..."
    docker buildx create --name "$BUILDER_NAME" --platform "$PLATFORM" --use
fi

# 构建前端镜像
echo "构建前端镜像 (ARM64)..."
cd ../react_ui
cp .env.example .env.local
if [[ $IS_CHINA_REGION == true ]]; then
    echo "使用中国镜像源构建前端镜像..."
    docker buildx build --platform "$PLATFORM" --build-arg USE_CHINA_MIRROR=true --load -t ${PREFIX}-frontend:latest .
else
    docker buildx build --platform "$PLATFORM" --load -t ${PREFIX}-frontend:latest .
fi
docker tag ${PREFIX}-frontend:latest $FRONTEND_ECR:latest
docker push $FRONTEND_ECR:latest
cd ..

echo "前端镜像推送完成: $FRONTEND_ECR:latest"

# 构建后端镜像
echo "构建后端镜像 (ARM64)..."
if [[ $IS_CHINA_REGION == true ]]; then
    echo "使用中国镜像源构建后端镜像..."
    docker buildx build --platform "$PLATFORM" --build-arg USE_CHINA_MIRROR=true --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple --load -t ${PREFIX}-backend:latest -f Dockerfile.backend .
else
    docker buildx build --platform "$PLATFORM" --load -t ${PREFIX}-backend:latest -f Dockerfile.backend .
fi
docker tag ${PREFIX}-backend:latest $BACKEND_ECR:latest
docker push $BACKEND_ECR:latest

echo "后端镜像推送完成: $BACKEND_ECR:latest"

# 3. 准备 CDK 环境
echo "========================================="
echo "步骤 3: 准备 CDK 环境"
echo "========================================="

cd cdk

# 安装依赖
echo "安装 CDK 依赖..."
# npm install -g typescript
# npm install
# npm i --save-dev @types/node
# 构建 TypeScript
echo "构建 TypeScript..."
npm run build

# Bootstrap CDK (如果需要)
echo "检查 CDK Bootstrap..."
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region $REGION &>/dev/null; then
    echo "Bootstrap CDK 环境..."
    npx cdk bootstrap --region $REGION
else
    echo "CDK 已经 Bootstrap"
fi

cd ..

# 4. 更新 Secrets Manager
echo "========================================="
echo "步骤 4: 更新 Secrets Manager 配置"
echo "========================================="

echo "从 .env 文件更新 Secrets Manager..."

# 创建或更新 AWS 凭证
aws secretsmanager create-secret \
    --name "${PREFIX}/aws-credentials" \
    --description "AWS Access Credentials" \
    --secret-string "{\"AccessKeyId\":\"${AWS_ACCESS_KEY_ID}\",\"SecretAccessKey\":\"${AWS_SECRET_ACCESS_KEY}\"}" \
    --region $REGION 2>/dev/null || \
aws secretsmanager update-secret \
    --secret-id "${PREFIX}/aws-credentials" \
    --secret-string "{\"AccessKeyId\":\"${AWS_ACCESS_KEY_ID}\",\"SecretAccessKey\":\"${AWS_SECRET_ACCESS_KEY}\"}" \
    --region $REGION

if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️ OPENAI_API_KEY 未设置或为空"
else
    # 创建或更新 OPENAI 兼容接口 API Key
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
    echo "⚠️ OPENAI_BASE_URL 未设置或为空"
else
    # 创建或更新 OPENAI 兼容接口 API Base
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
# 创建或更新 Langfuse 配置
# aws secretsmanager create-secret \
#     --name "${PREFIX}/langfuse-host" \
#     --description "Langfuse Host" \
#     --secret-string "${LANGFUSE_HOST}" \
#     --region $REGION 2>/dev/null || \
# aws secretsmanager update-secret \
#     --secret-id "${PREFIX}/langfuse-host" \
#     --secret-string "${LANGFUSE_HOST}" \
#     --region $REGION

# aws secretsmanager create-secret \
#     --name "${PREFIX}/langfuse-public-key" \
#     --description "Langfuse Public Key" \
#     --secret-string "${LANGFUSE_PUBLIC_KEY}" \
#     --region $REGION 2>/dev/null || \
# aws secretsmanager update-secret \
#     --secret-id "${PREFIX}/langfuse-public-key" \
#     --secret-string "${LANGFUSE_PUBLIC_KEY}" \
#     --region $REGION

# aws secretsmanager create-secret \
#     --name "${PREFIX}/langfuse-secret-key" \
#     --description "Langfuse Secret Key" \
#     --secret-string "${LANGFUSE_SECRET_KEY}" \
#     --region $REGION 2>/dev/null || \
# aws secretsmanager update-secret \
#     --secret-id "${PREFIX}/langfuse-secret-key" \
#     --secret-string "${LANGFUSE_SECRET_KEY}" \
#     --region $REGION

echo "Secrets Manager 配置完成"

# 5. 部署 CDK Stack（现在镜像已存在）
echo "========================================="
echo "步骤 5: 部署 CDK Stack"
echo "========================================="

cd cdk
echo "部署 CDK Stack（镜像已准备就绪）..."
echo "Mem0 功能设置: $ENABLE_MEM0"
export AWS_ACCOUNT_ID=$ACCOUNT_ID
export AWS_REGION=$REGION
export ENABLE_MEM0=$ENABLE_MEM0
npx cdk deploy --require-approval never --region $REGION --context enableMem0=$ENABLE_MEM0

# 获取输出
STACK_NAME="McpEcsFargateStack"

# 等待 Stack 部署完成
echo "等待 Stack 部署完成..."
aws cloudformation wait stack-create-complete --stack-name $STACK_NAME --region $REGION 2>/dev/null || \
aws cloudformation wait stack-update-complete --stack-name $STACK_NAME --region $REGION 2>/dev/null || true

# 获取部署输出
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

echo "CDK Stack 部署完成："
echo "- ALB DNS: $ALB_DNS"
echo "- 集群名称: $CLUSTER_NAME"
SERVICES=$(aws ecs list-services --cluster $CLUSTER_NAME --region $REGION --query 'serviceArns[*]' --output text)
# 解析服务名称
FRONTEND_SERVICE=""
BACKEND_SERVICE=""

for service_arn in $SERVICES; do
    service_name=$(basename $service_arn)
    echo "找到服务: $service_name"
    
    if [[ $service_name == *"frontend"* ]]; then
        FRONTEND_SERVICE=$service_name
    elif [[ $service_name == *"backend"* ]]; then
        BACKEND_SERVICE=$service_name
    fi
done

# 6. 等待服务稳定
echo "========================================="
echo "步骤 6: 等待服务更新完成"
echo "========================================="
echo "前端服务: $FRONTEND_SERVICE"
echo "后端服务: $BACKEND_SERVICE"
echo "等待前端服务稳定..."
aws ecs wait services-stable \
    --cluster $CLUSTER_NAME \
    --services $FRONTEND_SERVICE \
    --region $REGION &

echo "等待后端服务稳定..."
aws ecs wait services-stable \
    --cluster $CLUSTER_NAME \
    --services $BACKEND_SERVICE \
    --region $REGION &

# 等待两个服务都完成
wait

# 7. 部署完成
echo "========================================="
echo "部署完成！"
echo "========================================="

# 保存输出信息
cat > cdk-outputs.env << EOF
ALB_DNS=$ALB_DNS
FRONTEND_ECR=$FRONTEND_ECR
BACKEND_ECR=$BACKEND_ECR
CLUSTER_NAME=$CLUSTER_NAME
STACK_NAME=$STACK_NAME
REGION=$REGION
ACCOUNT_ID=$ACCOUNT_ID
EOF

echo "部署信息："
echo "- ALB DNS: $ALB_DNS"
echo "- 前端访问地址: http://$ALB_DNS"
echo "- 后端 API 地址: http://$ALB_DNS/api"
echo "- ECS 集群: $CLUSTER_NAME"
echo ""
echo "监控链接："
echo "- ECS 控制台: https://$REGION.$CONSOLE_DOMAIN/ecs/home?region=$REGION#/clusters/$CLUSTER_NAME"
echo "- CloudWatch 日志: https://$REGION.$CONSOLE_DOMAIN/cloudwatch/home?region=$REGION#logsV2:log-groups"
echo ""
echo "输出信息已保存到 cdk-outputs.env"
echo ""
echo "🎉 MCP 应用已成功部署到 AWS ECS Fargate！"
