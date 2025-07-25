from dotenv import load_dotenv
import os
import boto3
import utils

load_dotenv(dotenv_path=".env_mcp_cleanup_info")
agentID = os.getenv("agent_id")
repoName = os.getenv("repo_name")
roleName = os.getenv("role_name")
# ssmName = os.getenv("ssm_name")
# secretID = os.getenv("secret_id")


load_dotenv(dotenv_path=".env_cognito")
pool_id = os.getenv("pool_id")

load_dotenv(dotenv_path=".env_gateway")
gateway_role_name = os.getenv("gateway_role_arn").split("/")[-1]
bucket_name = os.getenv("s3_bucket")
gateway_id = os.getenv("gateway_id")
cpname = os.getenv("credential_provider_arn").split("/")[-1]

print("🗑️  Starting cleanup process...")

region='us-east-1'
agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=region)
ecr_client = boto3.client('ecr', region_name=region)
iam_client = boto3.client('iam', region_name=region)
cognito_client = boto3.client('cognito-idp', region_name=region)
gateway_client = boto3.client('bedrock-agentcore-control')
# ssm_client = boto3.client('ssm', region_name=region)
# secrets_client = boto3.client('secretsmanager', region_name=region)


try:
    # delete domain & user pool
    response = cognito_client.describe_user_pool(UserPoolId=pool_id)
    domain = response['UserPool'].get('Domain')
    response = cognito_client.delete_user_pool_domain(Domain=domain, UserPoolId=pool_id)
    print("Domain deleted.")
    response = cognito_client.delete_user_pool(UserPoolId=pool_id)
    print(f"User Pool {pool_id} deleted successfully.")

    # delete agentcore runtime
    print("Deleting AgentCore Runtime...")
    runtime_delete_response = agentcore_control_client.delete_agent_runtime(
        agentRuntimeId=agentID,
    )
    print("✓ AgentCore Runtime deletion initiated")

    # delete ECR repo
    print("Deleting ECR repository...")
    ecr_client.delete_repository(
        repositoryName=repoName,
        force=True
    )
    print("✓ ECR repository deleted")
    
    # delete mcp iam role
    print("Deleting MCP IAM role policies...")
    policies = iam_client.list_role_policies(
        RoleName=roleName,
        MaxItems=100
    )
    for policy_name in policies['PolicyNames']:
        iam_client.delete_role_policy(
            RoleName=roleName,
            PolicyName=policy_name
        )
    iam_client.delete_role(
        RoleName=roleName
    )
    print("✓ MCP IAM role deleted")

    # delete gateway iam role
    print("Deleting Gateway IAM role policies...")
    policies = iam_client.list_role_policies(
        RoleName=gateway_role_name,
        MaxItems=100
    )
    for policy_name in policies['PolicyNames']:
        iam_client.delete_role_policy(
            RoleName=gateway_role_name,
            PolicyName=policy_name
        )
    iam_client.delete_role(
        RoleName=gateway_role_name
    )
    print("✓ Gateway IAM role deleted")

    # delete S3 bucket
    s3 = boto3.client('s3')
    response = s3.list_objects_v2(Bucket=bucket_name)
    if 'Contents' in response:
        for obj in response['Contents']:
            s3.delete_object(Bucket=bucket_name, Key=obj['Key'])
    s3.delete_bucket(Bucket=bucket_name)
    print("✅ Bucket deleted successfully.")

    # delete credential provider
    acps = boto3.client(service_name="bedrock-agentcore-control")
    response = acps.delete_api_key_credential_provider(name="NasaInsightAPIKey")
    print("✓ credential provider deleted")

    # delete agentcore gateway
    utils.delete_gateway(gateway_client, gateway_id)

    # try:
    #     ssm_client.delete_parameter(Name=ssmName)
    #     print("✓ Parameter Store parameter deleted")
    # except ssm_client.exceptions.ParameterNotFound:
    #     print("ℹ️  Parameter Store parameter not found")

    # try:
    #     secrets_client.delete_secret(
    #         SecretId=secretID,
    #         ForceDeleteWithoutRecovery=True
    #     )
    #     print("✓ Secrets Manager secret deleted")
    # except secrets_client.exceptions.ResourceNotFoundException:
    #     print("ℹ️  Secrets Manager secret not found")

    print("\n✅ Cleanup completed successfully!")
    
except Exception as e:
    print(f"❌ Error during cleanup: {e}")
    print("You may need to manually clean up some resources.")