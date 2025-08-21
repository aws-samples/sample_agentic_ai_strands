#!/usr/bin/env python3
"""
Environment Variables Update Script
Reads environment variables from .env_setup file and updates corresponding variables in the .env file in the parent directory
Also updates bedrock_agentcore_template.yaml with execution_role, account, and ecr_repository values
"""

import os
import re
import yaml
from typing import Dict, List, Tuple

try:
    import boto3
    from botocore.exceptions import NoCredentialsError, ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


def parse_env_file(file_path: str) -> Dict[str, str]:
    """
    Parse environment variable file
    
    Args:
        file_path: Path to environment variable file
        
    Returns:
        Dict[str, str]: Dictionary of environment variables
    """
    env_vars = {}
    
    if not os.path.exists(file_path):
        print(f"File does not exist: {file_path}")
        return env_vars
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines and comment lines
                if not line or line.startswith('#'):
                    continue
                
                # Match environment variable format: KEY=VALUE
                match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$', line)
                if match:
                    key = match.group(1)
                    value = match.group(2)
                    
                    # Remove quotes from value if present
                    # if value.startswith('"') and value.endswith('"'):
                    #     value = value[1:-1]
                    # elif value.startswith("'") and value.endswith("'"):
                    #     value = value[1:-1]
                    
                    env_vars[key] = value #f"\"{value}\"" if key == 'COGNITO_M2M_CLIENT_SCOPE' else value
                else:
                    print(f"Warning: Line {line_num} has incorrect format: {line}")
    
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
    
    return env_vars


def get_actual_aws_region() -> str:
    """
    Get the actual AWS region using boto3
    
    Returns:
        str: The current AWS region
    """
    if not BOTO3_AVAILABLE:
        print("Warning: boto3 not available, cannot detect AWS region")
        return None
    
    try:
        # Try to get region from boto3 session
        session = boto3.Session()
        region = session.region_name
        if region:
            print(f"Detected AWS region from boto3 session: {region}")
            return region
        
        # Try to get region from STS service (requires credentials)
        try:
            sts_client = boto3.client('sts')
            # Get caller identity to determine the region from the endpoint
            response = sts_client.get_caller_identity()
            # Extract region from the ARN if available
            if 'Arn' in response:
                arn_parts = response['Arn'].split(':')
                if len(arn_parts) > 3:
                    region = arn_parts[3]
                    if region:
                        print(f"Detected AWS region from STS ARN: {region}")
                        return region
        except (NoCredentialsError, ClientError) as e:
            print(f"Could not determine region from STS: {e}")
        
        # Try to get region from EC2 metadata (if running on EC2)
        try:
            ec2_client = boto3.client('ec2')
            region = ec2_client.meta.region_name
            if region:
                print(f"Detected AWS region from EC2 client: {region}")
                return region
        except Exception as e:
            print(f"Could not determine region from EC2 metadata: {e}")
        
        # Try to get from AWS config
        try:
            import configparser
            import os.path
            
            aws_config_path = os.path.expanduser('~/.aws/config')
            if os.path.exists(aws_config_path):
                config = configparser.ConfigParser()
                config.read(aws_config_path)
                if 'default' in config and 'region' in config['default']:
                    region = config['default']['region']
                    print(f"Detected AWS region from AWS config file: {region}")
                    return region
        except Exception as e:
            print(f"Could not read AWS config file: {e}")
            
    except Exception as e:
        print(f"Error detecting AWS region: {e}")
    
    print("Could not detect AWS region, using default: us-east-1")
    return 'us-east-1'


def read_env_file_lines(file_path: str) -> List[str]:
    """
    Read all lines from environment variable file
    
    Args:
        file_path: Path to environment variable file
        
    Returns:
        List[str]: All lines in the file
    """
    if not os.path.exists(file_path):
        print(f"File does not exist: {file_path}")
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.readlines()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return []


