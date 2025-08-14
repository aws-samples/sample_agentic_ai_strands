import sys
import os

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import setup_cognito_user_pool_with_signup

if __name__ == '__main__':
    print("Setting up Amazon Cognito user pool with signup...")
    cognito_config = setup_cognito_user_pool_with_signup()
    
    pool_id = cognito_config['pool_id']
    app_client_id = cognito_config['app_client_id']
    m2m_client_id = cognito_config['m2m_client_id']
    m2m_client_secret = cognito_config['m2m_client_secret']
    scope_string = cognito_config['scope_string']
    discovery_url = cognito_config['discovery_url']
    
    with open(".env_cognito", "w") as f:
        f.write(f"COGNITO_USER_POOL_ID={pool_id}\n")
        f.write(f"COGNITO_CLIENT_ID={app_client_id}\n")
        f.write(f"COGNITO_M2M_CLIENT_ID={m2m_client_id}\n")
        f.write(f"COGNITO_M2M_CLIENT_SECRET={m2m_client_secret}\n")
        f.write(f"COGNITO_M2M_CLIENT_SCOPE={scope_string}\n")
        f.write(f"discovery_url={discovery_url}")
    print("Cognito config saved to .env_cognito")
    print(cognito_config) 