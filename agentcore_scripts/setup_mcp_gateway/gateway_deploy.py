import os
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from pprint import pprint
from dotenv import load_dotenv
from gw_utils import create_agentcore_gateway_role


assert load_dotenv(dotenv_path="../.env_cognito")
m2m_client_id = os.getenv("m2m_client_id")
cognito_discovery_url = os.getenv("discovery_url")

def main(my_api_key, bucket_name = 'nasa-open-api' ):
    #### Create an IAM role for the Gateway to assume
    agentcore_gateway_iam_role = create_agentcore_gateway_role("sample-apigateway")
    print("Agentcore gateway role ARN: ", agentcore_gateway_iam_role['Role']['Arn'])

    #### CreateGateway with Cognito authorizer without CMK. Use the Cognito user pool created in the previous step
    gateway_client = boto3.client('bedrock-agentcore-control')
    auth_config = {
        "customJWTAuthorizer": { 
            "allowedClients": [m2m_client_id],  # Client MUST match with the ClientId configured in Cognito. Example: 7rfbikfsm51j2fpaggacgng84g
            "discoveryUrl": cognito_discovery_url
        }
    }
    create_response = gateway_client.create_gateway(
        name='DemoGWOpenAPIAPIKeyNasaOAIforStrandsDemo',
        roleArn = agentcore_gateway_iam_role['Role']['Arn'], # The IAM Role must have permissions to create/list/get/delete Gateway 
        protocolType='MCP',
        authorizerType='CUSTOM_JWT',
        authorizerConfiguration=auth_config, 
        description='AgentCore Gateway with OpenAPI target'
    )
    # Retrieve the GatewayID used for GatewayTarget creation
    gatewayID = create_response["gatewayId"]
    gatewayURL = create_response["gatewayUrl"]
    print(gatewayID)
    print(gatewayURL)


    #### create api key credential provider
    acps = boto3.client(service_name="bedrock-agentcore-control")
    cpname = "NasaInsightAPIKeyDemo"
    response=acps.create_api_key_credential_provider(
        name=cpname, 
        apiKey=my_api_key, 
    )
    credentialProviderARN = response['credentialProviderArn']
    pprint(f"Egress Credentials provider ARN, {credentialProviderARN}")


    #### Upload openai json file to S3 bucket
    session = boto3.session.Session()
    s3_client = session.client('s3')


    # Check if bucket exists 
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"Bucket {bucket_name} already exists")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            s3_client.create_bucket(Bucket=bucket_name)
            
    file_path = 'openapi-specs/nasa_mars_insights_openapi.json'
    object_key = 'nasa_mars_insights_openapi.json'
    # Upload the file using put_object and read response
    try:
        with open(file_path, 'rb') as file_data:
            response = s3_client.put_object(Bucket=bucket_name, Key=object_key, Body=file_data)
        # Construct the ARN of the uploaded object with account ID and region
        openapi_s3_uri = f's3://{bucket_name}/{object_key}'
        print(f'Uploaded object S3 URI: {openapi_s3_uri}')
    except Exception as e:
        print(f'Error uploading file: {e}')


    #### Configure outbound auth and create the gateway target
    # S3 Uri for OpenAPI spec file
    nasa_openapi_s3_target_config = {
        "mcp": {
            "openApiSchema": {
                "s3": {
                    "uri": openapi_s3_uri
                }
            }
        }
    }
    # API Key credentials provider configuration
    api_key_credential_config = [
        {
            "credentialProviderType" : "API_KEY", 
            "credentialProvider": {
                "apiKeyCredentialProvider": {
                        "credentialParameterName": "api_key", # Replace this with the name of the api key name expected by the respective API provider. For passing token in the header, use "Authorization"
                        "providerArn": credentialProviderARN,
                        "credentialLocation":"QUERY_PARAMETER", # Location of api key. Possible values are "HEADER" and "QUERY_PARAMETER".
                        #"credentialPrefix": " " # Prefix for the token. Valid values are "Basic". Applies only for tokens.
                }
            }
        }
    ]
    targetname='DemoOpenAPITargetS3NasaMarsforStrands'
    response = gateway_client.create_gateway_target(
        gatewayIdentifier=gatewayID,
        name=targetname,
        description='OpenAPI Target with S3Uri using SDK',
        targetConfiguration=nasa_openapi_s3_target_config,
        credentialProviderConfigurations=api_key_credential_config)
    print(response)

    with open(".env_gateway", "w") as f:
        f.write(f"gateway_role_arn={agentcore_gateway_iam_role['Role']['Arn']}\n")
        f.write(f"gateway_id={gatewayID}\n")
        f.write(f"gateway_url={gatewayURL}\n")
        f.write(f"s3_bucket={bucket_name}\n")
        f.write(f"credential_provider_arn={credentialProviderARN}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--my-api-key', type=str)
    parser.add_argument('--bucket-name', type=str)
    args = parser.parse_args()
    my_api_key = args.my_api_key
    bucket_name = args.bucket_name
    main(my_api_key=my_api_key,bucket_name=bucket_name)