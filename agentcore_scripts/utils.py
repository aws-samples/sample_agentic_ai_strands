import boto3
import json
import time
from boto3.session import Session
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.constants import StrategyType
from botocore.exceptions import ClientError
import requests


def create_agentcore_gateway_role(gateway_name):
    iam_client = boto3.client('iam')
    agentcore_gateway_role_name = f'agentcore-{gateway_name}-role'
    boto_session = Session()
    region = boto_session.region_name
    account_id = boto3.client("sts").get_caller_identity()["Account"]
    role_policy = {
        "Version": "2012-10-17",
        "Statement": [{
                "Sid": "VisualEditor0",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:*",
                    "bedrock:*",
                    "agent-credential-provider:*",
                    "iam:PassRole",
                    "secretsmanager:GetSecretValue",
                    "lambda:InvokeFunction"
                ],
                "Resource": "*"
            }
        ]
    }

    assume_role_policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AssumeRolePolicy",
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock-agentcore.amazonaws.com"
                },
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {
                        "aws:SourceAccount": f"{account_id}"
                    },
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
                    }
                }
            }
        ]
    }

    assume_role_policy_document_json = json.dumps(
        assume_role_policy_document
    )

    role_policy_document = json.dumps(role_policy)
    # Create IAM Role for the Lambda function
    try:
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_gateway_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json
        )

        # Pause to make sure role is created
        time.sleep(10)
    except iam_client.exceptions.EntityAlreadyExistsException:
        print("Role already exists -- deleting and creating it again")
        policies = iam_client.list_role_policies(
            RoleName=agentcore_gateway_role_name,
            MaxItems=100
        )
        print("policies:", policies)
        for policy_name in policies['PolicyNames']:
            iam_client.delete_role_policy(
                RoleName=agentcore_gateway_role_name,
                PolicyName=policy_name
            )
        print(f"deleting {agentcore_gateway_role_name}")
        iam_client.delete_role(
            RoleName=agentcore_gateway_role_name
        )
        print(f"recreating {agentcore_gateway_role_name}")
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_gateway_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json
        )

    # Attach the AWSLambdaBasicExecutionRole policy
    print(f"attaching role policy {agentcore_gateway_role_name}")
    try:
        iam_client.put_role_policy(
            PolicyDocument=role_policy_document,
            PolicyName="AgentCorePolicy",
            RoleName=agentcore_gateway_role_name
        )
    except Exception as e:
        print(e)

    return agentcore_iam_role


def delete_gateway(gateway_client,gatewayId): 
    print("Deleting all targets for gateway", gatewayId)
    list_response = gateway_client.list_gateway_targets(
            gatewayIdentifier = gatewayId,
            maxResults=100
    )
    for item in list_response['items']:
        targetId = item["targetId"]
        print("Deleting target ", targetId)
        gateway_client.delete_gateway_target(
            gatewayIdentifier = gatewayId,
            targetId = targetId
        )
    print("Deleting gateway ", gatewayId)
    gateway_client.delete_gateway(gatewayIdentifier = gatewayId)


def get_token(user_pool_id: str, client_id: str, client_secret: str, scope_string: str, REGION: str) -> dict:
    try:
        user_pool_id_without_underscore = user_pool_id.replace("_", "")
        url = f"https://{user_pool_id_without_underscore}.auth.{REGION}.amazoncognito.com/oauth2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope_string,

        }
        print(client_id)
        print(client_secret)
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as err:
        return {"error": str(err)}


