CLAUDE_37_SONNET_MODEL_ID = 'anthropic.claude-3-7-sonnet-20250219-v1:0'
CLAUDE_4_SONNET_MODEL_ID = 'anthropic.claude-sonnet-4-20250514-v1:0'
CLAUDE_4_OPUS_MODEL_ID = 'anthropic.claude-opus-4-20250514-v1:0'
CLAUDE_35_HAIKU_MODEL_ID = 'anthropic.claude-3-5-haiku-20241022-v1:0'
CLAUDE_35_SONNET_MODEL_ID = 'anthropic.claude-3-5-sonnet-20241022-v2:0'
CLAUDE_45_SONNET_MODEL_ID = 'anthropic.claude-sonnet-4-5-20250929-v1:0'
NOVA_RPO_MODEL_ID = 'us.amazon.nova-pro-v1:0'
NOVA_LITE_MODEL_ID = 'us.amazon.nova-lite-v1:0'

def is_claude_thinking(model_id):
    return  ( CLAUDE_37_SONNET_MODEL_ID in model_id 
            or CLAUDE_4_SONNET_MODEL_ID in model_id 
            or CLAUDE_4_OPUS_MODEL_ID in model_id
            or CLAUDE_45_SONNET_MODEL_ID in model_id )
    
def is_interleaved_claude_thinking(model_id):
    return ( CLAUDE_4_SONNET_MODEL_ID in model_id 
            or CLAUDE_4_OPUS_MODEL_ID in model_id
            or CLAUDE_45_SONNET_MODEL_ID in model_id )
    
def is_prompt_cache(model_id):
    return  ( CLAUDE_37_SONNET_MODEL_ID in model_id 
        or CLAUDE_4_SONNET_MODEL_ID in model_id 
        or CLAUDE_4_OPUS_MODEL_ID in model_id
        or CLAUDE_45_SONNET_MODEL_ID in model_id )