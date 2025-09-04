import json
import boto3
import logging
import base64
import re
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

MODEL_ID = "openai.gpt-oss-120b-1:0"

prompt_template_1 = """You are an expert evaluator tasked with scoring responses using a comprehensive rubric. Follow this structured evaluation process:

Score the response using this rubric:

## SCORING CRITERIA:
1. Content Accuracy & Relevance (25 pts): Correctness and task alignment
2. Language Clarity & Fluency (20 pts): Grammar, readability, flow
3. Logical Structure & Organization (20 pts): Clear structure and idea progression
4. Innovation & Depth (15 pts): Insights beyond basic requirements
5. Task Completeness (20 pts): Addresses all task requirements thoroughly


## SCORING SCALE:
-Excellent: 90-100% of category points
-Good: 70-89% of category points
-Fair: 50-69% of category points
-Poor: Below 50% of category points


## Task: 
{task}

## Response: 
<response>
{text}
</response>

## OUTPUT FORMAT:
```json
{{
  "overall_assessment": "Summary and key explanation for the score",
  "scores": {{
    "content_accuracy": 0,
    "language_clarity": 0,
    "logical_structure": 0,
    "innovation_depth": 0,
    "task_completeness": 0,
    "total": 0
  }}
}}
```
Evaluate objectively and provide specific justifications.
"""

def lambda_handler(event, context):
    # Available data provided in the event
    taskguid = event.get("TASKGUID", "")
    option = event.get("OPTION", 1)
    task = event.get("TASK", "")
    text = event.get("TEXT", "")
    logging.info(f"Task GUID: {taskguid},OPTION:{option}")
    
    score = evaluate_text_with_bedrock(task, text)
    
    message = f"Failed! Task sorce:{score} is not past minimum requirement"
    success_message = "The task is not past minimum requirement"

    if score >= 50:
        success_message = f"Task is completed successfully"
        message = f"Task is completed successfully with score:{score}"

    logging.info(f"success_message: {success_message}")

    combined_message = f"{taskguid}-{success_message}"

    # Encrypt the message using base64 encoding
    encrypted_message = base64.b64encode(combined_message.encode('utf-8')).decode('utf-8')

    return {
        "encrypted_message": encrypted_message,
        "message": f"{message}"
    }
   

def evaluate_text_with_bedrock(task, text):
    """
    Use AWS Bedrock to call model for text scoring
    """
    logger.info("Starting Bedrock service call")
    
    # Create Bedrock Runtime client
    bedrock_client = boto3.client(
        'bedrock-runtime',
    )
    
    # Build scoring prompt
    prompt = prompt_template_1.format(task=task, text=text)
    temperature = 0.6
    # Base inference parameters to use.
    inference_config = {"temperature": temperature,"maxTokens":4000}
    response = bedrock_client.converse(
        modelId=MODEL_ID,
        messages=[
            {
                "role": "user",
                "content":[{"text":prompt}]
            }
        ],
        inferenceConfig=inference_config,
    )

    # Parse response
    for chunk in response['output']['message']['content']:
        if 'text' in chunk:
            llm_reponse = chunk['text']
    logger.info(f"Model response: {llm_reponse}")
    score = extract_score_from_text(llm_reponse)
    return score

def extract_score_from_text(text):
    """
    Extract numeric score from model returned text
    Expected format: JSON wrapped in markdown code blocks
    """
    logger.info(f"Extracting score from text: {text[:200]}...")
    
    # Method 1: Extract JSON from markdown code blocks
    json_code_block_pattern = r'```json\s*(\{.*?\})\s*```'
    json_match = re.search(json_code_block_pattern, text, re.DOTALL)
    if json_match:
        try:
            json_str = json_match.group(1)
            json_data = json.loads(json_str)
            if 'scores' in json_data and 'total' in json_data['scores']:
                logger.info(f"Successfully extracted total score: {json_data['scores']['total']}")
                return json_data['scores']['total']
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed for code block: {e}")
    
    # Method 2: Try to parse the entire text as JSON (fallback)
    try:
        json_data = json.loads(text.strip())
        if 'scores' in json_data and 'total' in json_data['scores']:
            logger.info(f"Successfully extracted total score from raw JSON: {json_data['scores']['total']}")
            return json_data['scores']['total']
    except json.JSONDecodeError:
        logger.info("Raw JSON parsing failed, trying pattern matching")
    
    # Method 3: Look for JSON-like structure anywhere in the text
    json_pattern = r'\{[^{}]*"scores"[^{}]*"total"\s*:\s*(\d+)[^{}]*\}'
    json_match = re.search(json_pattern, text, re.DOTALL)
    if json_match:
        try:
            # Extract the full JSON object
            full_json_pattern = r'\{(?:[^{}]|{[^{}]*})*\}'
            full_match = re.search(full_json_pattern, text, re.DOTALL)
            if full_match:
                json_str = full_match.group(0)
                json_data = json.loads(json_str)
                if 'scores' in json_data and 'total' in json_data['scores']:
                    logger.info(f"Successfully extracted total score from pattern: {json_data['scores']['total']}")
                    return json_data['scores']['total']
        except json.JSONDecodeError:
            pass
    
    # Method 4: Direct pattern matching for "total": number
    total_pattern = r'"total"\s*:\s*(\d+)'
    total_match = re.search(total_pattern, text)
    if total_match:
        score = int(total_match.group(1))
        logger.info(f"Extracted total score using pattern matching: {score}")
        return score
    
    # Method 5: Look for "Total: number" or "Total Score: number" patterns
    total_text_pattern = r'(?:total|score)\s*:?\s*(\d+)'
    total_text_match = re.search(total_text_pattern, text, re.IGNORECASE)
    if total_text_match:
        score = int(total_text_match.group(1))
        logger.info(f"Extracted score using text pattern: {score}")
        return score
    
    # Method 6: Look for any number between 0-100 (assuming it's a percentage score)
    score_pattern = r'\b([0-9]{1,3})\b'
    score_matches = re.findall(score_pattern, text)
    if score_matches:
        # Take the first number that could be a valid score (0-100)
        for match in score_matches:
            score = int(match)
            if 0 <= score <= 100:
                logger.info(f"Extracted score using number pattern: {score}")
                return score
    
    # If all else fails, return 0
    logger.warning(f"Could not extract score from text: {text}")
    return 0
   