def setup_memclient():
    boto_session = Session()
    region = boto_session.region_name
    # Initialize Memory Client
    client = MemoryClient(region_name=region)
    memory_name = "AgentMemory"
    memory_id = ''
    # Define memory strategies for customer support
    strategies = [
        {
            StrategyType.USER_PREFERENCE.value: {
                "name": "UserPreferences",
                "description": "Captures customer preferences and behavior",
                "namespaces": ["user/{actorId}/preferences"]
            }
        },
        {
            StrategyType.SEMANTIC.value: {
                "name": "FactsSemantic",
                "description": "Stores facts from conversations",
                "namespaces": ["user/{actorId}/semantic"],
            }
        }
    ]
    print(f"Creating memory: {memory_name}")
    # Create memory resource
    try:
        memory = client.create_memory_and_wait(
            name=memory_name,
            strategies=strategies,         # Define the memory strategies
            description="Memory for strands agent",
            event_expiry_days=30,          # Memories expire after 90 days
        )
        memory_id = memory['id']
        print(f"✅ Created memory: {memory_id}")
        return memory_id
    except ClientError as e:
        if e.response['Error']['Code'] == 'ValidationException' and "already exists" in str(e):
            # If memory already exists, retrieve its ID
            memories = client.list_memories()
            memory_id = next((m['id'] for m in memories if m['id'].startswith(memory_name)), None)
            print(f"Memory already exists. Using existing memory ID: {memory_id}")
            return memory_id
    except Exception as e:
        # Handle any errors during memory creation
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        # Cleanup on error - delete the memory if it was partially created
        if memory_id:
            try:
                client.delete_memory_and_wait(memory_id=memory_id,max_wait = 300)
                print(f"Cleaned up memory: {memory_id}")
            except Exception as cleanup_error:
                print(f"Failed to clean up memory: {cleanup_error}")
    return memory_id
            
            
def get_user_token(client_id):
    boto_session = Session()
    region = boto_session.region_name
    
    # Initialize Cognito client
    cognito_client = boto3.client('cognito-idp', region_name=region)
    
    # Authenticate User and get Access Token
    auth_response = cognito_client.initiate_auth(
        ClientId=client_id,
        AuthFlow='USER_PASSWORD_AUTH',
        AuthParameters={
            'USERNAME': 'testuser',
            'PASSWORD': 'MyPassword123!'
        }
    )
    bearer_token = auth_response['AuthenticationResult']['AccessToken']
    # Output the required valuess
    print(f"Bearer Token: {bearer_token}")
    return bearer_token
    
    
def setup_cognito_user_pool():
    boto_session = Session()
    region = boto_session.region_name
    
    # Initialize Cognito client
    cognito_client = boto3.client('cognito-idp', region_name=region)
    
    try:
        # Create User Pool
        user_pool_response = cognito_client.create_user_pool(
            PoolName='StrandDemoPool',
            Policies={
                'PasswordPolicy': {
                    'MinimumLength': 8
                }
            },
            # Configure email verification
            AliasAttributes=['email'],
            AutoVerifiedAttributes=['email'],
            VerificationMessageTemplate={
                'DefaultEmailOption': 'CONFIRM_WITH_CODE',
                'EmailMessage': 'Your verification code is {####}',
                'EmailSubject': 'Your verification code'
            },
            # Configure email settings
            EmailConfiguration={
                'EmailSendingAccount': 'COGNITO_DEFAULT'
            }
        )
        pool_id = user_pool_response['UserPool']['Id']
        
        # Create App Client
        app_client_response = cognito_client.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName='StrandDemoPoolClient',
            GenerateSecret=False,
            ExplicitAuthFlows=[
                'ALLOW_USER_PASSWORD_AUTH',
                'ALLOW_USER_SRP_AUTH',
                'ALLOW_REFRESH_TOKEN_AUTH'
            ],
            # Set token expiration values
            AccessTokenValidity=24,      # 24 hours (maximum)
            IdTokenValidity=24,          # 24 hours (maximum)
            RefreshTokenValidity=30,     # 30 days
            TokenValidityUnits={
                'AccessToken': 'hours',
                'IdToken': 'hours',
                'RefreshToken': 'days'
            }
        )
        client_id = app_client_response['UserPoolClient']['ClientId']
        
        # Create User
        cognito_client.admin_create_user(
            UserPoolId=pool_id,
            Username='testuser',
            TemporaryPassword='Temp123!',
            MessageAction='SUPPRESS'
        )
        
        # Set Permanent Password
        cognito_client.admin_set_user_password(
            UserPoolId=pool_id,
            Username='testuser',
            Password='MyPassword123!',
            Permanent=True
        )
        
        # Authenticate User and get Access Token
        auth_response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': 'testuser',
                'PASSWORD': 'MyPassword123!'
            }
        )
        bearer_token = auth_response['AuthenticationResult']['AccessToken']
        
        # Output the required values
        print(f"Pool id: {pool_id}")
        print(f"Discovery URL: https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration")
        print(f"Client ID: {client_id}")
        print(f"Bearer Token: {bearer_token}")
        
        # Return values if needed for further processing
        return {
            'pool_id': pool_id,
            'client_id': client_id,
            'bearer_token': bearer_token,
            'discovery_url':f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"
        }
        
    except Exception as e:
        print(f"Error: {e}")
        return None


