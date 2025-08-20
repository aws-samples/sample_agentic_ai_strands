#!/usr/bin/env python3
"""
ECR Repository Setup Script
Creates AWS ECR repository: bedrock_agentcore-agent_runtime
"""

import sys
import os
import boto3
import json
from botocore.exceptions import ClientError
from boto3.session import Session

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import *


def create_ecr_repository(repository_name: str, region: str = None) -> dict:
    """
    Create ECR repository
    
    Args:
        repository_name (str): ECR repository name
        region (str): AWS region, defaults to current session region
        
    Returns:
        dict: repository information
    """
    # Use specified region or default region
    if region:
        ecr_client = boto3.client('ecr', region_name=region)
    else:
        boto_session = Session()
        region = boto_session.region_name or 'us-west-2'
        ecr_client = boto3.client('ecr', region_name=region)
    
    # Get account ID
    try:
        account_id = boto3.client("sts").get_caller_identity()["Account"]
    except Exception as e:
        print(f"❌ Unable to get AWS account ID: {e}")
        return None
    
    print(f"Creating ECR repository in region {region}: {repository_name}")
    print(f"AWS Account ID: {account_id}")
    
    try:
        # Attempt to create ECR repository
        response = ecr_client.create_repository(
            repositoryName=repository_name,
            imageScanningConfiguration={
                'scanOnPush': True
            },
            encryptionConfiguration={
                'encryptionType': 'AES256'
            }
        )
        
        repository = response['repository']
        repository_uri = repository['repositoryUri']
        repository_arn = repository['repositoryArn']
        
        print(f"✅ Successfully created ECR repository:")
        print(f"   Repository Name: {repository_name}")
        print(f"   Repository URI: {repository_uri}")
        print(f"   Repository ARN: {repository_arn}")
        print(f"   Region: {region}")
        
        return {
            'repository_name': repository_name,
            'repository_uri': repository_uri,
            'repository_arn': repository_arn,
            'region': region,
            'account_id': account_id,
            'created': True
        }
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        
        if error_code == 'RepositoryAlreadyExistsException':
            print(f"⚠️ ECR repository '{repository_name}' already exists")
            
            # Get existing repository information
            try:
                describe_response = ecr_client.describe_repositories(
                    repositoryNames=[repository_name]
                )
                
                if describe_response['repositories']:
                    repository = describe_response['repositories'][0]
                    repository_uri = repository['repositoryUri']
                    repository_arn = repository['repositoryArn']
                    
                    print(f"✅ Using existing ECR repository:")
                    print(f"   Repository Name: {repository_name}")
                    print(f"   Repository URI: {repository_uri}")
                    print(f"   Repository ARN: {repository_arn}")
                    print(f"   Region: {region}")
                    
                    return {
                        'repository_name': repository_name,
                        'repository_uri': repository_uri,
                        'repository_arn': repository_arn,
                        'region': region,
                        'account_id': account_id,
                        'created': False
                    }
                else:
                    print(f"❌ Unable to get existing repository information")
                    return None
                    
            except Exception as describe_error:
                print(f"❌ Error getting existing repository information: {describe_error}")
                return None
                
        else:
            print(f"❌ Error creating ECR repository: {e}")
            return None
            
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None


def setup_ecr_repository_with_policy(repository_name: str, region: str = None) -> dict:
    """
    Create ECR repository and set access policy
    
    Args:
        repository_name (str): ECR repository name
        region (str): AWS region
        
    Returns:
        dict: repository information
    """
    # Create repository
    repo_info = create_ecr_repository(repository_name, region)
    if not repo_info:
        return None
    
    # Set repository policy
    if region:
        ecr_client = boto3.client('ecr', region_name=region)
    else:
        boto_session = Session()
        region = boto_session.region_name or 'us-west-2'
        ecr_client = boto3.client('ecr', region_name=region)
    
    account_id = repo_info['account_id']
    
    # Define repository access policy
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowPushPull",
                "Effect": "Allow",
                "Principal": {
                    "AWS": f"arn:aws:iam::{account_id}:root"
                },
                "Action": [
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:PutImage",
                    "ecr:InitiateLayerUpload",
                    "ecr:UploadLayerPart",
                    "ecr:CompleteLayerUpload"
                ]
            },
            {
                "Sid": "AllowBedrockAgentCoreAccess",
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock-agentcore.amazonaws.com"
                },
                "Action": [
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer"
                ]
            }
        ]
    }
    
    try:
        # Set repository policy
        ecr_client.set_repository_policy(
            repositoryName=repository_name,
            policyText=json.dumps(policy_document)
        )
        print(f"✅ Successfully set ECR repository access policy")
        
    except Exception as e:
        print(f"⚠️ Error setting repository policy: {e}")
        # Policy setting failure doesn't affect repository creation
    
    return repo_info


def get_ecr_login_command(region: str = None) -> str:
    """
    Get ECR login command
    
    Args:
        region (str): AWS region
        
    Returns:
        str: ECR login command
    """
    if not region:
        boto_session = Session()
        region = boto_session.region_name or 'us-west-2'
    
    try:
        account_id = boto3.client("sts").get_caller_identity()["Account"]
        login_command = f"aws ecr get-login-password --region {region} | docker login --username AWS --password-stdin {account_id}.dkr.ecr.{region}.amazonaws.com"
        return login_command
    except Exception as e:
        print(f"❌ Error generating login command: {e}")
        return ""


if __name__ == '__main__':
    print("=" * 60)
    print("Setting up AWS ECR Repository")
    print("=" * 60)
    
    # Configuration parameters
    REPOSITORY_NAME = "bedrock_agentcore-agent_runtime"
    
    # Create ECR repository
    print(f"Creating ECR repository: {REPOSITORY_NAME}")
    repo_info = setup_ecr_repository_with_policy(REPOSITORY_NAME)
    
    if repo_info:
        print("\n" + "=" * 60)
        print("ECR Repository Setup Complete!")
        print("=" * 60)
        print(f"Repository Name: {repo_info['repository_name']}")
        print(f"Repository URI:  {repo_info['repository_uri']}")
        print(f"Repository ARN:  {repo_info['repository_arn']}")
        print(f"Region:          {repo_info['region']}")
        print(f"Account ID:      {repo_info['account_id']}")
        
        # Generate Docker login command
        login_command = get_ecr_login_command()
        if login_command:
            print("\n" + "-" * 60)
            print("Docker Login Command:")
            print(login_command)
        
        # Append ECR repository URI to .env_setup file
        try:
            with open(".env_setup", "a") as f:
                f.write(f"ECR_REPOSITORY_URI={repo_info['repository_uri']}\n")
            
            print(f"\n✅ ECR repository URI has been appended to .env_setup file")
            print(f"   ECR_REPOSITORY_URI={repo_info['repository_uri']}")
            
        except Exception as e:
            print(f"⚠️ Error saving ECR repository URI to .env_setup: {e}")
        
        print("\n" + "=" * 60)
        print("Next Steps:")
        print("1. Use the Docker login command above to login to ECR")
        print("2. Build Docker image:")
        print(f"   docker build -t {repo_info['repository_uri']}:latest .")
        print("3. Push image to ECR:")
        print(f"   docker push {repo_info['repository_uri']}:latest")
        print("=" * 60)
        
    else:
        print("\n❌ ECR Repository setup failed!")
        sys.exit(1)