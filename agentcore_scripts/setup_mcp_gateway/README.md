## Overview
You can use this to set up Amazon Cognito, deploy a local mcp server (s3 upload server) to Bedrock AgentCore MCP runtime, and deploy a AgentCore Gateway to transform APIs (we used NASA Mars weather API) into mcp tools.
In the process, we create two execution roles for MCP runtime and Gateway.

## How to use
1. Prepare a s3 bucket 
2. We are going to have a Mars Weather agent getting weather data from Nasa's Open APIs. You will need to register for Nasa Insight API [here](https://api.nasa.gov/). It's free! Once you register, you will get an API Key in your email. Use the API key to configure the credentials provider for creating the OpenAPI target.
3. After you've run `setup_congnito` in folder `agentcore_scripts/`, you will get a `.env_cognito` file
4. in `agentcore_scripts/setup_mcp_gateway/`   
    - run `bash setup_mcp_runtime.sh` 
    - run `bash setup_gateway.sh <nasa-api-key> <s3bucketname>`
3. Waiting for resources to be created
4. Use test_mcp_gateway.ipynb to test MCP and Gateway
5. Use resource-clean-up.py to delete resources you just deployed
