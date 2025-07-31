from mcp.server.fastmcp import FastMCP
import boto3, os, time, json
from botocore.exceptions import ClientError, NoCredentialsError

# replace to your role name
eb_service_role = 'aws-elasticbeanstalk-service-role'
ec2_profile = 'aws-elasticbeanstalk-ec2-role'

mcp = FastMCP("eb-deploy-server")

def create_bucket_if_not_exists(s3_client, bucket_name: str, region: str) -> bool:
    """Create S3 bucket if it doesn't exist"""
    try:
        # Check if bucket exists
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"Bucket {bucket_name} already exists")
        return True
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            # Bucket doesn't exist, create it
            try:
                if region == 'us-east-1':
                    # For us-east-1, don't specify LocationConstraint
                    s3_client.create_bucket(Bucket=bucket_name)
                else:
                    s3_client.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={'LocationConstraint': region}
                    )
                print(f"Created bucket {bucket_name}")
                return True
            except ClientError as create_error:
                raise ValueError(f"Failed to create bucket {bucket_name}: {str(create_error)}")
        else:
            raise ValueError(f"Failed to check bucket {bucket_name}: {str(e)}")


def upload_zip_to_s3(zip_file_path, bucket_name):
    """upload zip to s3"""
    s3 = boto3.client('s3')
    region = s3.meta.region_name

    create_bucket_if_not_exists(s3, bucket_name, region)
    
    filename = os.path.basename(zip_file_path)
    s3_key = f'eb-deployments/{filename}'
    print(f"Uploading {zip_file_path} to S3...")
    s3.upload_file(zip_file_path, bucket_name, s3_key)
    print("✅ Upload completed")
    
    return s3_key


def create_eb_application_version(app_name, version_label, bucket_name, s3_key):
    """创建EB应用版本"""
    eb = boto3.client('elasticbeanstalk')
    
    print(f"Creating application version: {version_label}")
    
    response = eb.create_application_version(
        ApplicationName=app_name,
        VersionLabel=version_label,
        SourceBundle={
            'S3Bucket': bucket_name,
            'S3Key': s3_key
        },
        AutoCreateApplication=True,
        Description=f'Deployed at {time.strftime("%Y-%m-%d %H:%M:%S")}'
    )
    
    print("✅ Application version created")
    return response


def deploy_to_eb_environment(app_name, env_name, version_label, eb_service_role, ec2_profile):
    """部署到EB环境"""
    eb = boto3.client('elasticbeanstalk')
    
    print(f"Deploying to environment: {env_name}")
    
    # 创建新环境
    response = eb.create_environment(
        ApplicationName=app_name,
        EnvironmentName=env_name,
        SolutionStackName='64bit Amazon Linux 2023 v4.6.1 running Python 3.13',
        VersionLabel=version_label,
        OptionSettings=[
            {
                'Namespace': 'aws:autoscaling:launchconfiguration',
                'OptionName': 'InstanceType',
                'Value': 't3.micro'
            },
            {
                'Namespace': 'aws:elasticbeanstalk:environment',
                'OptionName': 'ServiceRole',
                'Value': eb_service_role
            },
            {
                'Namespace': 'aws:autoscaling:launchconfiguration',
                'OptionName': 'IamInstanceProfile',
                'Value': ec2_profile
            }
        ]
    )
    
    print("✅ Deployment initiated")
    response = wait_for_deployment_complete(app_name, env_name, timeout=600)
    return response


def wait_for_deployment_complete(app_name, env_name, timeout=600):
    eb = boto3.client('elasticbeanstalk')
    start_time = time.time()
    
    print(f"⏳ Waiting for deployment to complete...")
    print(f"Application: {app_name}, Environment: {env_name}")
    print("-" * 50)
    
    while time.time() - start_time < timeout:
        try:
            print("Checking environment setup status...")
            # 获取环境状态
            response = eb.describe_environments(
                ApplicationName=app_name,
                EnvironmentNames=[env_name]
            )
            env = response['Environments'][0]
            status = env['Status']
            health = env['Health']
            
            # 检查是否完成
            if status == 'Ready':
                if health == 'Green':
                    print("✅ Deployment completed successfully!")
                    return {
                        'success': True,
                        'status': status,
                        'health': health,
                        'url': env.get('CNAME', ''),
                        'environment_id': env.get('EnvironmentId', '')
                    }
                elif health == 'Yellow':
                    print("⚠️ Deployment completed with warnings")
                    return {
                        'success': True,
                        'status': status,
                        'health': health,
                        'url': env.get('CNAME', ''),
                        'warning': 'Application health is Yellow'
                    }
                elif health == 'Red':
                    print("❌ Deployment completed but application is unhealthy")
                    return {
                        'success': False,
                        'status': status,
                        'health': health,
                        'error': 'Application health is Red'
                    }
            elif status == 'Terminated':
                print("❌ Environment terminated during deployment")
                return {
                    'success': False,
                    'status': status,
                    'error': 'Environment was terminated'
                }
            
        except Exception as e:
            print(f"❌ Error checking deployment status: {e}")
        
        time.sleep(10)
    
    # 超时
    print("⏰ Deployment timeout reached")
    return {
        'success': False,
        'status': 'Timeout',
        'error': f'Deployment did not complete within {timeout} seconds'
    }


def eb_deploy_from_zip(zip_file_path):
    # set necessary variables for eb
    s3_bucket_name = "eb-deploy-"+str(int(time.time()))
    app_name = 'eb-app-'+str(int(time.time()))
    env_name = "dev-env-"+str(int(time.time()))

    # deploy
    s3_key = upload_zip_to_s3(zip_file_path, s3_bucket_name)
    res = create_eb_application_version(app_name, "1", s3_bucket_name, s3_key)
    res = deploy_to_eb_environment(app_name, env_name, "1", eb_service_role, ec2_profile)
    return f"Check out the app at: {res.get('url')}"

@mcp.tool()
def deploy_on_eb_from_path(proj_dir):
    """Deploy a flask project with AWS Elastic Beanstalk and return a public URL of the deployed project
    
    Args:
        proj_dir: complete absolute path to the flask project you want to deploy
    
    Returns:
        a public URL that you can use to access your deployed flask-based website
    """
    try:
        # For EB deployment
        # Add .ebextensions/python.config file
        ebx_path = os.path.join(proj_dir, ".ebextensions")
        os.mkdir(ebx_path)
        config_path = os.path.join(ebx_path, "python.config")
        with open(config_path, "w") as f:
            f.write("option_settings:\n")
            f.write("  aws:elasticbeanstalk:container:python:\n")
            f.write('    WSGIPath: "app:app"')
        
        # Zip the project
        parent_dir = os.path.dirname(proj_dir)
        zip_file_path = os.path.join(parent_dir, "eb-deploy.zip")
        os.system(f"cd {proj_dir} && zip -r ../eb-deploy.zip .")
        eb_url = eb_deploy_from_zip(zip_file_path)
        return eb_url
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()