def setup_cognito_user_pool_with_signup(pool_name = "StrandDemoPoolWithSignup" ):
    """
    创建支持用户注册的 Cognito UserPool，如果pool已经存在，则更新设置
    """
    boto_session = Session()
    region = boto_session.region_name
    
    # Initialize Cognito client
    cognito_client = boto3.client('cognito-idp', region_name=region)
    
    pool_id = None
    client_id = None
    m2m_client_id = None
    m2m_client_secret = None
    
    try:
        # Try to create User Pool with email verification
        try:
            user_pool_response = cognito_client.create_user_pool(
                PoolName=pool_name,
                Policies={
                    'PasswordPolicy': {
                        'MinimumLength': 8,
                        'RequireUppercase': True,
                        'RequireLowercase': True,
                        'RequireNumbers': True,
                        'RequireSymbols': False
                    }
                },
                # Configure email verification
                AliasAttributes=['email'],
                AutoVerifiedAttributes=['email'],
                VerificationMessageTemplate={
                    'DefaultEmailOption': 'CONFIRM_WITH_CODE',
                    'EmailMessage': 'Your verification code is {####}',
                    'EmailSubject': 'Your verification code for Strands Agent'
                },
                # Configure email settings
                EmailConfiguration={
                    'EmailSendingAccount': 'COGNITO_DEFAULT'
                },
                # Configure sign-up settings
                AdminCreateUserConfig={
                    'AllowAdminCreateUserOnly': False,
                    'InviteMessageTemplate': {
                        'EmailMessage': 'Welcome to Strands Agent! Your username is {username} and temporary password is {####}',
                        'EmailSubject': 'Welcome to Strands Agent'
                    }
                }
            )
            pool_id = user_pool_response['UserPool']['Id']
            print(f"✅ Created new user pool: {pool_id}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'LimitExceededException' or 'already exists' in str(e).lower():
                # Pool already exists, find it by name
                print(f"User pool with name '{pool_name}' already exists, finding existing pool...")
                paginator = cognito_client.get_paginator('list_user_pools')
                for page in paginator.paginate(MaxResults=60):
                    for pool in page['UserPools']:
                        if pool['Name'] == pool_name:
                            pool_id = pool['Id']
                            print(f"✅ Found existing user pool: {pool_id}")
                            break
                    if pool_id:
                        break
                
                if not pool_id:
                    print(f"❌ Could not find existing user pool with name '{pool_name}'")
                    return None
                    
                # Update the existing user pool
                try:
                    cognito_client.update_user_pool(
                        UserPoolId=pool_id,
                        Policies={
                            'PasswordPolicy': {
                                'MinimumLength': 8,
                                'RequireUppercase': True,
                                'RequireLowercase': True,
                                'RequireNumbers': True,
                                'RequireSymbols': False
                            }
                        },
                        # Configure email verification
                        AliasAttributes=['email'],
                        AutoVerifiedAttributes=['email'],
                        VerificationMessageTemplate={
                            'DefaultEmailOption': 'CONFIRM_WITH_CODE',
                            'EmailMessage': 'Your verification code is {####}',
                            'EmailSubject': 'Your verification code for Strands Agent'
                        },
                        # Configure email settings
                        EmailConfiguration={
                            'EmailSendingAccount': 'COGNITO_DEFAULT'
                        },
                        # Configure sign-up settings
                        AdminCreateUserConfig={
                            'AllowAdminCreateUserOnly': False,
                            'InviteMessageTemplate': {
                                'EmailMessage': 'Welcome to Strands Agent! Your username is {username} and temporary password is {####}',
                                'EmailSubject': 'Welcome to Strands Agent'
                            }
                        }
                    )
                    print(f"✅ Updated existing user pool: {pool_id}")
                except Exception as update_error:
                    print(f"⚠️ Failed to update user pool (continuing with existing settings): {update_error}")
            else:
                raise e

        # Try to create App Client or find existing one
        try:
            app_client_response = cognito_client.create_user_pool_client(
                UserPoolId=pool_id,
                ClientName='StrandDemoPoolSignupClient',
                GenerateSecret=False,
                ExplicitAuthFlows=[
                    'ALLOW_USER_PASSWORD_AUTH',
                    'ALLOW_USER_SRP_AUTH',
                    'ALLOW_REFRESH_TOKEN_AUTH'
                ],
                # Set token expiration values
                AccessTokenValidity=24,      # 24 hours (maximum)
                IdTokenValidity=24,          # 24 hours (maximum)
                RefreshTokenValidity=30,     # 30 days
                TokenValidityUnits={
                    'AccessToken': 'hours',
                    'IdToken': 'hours',
                    'RefreshToken': 'days'
                }
            )
            client_id = app_client_response['UserPoolClient']['ClientId']
            print(f"✅ Created new app client: {client_id}")
            
        except ClientError as e:
            if 'already exists' in str(e).lower() or e.response['Error']['Code'] == 'LimitExceededException':
                # Find existing app client
                print("App client already exists, finding existing client...")
                paginator = cognito_client.get_paginator('list_user_pool_clients')
                for page in paginator.paginate(UserPoolId=pool_id, MaxResults=60):
                    for client in page['UserPoolClients']:
                        if client['ClientName'] == 'StrandDemoPoolSignupClient':
                            client_id = client['ClientId']
                            print(f"✅ Found existing app client: {client_id}")
                            break
                    if client_id:
                        break
                        
                if not client_id:
                    print("❌ Could not find existing app client")
                    return None
                    
                # Update the existing app client
                try:
                    cognito_client.update_user_pool_client(
                        UserPoolId=pool_id,
                        ClientId=client_id,
                        ClientName='StrandDemoPoolSignupClient',
                        GenerateSecret=False,
                        ExplicitAuthFlows=[
                            'ALLOW_USER_PASSWORD_AUTH',
                            'ALLOW_USER_SRP_AUTH',
                            'ALLOW_REFRESH_TOKEN_AUTH'
                        ],
                        AccessTokenValidity=24,
                        IdTokenValidity=24,
                        RefreshTokenValidity=30,
                        TokenValidityUnits={
                            'AccessToken': 'hours',
                            'IdToken': 'hours',
                            'RefreshToken': 'days'
                        }
                    )
                    print(f"✅ Updated existing app client: {client_id}")
                except Exception as update_error:
                    print(f"⚠️ Failed to update app client (continuing with existing settings): {update_error}")
            else:
                raise e
        
        # Create User (for testing)
        try:
            cognito_client.admin_create_user(
                UserPoolId=pool_id,
                Username='testuser',
                TemporaryPassword='Temp123!',
                MessageAction='SUPPRESS'
            )
            
            # Set Permanent Password
            cognito_client.admin_set_user_password(
                UserPoolId=pool_id,
                Username='testuser',
                Password='MyPassword123!',
                Permanent=True
            )
            
            print("✅ Test user created successfully")
        except Exception as user_error:
            print(f"⚠️ Test user creation failed (this is optional): {user_error}")
        

        # Try to create domain or use existing one
        user_pool_id_without_underscore_lc = pool_id.replace("_", "").lower()
        try:
            response = cognito_client.create_user_pool_domain(
                Domain=user_pool_id_without_underscore_lc,
                UserPoolId=pool_id
            )
            print(f"✅ Created new domain: {user_pool_id_without_underscore_lc}")
        except ClientError as e:
            if 'already exists' in str(e).lower() or e.response['Error']['Code'] == 'InvalidParameterException':
                print(f"✅ Domain already exists: {user_pool_id_without_underscore_lc}")
            else:
                raise e
        

        # Try to create resource server or use existing one
        RESOURCE_SERVER_ID = "strands-demo-resource-server-id"
        RESOURCE_SERVER_NAME = "strands-demo-resource-server-name"
        SCOPES = [
            {"ScopeName": "gateway:read", "ScopeDescription": "Read access"},
            {"ScopeName": "gateway:write", "ScopeDescription": "Write access"}
        ]
        
        try:
            print('Creating new resource server...')
            cognito_client.create_resource_server(
                UserPoolId=pool_id,
                Identifier=RESOURCE_SERVER_ID,
                Name=RESOURCE_SERVER_NAME,
                Scopes=SCOPES
            )
            print(f"✅ Created new resource server: {RESOURCE_SERVER_ID}")
        except ClientError as e:
            if 'already exists' in str(e).lower() or e.response['Error']['Code'] == 'InvalidParameterException':
                print(f"✅ Resource server already exists: {RESOURCE_SERVER_ID}")
                # Update existing resource server
                try:
                    cognito_client.update_resource_server(
                        UserPoolId=pool_id,
                        Identifier=RESOURCE_SERVER_ID,
                        Name=RESOURCE_SERVER_NAME,
                        Scopes=SCOPES
                    )
                    print(f"✅ Updated existing resource server: {RESOURCE_SERVER_ID}")
                except Exception as update_error:
                    print(f"⚠️ Failed to update resource server (continuing with existing settings): {update_error}")
            # else:
            #     raise e

        # Try to create M2M client or find existing one
        M2M_CLIENT_NAME = "strands-demo-m2m-client"
        try:
            print('Creating new M2M client...')
            created = cognito_client.create_user_pool_client(
                UserPoolId=pool_id,
                ClientName=M2M_CLIENT_NAME,
                GenerateSecret=True,
                AllowedOAuthFlows=["client_credentials"],
                AllowedOAuthScopes=[f"{RESOURCE_SERVER_ID}/gateway:read", f"{RESOURCE_SERVER_ID}/gateway:write"],
                AllowedOAuthFlowsUserPoolClient=True,
                SupportedIdentityProviders=["COGNITO"],
                ExplicitAuthFlows=["ALLOW_REFRESH_TOKEN_AUTH"]
            )
            m2m_client_id, m2m_client_secret = created["UserPoolClient"]["ClientId"], created["UserPoolClient"]["ClientSecret"]
            print(f"✅ Created new M2M client: {m2m_client_id}")
            
        except ClientError as e:
            if 'already exists' in str(e).lower() or e.response['Error']['Code'] == 'LimitExceededException':
                # Find existing M2M client
                print("M2M client already exists, finding existing client...")
                paginator = cognito_client.get_paginator('list_user_pool_clients')
                for page in paginator.paginate(UserPoolId=pool_id, MaxResults=60):
                    for client in page['UserPoolClients']:
                        if client['ClientName'] == M2M_CLIENT_NAME:
                            m2m_client_id = client['ClientId']
                            print(f"✅ Found existing M2M client: {m2m_client_id}")
                            break
                    if m2m_client_id:
                        break
                        
                if not m2m_client_id:
                    print("❌ Could not find existing M2M client")
                    return None
                
                # Get the client secret (note: we can't retrieve the secret for existing clients)
                print("⚠️ Using existing M2M client - secret cannot be retrieved")
                m2m_client_secret = "***EXISTING_CLIENT_SECRET***"
                
                # Update the existing M2M client
                try:
                    cognito_client.update_user_pool_client(
                        UserPoolId=pool_id,
                        ClientId=m2m_client_id,
                        ClientName=M2M_CLIENT_NAME,
                        AllowedOAuthFlows=["client_credentials"],
                        AllowedOAuthScopes=[f"{RESOURCE_SERVER_ID}/gateway:read", f"{RESOURCE_SERVER_ID}/gateway:write"],
                        AllowedOAuthFlowsUserPoolClient=True,
                        SupportedIdentityProviders=["COGNITO"],
                        ExplicitAuthFlows=["ALLOW_REFRESH_TOKEN_AUTH"]
                    )
                    print(f"✅ Updated existing M2M client: {m2m_client_id}")
                except Exception as update_error:
                    print(f"⚠️ Failed to update M2M client (continuing with existing settings): {update_error}")
            # else:
            #     raise e
        
        # get domain
        response = cognito_client.describe_user_pool(UserPoolId=pool_id)
        domain = response['UserPool'].get('Domain')
        
        scopeString = f"{RESOURCE_SERVER_ID}/gateway:read {RESOURCE_SERVER_ID}/gateway:write"

        # Output the required values
        print(f"Pool id: {pool_id}")
        print(f"Discovery URL: https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration")
        print(f"APP Client ID: {client_id}")
        print(f"Domain: {domain}.auth.{region}.amazoncognito.com")
        print(f"Resource server ID: {RESOURCE_SERVER_ID}")
        print(f"M2M Client ID: {m2m_client_id}")
        print(f"M2M Client Secret: {m2m_client_secret}")
        print(f"Scope String: {scopeString}")
        print("✅ UserPool with signup support setup completed successfully!")
        
        # Return values if needed for further processing
        return {
            'pool_id': pool_id,
            'app_client_id': client_id,
            'm2m_client_id': m2m_client_id,
            'm2m_client_secret': m2m_client_secret,
            'scope_string': scopeString,
            'discovery_url': f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def create_agentcore_role(agent_name):
    print(f"🔍 DEBUG: Starting create_agentcore_role for agent: {agent_name}")
    iam_client = boto3.client('iam')
    agentcore_role_name = f'agentcore-{agent_name}-role'
    boto_session = Session()
    region = boto_session.region_name
    account_id = boto3.client("sts").get_caller_identity()["Account"]
    print(f"🔍 DEBUG: Role name will be: {agentcore_role_name}")
    print(f"🔍 DEBUG: Region: {region}, Account: {account_id}")
    role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
            "Sid": "IAMRoleManagement",
            "Effect": "Allow",
            "Action": [
                "iam:CreateRole",
                "iam:DeleteRole",
                "iam:GetRole",
                "iam:PutRolePolicy",
                "iam:DeleteRolePolicy",
                "iam:AttachRolePolicy",
                "iam:DetachRolePolicy",
                "iam:TagRole",
                "iam:ListRolePolicies",
                "iam:ListAttachedRolePolicies"
            ],
            "Resource": [
                "arn:aws:iam::*:role/*BedrockAgentCore*",
                "arn:aws:iam::*:role/service-role/*BedrockAgentCore*"
            ]
           },
            {
                "Sid": "CodeBuildProjectAccess",
                "Effect": "Allow",
                "Action": [
                    "codebuild:StartBuild",
                    "codebuild:BatchGetBuilds",
                    "codebuild:ListBuildsForProject",
                    "codebuild:CreateProject",
                    "codebuild:UpdateProject",
                    "codebuild:BatchGetProjects"
                ],
                "Resource": [
                    "arn:aws:codebuild:*:*:project/bedrock-agentcore-*",
                    "arn:aws:codebuild:*:*:build/bedrock-agentcore-*"
                ]
            },
            {
                "Sid": "CodeBuildListAccess",
                "Effect": "Allow",
                "Action": [
                    "codebuild:ListProjects"
                ],
                "Resource": "*"
            },
            {
                "Sid": "BedrockPermissions",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                "Resource": "*"
            },
            {
            "Sid": "IAMPassRoleAccess",
            "Effect": "Allow",
            "Action": [
                "iam:PassRole"
            ],
            "Resource": [
                "arn:aws:iam::*:role/AmazonBedrockAgentCore*",
                "arn:aws:iam::*:role/service-role/AmazonBedrockAgentCore*"
            ]
            },
            {
                "Sid": "ECRImageAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer"
                ],
                "Resource": [
                    f"arn:aws:ecr:{region}:{account_id}:repository/*"
                ]
            },
            {
                "Sid": "CloudWatchLogsAccess",
                "Effect": "Allow",
                "Action": [
                    "logs:GetLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams"
                ],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}::log-group:/aws/bedrock-agentcore/*",
                    f"arn:aws:logs:{region}:{account_id}::log-group:/aws/codebuild/*"
                ]
            },
            {
                "Sid": "S3Access",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket",
                    "s3:CreateBucket",
                    "s3:PutLifecycleConfiguration"
                ],
                "Resource": [
                    "arn:aws:s3:::bedrock-agentcore-*",
                    "arn:aws:s3:::bedrock-agentcore-*/*"
                ]
            },
            {
                "Sid": "ECRRepositoryAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:CreateRepository",
                    "ecr:DescribeRepositories",
                    "ecr:GetRepositoryPolicy",
                    "ecr:InitiateLayerUpload",
                    "ecr:CompleteLayerUpload",
                    "ecr:PutImage",
                    "ecr:UploadLayerPart",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                    "ecr:ListImages",
                    "ecr:TagResource"
                ],
                "Resource": [
                    f"arn:aws:ecr:{region}:{account_id}::repository/bedrock-agentcore-*"
                ]
            },
            {
                "Sid": "ECRAuthorizationAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:GetAuthorizationToken"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup"
                ],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/agent_runtime*"
                ]
            },
            {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": [
                f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
            ]
        },
            {
            "Effect": "Allow",
            "Action": [
                "xray:PutTraceSegments",
                "xray:PutTelemetryRecords",
                "xray:GetSamplingRules",
                "xray:GetSamplingTargets"
                ],
             "Resource": [ "*" ]
             },
             {
                "Effect": "Allow",
                "Resource": "*",
                "Action": "cloudwatch:PutMetricData",
                "Condition": {
                    "StringEquals": {
                        "cloudwatch:namespace": "bedrock-agentcore"
                    }
                }
            },
            {
                "Sid": "GetAgentAccessToken",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId"
                ],
                "Resource": [
                  f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default",
                  f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default/workload-identity/*"
                ]
            },
            {
                "Sid": "DynamoDBAccess",
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:BatchGetItem",
                    "dynamodb:BatchWriteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan"
                ],
                "Resource": [
                    f"arn:aws:dynamodb:{region}:{account_id}:table/*"
                ]
            }
        ]
    }
    assume_role_policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AssumeRolePolicy",
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock-agentcore.amazonaws.com"
                },
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {
                        "aws:SourceAccount": f"{account_id}"
                    },
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
                    }
                }
            }
        ]
    }

    assume_role_policy_document_json = json.dumps(
        assume_role_policy_document
    )
    role_policy_document = json.dumps(role_policy)
    print(f"🔍 DEBUG: Policy document length: {len(role_policy_document)} characters")
    
    # Create IAM Role for the Lambda function
    role_created = False
    try:
        print(f"🔍 DEBUG: Attempting to create role: {agentcore_role_name}")
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json
        )
        print(f"✅ DEBUG: Successfully created new role: {agentcore_role_name}")
        role_created = True

        # Pause to make sure role is created
        print("🔍 DEBUG: Waiting 10 seconds for role propagation...")
        time.sleep(10)
    except iam_client.exceptions.EntityAlreadyExistsException:
        print(f"⚠️ DEBUG: Role already exists: {agentcore_role_name}")
        print("🔍 DEBUG: CRITICAL - Previous version would return here WITHOUT attaching policies!")
        agentcore_iam_role = iam_client.get_role(
            RoleName=agentcore_role_name
        )
        print(f"🔍 DEBUG: Retrieved existing role: {agentcore_iam_role['Role']['Arn']}")
        # DON'T RETURN - Continue to attach policies!

    # Attach the inline policy
    print(f"🔍 DEBUG: Starting policy attachment for {agentcore_role_name}")
    
    # Check existing inline policies first
    try:
        existing_policies = iam_client.list_role_policies(RoleName=agentcore_role_name)
        print(f"🔍 DEBUG: Existing inline policies: {existing_policies.get('PolicyNames', [])}")
    except Exception as e:
        print(f"⚠️ DEBUG: Could not list existing policies: {e}")
    
    print(f"🔍 DEBUG: Attaching inline policy 'AgentCorePolicy' to {agentcore_role_name}")
    try:
        iam_client.put_role_policy(
            PolicyDocument=role_policy_document,
            PolicyName="AgentCorePolicy",
            RoleName=agentcore_role_name
        )
        print(f"✅ DEBUG: Successfully attached inline policy 'AgentCorePolicy'")
    except Exception as e:
        print(f"❌ DEBUG: FAILED to attach inline policy: {type(e).__name__}: {e}")
        print(f"🔍 DEBUG: Policy document preview: {role_policy_document[:200]}...")

    # Check existing managed policies first
    try:
        existing_managed = iam_client.list_attached_role_policies(RoleName=agentcore_role_name)
        print(f"🔍 DEBUG: Existing managed policies: {[p['PolicyName'] for p in existing_managed.get('AttachedPolicies', [])]}")
    except Exception as e:
        print(f"⚠️ DEBUG: Could not list existing managed policies: {e}")

    # Attach the AWS managed policy for Bedrock AgentCore Memory
    memory_policy_arn = "arn:aws:iam::aws:policy/AmazonBedrockAgentCoreMemoryBedrockModelInferenceExecutionRolePolicy"
    print(f"🔍 DEBUG: Attaching managed policy: {memory_policy_arn}")
    try:
        iam_client.attach_role_policy(
            RoleName=agentcore_role_name,
            PolicyArn=memory_policy_arn
        )
        print(f"✅ DEBUG: Successfully attached memory policy")
    except Exception as e:
        print(f"❌ DEBUG: FAILED to attach memory policy: {type(e).__name__}: {e}")
        
    # Attach the AWS managed policy for Bedrock AgentCore Full Access
    full_access_policy_arn = "arn:aws:iam::aws:policy/BedrockAgentCoreFullAccess"
    print(f"🔍 DEBUG: Attaching managed policy: {full_access_policy_arn}")
    try:
        iam_client.attach_role_policy(
            RoleName=agentcore_role_name,
            PolicyArn=full_access_policy_arn
        )
        print(f"✅ DEBUG: Successfully attached full access policy")
    except Exception as e:
        print(f"❌ DEBUG: FAILED to attach full access policy: {type(e).__name__}: {e}")
    
    # Attach the AWS managed policy for ElasticBeanstalk Administrator Access
    eb_admin_policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess-AWSElasticBeanstalk"
    print(f"🔍 DEBUG: Attaching managed policy: {eb_admin_policy_arn}")
    try:
        iam_client.attach_role_policy(
            RoleName=agentcore_role_name,
            PolicyArn=eb_admin_policy_arn
        )
        print(f"✅ DEBUG: Successfully attached ElasticBeanstalk admin policy")
    except Exception as e:
        print(f"❌ DEBUG: FAILED to attach ElasticBeanstalk admin policy: {type(e).__name__}: {e}")
    
    print(f"🔍 DEBUG: create_agentcore_role completed for {agentcore_role_name}")
    return agentcore_iam_role