def update_env_file(env_file_path: str, updates: Dict[str, str], backup: bool = True) -> bool:
    """
    Update environment variable file
    
    Args:
        env_file_path: Path to environment variable file to update
        updates: Dictionary of environment variables to update
        backup: Whether to create backup file
        
    Returns:
        bool: Whether the update was successful
    """
    if not os.path.exists(env_file_path):
        print(f"File does not exist: {env_file_path}")
        return False
    
    # Create backup file
    if backup:
        backup_path = f"{env_file_path}.backup"
        try:
            with open(env_file_path, 'r', encoding='utf-8') as src, \
                 open(backup_path, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
            print(f"Created backup file: {backup_path}")
        except Exception as e:
            print(f"Failed to create backup file: {e}")
            return False
    
    # Read original file content
    lines = read_env_file_lines(env_file_path)
    if not lines:
        return False
    
    updated_lines = []
    updated_keys = set()
    
    # Iterate through each line, updating matching environment variables
    for line in lines:
        original_line = line
        stripped_line = line.strip()
        
        # Skip empty lines and comment lines
        if not stripped_line or stripped_line.startswith('#'):
            updated_lines.append(original_line)
            continue
        
        # Match environment variable format
        match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$', stripped_line)
        if match:
            key = match.group(1)
            
            if key in updates:
                # Update variable value while maintaining original format style
                new_value = updates[key]
                
                # Check if original value was surrounded by quotes
                original_value = match.group(2)
                if original_value.startswith('"') and original_value.endswith('"'):
                    new_line = f"{key}=\"{new_value}\"\n"
                elif original_value.startswith("'") and original_value.endswith("'"):
                    new_line = f"{key}='{new_value}'\n"
                else:
                    new_line = f"{key}={new_value}\n"
                
                updated_lines.append(new_line)
                updated_keys.add(key)
                print(f"Updated variable: {key}")
            else:
                updated_lines.append(original_line)
        else:
            updated_lines.append(original_line)
    
    # Write updated content to file
    try:
        with open(env_file_path, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)
        
        print(f"Successfully updated {len(updated_keys)} environment variables")
        print(f"Updated variables: {', '.join(sorted(updated_keys))}")
        
        # Show variables that were not updated (exist in setup file but not in env file)
        not_found_keys = set(updates.keys()) - updated_keys
        if not_found_keys:
            print(f"The following variables were not found in target file and not updated: {', '.join(sorted(not_found_keys))}")
        
        return True
        
    except Exception as e:
        print(f"Error writing to file {env_file_path}: {e}")
        return False


def update_yaml_template(yaml_file_path: str, env_vars: Dict[str, str]) -> bool:
    """
    Update bedrock_agentcore_template.yaml with values from environment variables
    
    Args:
        yaml_file_path: Path to the YAML template file
        env_vars: Dictionary of environment variables
        
    Returns:
        bool: Whether the update was successful
    """
    if not os.path.exists(yaml_file_path):
        print(f"YAML template file does not exist: {yaml_file_path}")
        return False
    
    try:
        # Read YAML file
        with open(yaml_file_path, 'r', encoding='utf-8') as f:
            yaml_data = yaml.safe_load(f)
        
        updates_made = []
        
        # Update execution_role if AGENTCORE_EXECUTION_ROLE is available
        if 'AGENTCORE_EXECUTION_ROLE' in env_vars:
            execution_role = env_vars['AGENTCORE_EXECUTION_ROLE']
            if 'agents' in yaml_data and 'agent_runtime' in yaml_data['agents']:
                if 'aws' not in yaml_data['agents']['agent_runtime']:
                    yaml_data['agents']['agent_runtime']['aws'] = {}
                yaml_data['agents']['agent_runtime']['aws']['execution_role'] = execution_role
                updates_made.append('execution_role')
                
                # Extract account ID from execution role ARN
                # ARN format: arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME
                match = re.search(r'arn:aws:iam::(\d+):', execution_role)
                if match:
                    account_id = match.group(1)
                    yaml_data['agents']['agent_runtime']['aws']['account'] = account_id
                    updates_made.append('account')
                    print(f"Extracted account ID: {account_id}")
        
        # Update ecr_repository if ECR_REPOSITORY_URI is available
        if 'ECR_REPOSITORY_URI' in env_vars:
            ecr_repository = env_vars['ECR_REPOSITORY_URI']
            if 'agents' in yaml_data and 'agent_runtime' in yaml_data['agents']:
                if 'aws' not in yaml_data['agents']['agent_runtime']:
                    yaml_data['agents']['agent_runtime']['aws'] = {}
                yaml_data['agents']['agent_runtime']['aws']['ecr_repository'] = ecr_repository
                updates_made.append('ecr_repository')
        
        # Update region - try multiple sources
        region = None
        print("DEBUG: Attempting to determine AWS region...")
        
        # Method 1: Extract from ECR_REPOSITORY_URI
        if 'ECR_REPOSITORY_URI' in env_vars:
            ecr_uri = env_vars['ECR_REPOSITORY_URI']
            print(f"DEBUG: Found ECR_REPOSITORY_URI: {ecr_uri}")
            # ECR URI format: <account-id>.dkr.ecr.<region>.amazonaws.com/<repo-name>
            ecr_match = re.search(r'\.dkr\.ecr\.([^.]+)\.amazonaws\.com', ecr_uri)
            if ecr_match:
                region = ecr_match.group(1)
                print(f"DEBUG: Extracted region from ECR URI: {region}")
        
        # Method 2: Check environment variables
        if not region:
            for region_var in ['AWS_DEFAULT_REGION', 'AWS_REGION', 'REGION']:
                if region_var in env_vars:
                    region = env_vars[region_var]
                    print(f"DEBUG: Found region from {region_var}: {region}")
                    break
        
        # Method 3: Default fallback
        if not region:
            region = 'us-east-1'  # Default region as used in setup_ecr.py
            print(f"DEBUG: Using default region: {region}")
        
        # Update region in YAML
        if region and 'agents' in yaml_data and 'agent_runtime' in yaml_data['agents']:
            if 'aws' not in yaml_data['agents']['agent_runtime']:
                yaml_data['agents']['agent_runtime']['aws'] = {}
            yaml_data['agents']['agent_runtime']['aws']['region'] = region
            updates_made.append('region')
            print(f"Updated region: {region}")
        
        if updates_made:
            # Write updated YAML back to file
            with open(yaml_file_path, 'w', encoding='utf-8') as f:
                yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)
            
            print(f"Successfully updated YAML template with: {', '.join(updates_made)}")
            return True
        else:
            print("No relevant environment variables found for YAML template update")
            return True
            
    except Exception as e:
        print(f"Error updating YAML template {yaml_file_path}: {e}")
        return False


