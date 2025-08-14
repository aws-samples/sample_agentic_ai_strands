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
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    env_vars[key] = value
                else:
                    print(f"Warning: Line {line_num} has incorrect format: {line}")
    
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
    
    return env_vars


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