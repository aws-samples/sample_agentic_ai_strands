#!/bin/bash

set -e

# 配置变量
REGION="${AWS_REGION:-us-east-2}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
PREFIX="strands-agentcore"

# 检测是否为中国区域
if [[ $REGION == cn-* ]]; then
    IS_CHINA_REGION=true
    ECR_DOMAIN="amazonaws.com.cn"
    echo "检测到中国区域: $REGION"
else
    IS_CHINA_REGION=false
    ECR_DOMAIN="amazonaws.com"
    echo "检测到全球区域: $REGION"
fi

echo "更新已部署的 ECS 服务..."
echo "使用 AWS 账户: $ACCOUNT_ID"
echo "使用区域: $REGION"
echo "ECR 域名: $ECR_DOMAIN"

# 获取 ECR 仓库 URI
FRONTEND_ECR="$ACCOUNT_ID.dkr.ecr.$REGION.$ECR_DOMAIN/${PREFIX}-frontend"
BACKEND_ECR="$ACCOUNT_ID.dkr.ecr.$REGION.$ECR_DOMAIN/${PREFIX}-backend"

echo "前端 ECR: $FRONTEND_ECR"
echo "后端 ECR: $BACKEND_ECR"


# 4. 更新 ECS 服务
echo "========================================="
echo "步骤 4: 获取 ECS 服务名称"
echo "========================================="
# cd cdk

CLUSTER_NAME="${PREFIX}-cluster"

# 获取集群中的所有服务
echo "获取集群 $CLUSTER_NAME 中的服务列表..."
SERVICES=$(aws ecs list-services --cluster $CLUSTER_NAME --region $REGION --query 'serviceArns[*]' --output text)

if [ -z "$SERVICES" ]; then
    echo "错误: 在集群 $CLUSTER_NAME 中未找到任何服务"
    exit 1
fi

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

echo "前端服务: $FRONTEND_SERVICE"
echo "后端服务: $BACKEND_SERVICE"

if [ -z "$FRONTEND_SERVICE" ] || [ -z "$BACKEND_SERVICE" ]; then
    echo "错误: 未找到前端或后端服务"
    echo "找到的服务: $SERVICES"
    exit 1
fi

echo "========================================="
echo "步骤 5: 更新 ECS 服务"
echo "========================================="

echo "强制更新前端服务: $FRONTEND_SERVICE"
aws ecs update-service \
    --cluster $CLUSTER_NAME \
    --service $FRONTEND_SERVICE \
    --force-new-deployment \
    --region $REGION > /dev/null

echo "强制更新后端服务: $BACKEND_SERVICE"
aws ecs update-service \
    --cluster $CLUSTER_NAME \
    --service $BACKEND_SERVICE \
    --force-new-deployment \
    --region $REGION > /dev/null

# 6. 等待服务更新完成
echo "========================================="
echo "步骤 6: 等待服务更新完成"
echo "========================================="

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

echo "========================================="
echo "ECS 服务更新完成！"
echo "========================================="

# 获取 ALB DNS 名称
ALB_DNS=$(aws cloudformation describe-stacks \
    --stack-name StrandsAgentsEcsFargateStack \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`AlbDnsName`].OutputValue' \
    --output text 2>/dev/null || echo "无法获取ALB DNS")

echo "部署信息："
echo "- 集群名称: $CLUSTER_NAME"
echo "- 前端服务: $FRONTEND_SERVICE"
echo "- 后端服务: $BACKEND_SERVICE"
echo "- ALB DNS: $ALB_DNS"
echo ""
echo "访问地址："
echo "- 前端: http://$ALB_DNS/chat"
echo "- 后端API: http://$ALB_DNS/v1/"
echo ""
echo "🎉 ECS 服务更新成功！"
