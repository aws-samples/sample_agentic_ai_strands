from utils import create_agentcore_role

agent_name="strands_agent_role"

if __name__ == '__main__':
    print(f"Creating IAM role for {agent_name}...")
    agentcore_iam_role = create_agentcore_role(agent_name=agent_name)
    print(f"IAM role created ✓")
    print(f"Role ARN: {agentcore_iam_role['Role']['Arn']}")

