## Setup agentcore runtime

### first install agentcore toolkit

```bash
source .venv/bin/activate
uv pip install bedrock-agentcore-starter-toolkit
```

## Deployment Steps

### Step 1: Set role and identity

```bash
cd agentcore_scripts
./run.sh
```

check output files in the folder `agentcore_scripts`

### Step 1: Configure Your Agent

# Run the configuration command to set up your agent:

`uv run agentcore configure --entrypoint src/agent_runtime.py -er <REPLACE_FROM_IAM_ROLE_ARN>`

- The command will:
- Generate a Dockerfile and .dockerignore
- Create a .bedrock_agentcore.yaml configuration file

### Step 2: Launch Your Agent to the Cloud

```
#### Local Testing

##### For development and testing, you can run your agent locally:
`agentcore launch -l`

##### This will:

##### Build a Docker image

### Run the container locally

### Start a server at http://localhost:8080

# Deploy your agent to AWS:

agentcore launch

# This command will:

### Build a Docker image with your agent code

### Push the image to Amazon ECR

### Create a Bedrock AgentCore runtime

### Deploy your agent to the cloud
```