def main():
    """Main function"""
    # Get script directory and project root directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    # Set file paths
    env_setup_path = os.path.join(script_dir, '.env_setup')
    env_path = os.path.join(project_root, '.env')
    yaml_template_path = os.path.join(project_root, '.bedrock_agentcore.yaml')
    
    print("=" * 60)
    print("Environment Variables Update Script")
    print("=" * 60)
    print(f"Reading configuration file: {env_setup_path}")
    print(f"Updating target file: {env_path}")
    print(f"Updating YAML template: {yaml_template_path}")
    print()
    
    # Check if files exist
    if not os.path.exists(env_setup_path):
        print(f"Error: Configuration file does not exist: {env_setup_path}")
        return 1
    
    if not os.path.exists(env_path):
        print(f"Error: Target file does not exist: {env_path}")
        return 1
    
    # Parse configuration file
    print("Reading configuration file...")
    setup_vars = parse_env_file(env_setup_path)
    if not setup_vars:
        print("Error: No valid environment variables found in configuration file")
        return 1
    
    # Detect actual AWS region and add it to setup variables
    print("Detecting actual AWS region...")
    actual_region = get_actual_aws_region()
    if actual_region:
        setup_vars['AWS_REGION'] = actual_region
        setup_vars['AGENTCORE_REGION'] = actual_region
        print(f"Will update AWS_REGION and AGENTCORE_REGION to: {actual_region}")
    else:
        print("Warning: Could not detect AWS region, skipping region update")
    
    print(f"Read {len(setup_vars)} environment variables from configuration file:")
    for key, value in setup_vars.items():
        # For sensitive information, only show first few characters
        if 'SECRET' in key.upper() or 'KEY' in key.upper():
            display_value = value[:8] + "..." if len(value) > 8 else value
        else:
            display_value = value
        print(f"  {key} = {display_value}")
    print()
    
    # Update target .env file
    print("Updating target .env file...")
    env_success = update_env_file(env_path, setup_vars, backup=True)
    
    # Update YAML template file
    print("\nUpdating YAML template file...")
    yaml_success = update_yaml_template(yaml_template_path, setup_vars)
    
    if env_success and yaml_success:
        print("\nAll updates completed! ✓")
        return 0
    else:
        if not env_success:
            print("\n.env file update failed! ✗")
        if not yaml_success:
            print("\nYAML template update failed! ✗")
        return 1


if __name__ == "__main__":
    exit(main())