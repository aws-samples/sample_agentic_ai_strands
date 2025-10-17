import streamlit as st
import boto3
import json
import base64
from typing import Dict, Any
import time

# Configure Streamlit page
st.set_page_config(
    page_title="Workshop Validation UI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize AWS Lambda client
@st.cache_resource
def get_lambda_client():
    """Initialize and cache the Lambda client"""
    try:
        return boto3.client('lambda')
    except Exception as e:
        st.error(f"Failed to initialize AWS Lambda client: {str(e)}")
        return None

def invoke_lambda_function(function_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke a Lambda function with the given payload"""
    lambda_client = get_lambda_client()
    if not lambda_client:
        return {"error": "Lambda client not available"}
    
    try:
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        # Parse the response
        response_payload = json.loads(response['Payload'].read())
        return {
            "success": True,
            "response": response_payload,
            "status_code": response['StatusCode']
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def decode_encrypted_message(encrypted_message: str) -> str:
    """Decode the base64 encoded message from Lambda response"""
    try:
        decoded_bytes = base64.b64decode(encrypted_message)
        return decoded_bytes.decode('utf-8')
    except Exception as e:
        return f"Failed to decode message: {str(e)}"

def display_lambda_response(result: Dict[str, Any]):
    """Display the Lambda function response in a formatted way"""
    if result.get("success"):
        st.success("✅ Lambda function executed successfully!")
        
        response = result["response"]
        st.subheader("Response Details:")
        
        # Display status code
        st.info(f"**Status Code:** {result['status_code']}")
        
        # Display encrypted message if present
        if "encrypted_message" in response:
            st.code(f"Encrypted Message: {response['encrypted_message']}", language="text")
        
        # Display any additional response fields
        if "message" in response:
            st.info(f"**Message:** {response['message']}")
        
        # Display full response
        with st.expander("Full Response JSON"):
            st.json(response)
    else:
        st.error("❌ Lambda function execution failed!")
        st.error(f"**Error:** {result['error']}")

# Main UI
st.title("🚀 Workshop Validation UI")
st.markdown("---")

# Sidebar for AWS configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # AWS Region selection
    aws_region = st.selectbox(
        "AWS Region",
        ["us-west-2", "us-east-1"],
        index=0
    )
    
    # Lambda function names (with defaults)
    st.subheader("Lambda Function Names")
    task1_function = st.text_input("Task 1 Function", value="jam_task_1_validation")
    task2_function = st.text_input("Task 2 Function", value="jam_task_2_validation")
    task3_function = st.text_input("Task 3 Function", value="jam_task_3_validation")
    
    st.markdown("---")
    # st.markdown("**Note:** Make sure your AWS credentials are properly configured.")

# Main content area with tabs
tab1, tab2, tab3 = st.tabs(["📋 Task 2: Awakening ARIA's Core Intelligence", "🏗️ Task 3: Building ARIA's Enterprise Platform", "📝 Task 4: Demonstrating ARIA's Real-World Magic"])

# Task 1 Tab - AgentCore Runtime Validation
with tab1:
    st.header("Task 2: Awakening ARIA's Core Intelligence")
    st.markdown("This task validates if the AgentCore runtime is deployed and running.")
    
    with st.form("task1_form"):
        st.subheader("Input Parameters")
        
        col1, col2 = st.columns(2)
        
        with col1:
            task1_guid = st.text_input(
                "Task GUID *",
                placeholder="Enter unique task identifier",
                help="A unique identifier for this validation task"
            )
        
        with col2:
            agentcore_arn = st.text_input(
                "AgentCore Runtime ARN *",
                placeholder="arn:aws:bedrock-agentcore:region:account:runtime/agent_runtime_id",
                help="The ARN of the AgentCore runtime to validate"
            )
        
        submitted1 = st.form_submit_button("🚀 Validate AgentCore Runtime", use_container_width=True)
        
        if submitted1:
            if not task1_guid or not agentcore_arn:
                st.error("Please fill in all required fields!")
            else:
                payload = {
                    "TASKGUID": task1_guid,
                    "AGENTCORE_RUNTIME_ARN": agentcore_arn
                }
                
                with st.spinner("Invoking Lambda function..."):
                    result = invoke_lambda_function(task1_function, payload)
                    display_lambda_response(result)

# Task 2 Tab - ECS Stack Validation
with tab2:
    st.header("Task 3: Building ARIA's Enterprise Platform")
    st.markdown("This task validates if the ECS CloudFormation stack is deployed successfully.")
    
    with st.form("task2_form"):
        st.subheader("Input Parameters")
        
        task2_guid = st.text_input(
            "Task GUID *",
            placeholder="Enter unique task identifier",
            help="A unique identifier for this validation task"
        )
        
        st.info("**Note:** This task automatically checks for the 'StrandsAgentsEcsFargateStack' CloudFormation stack.")
        
        submitted2 = st.form_submit_button("🏗️ Validate ECS Stack", use_container_width=True)
        
        if submitted2:
            if not task2_guid:
                st.error("Please provide a Task GUID!")
            else:
                payload = {
                    "TASKGUID": task2_guid
                }
                
                with st.spinner("Invoking Lambda function..."):
                    result = invoke_lambda_function(task2_function, payload)
                    display_lambda_response(result)

# Task 3 Tab - Text Evaluation
with tab3:
    st.header("Task 4: Demonstrating ARIA's Real-World Magic")
    st.markdown("This task evaluates text content against a specific task using AI scoring criteria.")
    
    with st.form("task3_form"):
        st.subheader("Input Parameters")
        
        col1, col2 = st.columns(2)
        
        with col1:
            task3_guid = st.text_input(
                "Task GUID *",
                placeholder="Enter unique task identifier",
                help="A unique identifier for this validation task"
            )
        
        with col2:
            option = st.number_input(
                "Option",
                min_value=1,
                max_value=10,
                value=1,
                help="Option parameter for the evaluation"
            )
        
        task_description = st.text_area(
            "Task Description *",
            placeholder="Describe the task that needs to be evaluated...",
            height=100,
            help="The task description against which the text will be evaluated"
        )
        
        text_content = st.text_area(
            "Text Content to Evaluate *",
            placeholder="Enter the text content that needs to be evaluated...",
            height=200,
            help="The text content that will be scored against the task description"
        )
        
        st.markdown("**Evaluation Criteria:**")
        st.markdown("""
        - **Content Accuracy & Relevance** (25 pts): Correctness and task alignment
        - **Language Clarity & Fluency** (20 pts): Grammar, readability, flow
        - **Logical Structure & Organization** (20 pts): Clear structure and idea progression
        - **Innovation & Depth** (15 pts): Insights beyond basic requirements
        - **Task Completeness** (20 pts): Addresses all task requirements thoroughly
        """)
        
        submitted3 = st.form_submit_button("📝 Evaluate Text", use_container_width=True)
        
        if submitted3:
            if not task3_guid or not task_description or not text_content:
                st.error("Please fill in all required fields!")
            else:
                payload = {
                    "TASKGUID": task3_guid,
                    "OPTION": option,
                    "TASK": task_description,
                    "TEXT": text_content
                }
                
                with st.spinner("Invoking Lambda function and evaluating with Bedrock..."):
                    result = invoke_lambda_function(task3_function, payload)
                    display_lambda_response(result)

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
        <p>Workshop Lambda Validation UI | Built with Streamlit</p>
    </div>
    """,
    unsafe_allow_html=True
)