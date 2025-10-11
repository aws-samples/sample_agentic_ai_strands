import logging
import json
import os
from typing import Dict
from datetime import datetime
from botocore.exceptions import ClientError
from strands import Agent, tool
from strands.hooks import AfterInvocationEvent, HookProvider, HookRegistry, MessageAddedEvent,AgentInitializedEvent
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.constants import StrategyType
from bedrock_agentcore.memory import MemoryClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
)
logger = logging.getLogger(__name__)


class AgentMemoryHooks(HookProvider):
    """Memory hooks for agent"""
    
    def __init__(self, memory_id: str, actor_id: str, session_id: str, recent_turns:int = 5):
        self.memory_id = memory_id
        self.memory_client = MemoryClient(region_name=os.environ.get("AGENTCORE_REGION","us-west-2"))
        self.actor_id = actor_id
        self.session_id = session_id
        self.recent_turns = recent_turns

        # Helper function to get namespaces from memory strategies list
    def get_namespaces(self) -> Dict:
        """Get namespace mapping for memory strategies."""
        strategies = self.memory_client.get_memory_strategies(self.memory_id)
        return {i["type"]: i["namespaces"][0].format(actorId=self.actor_id ) for i in strategies}
                
    def on_agent_initialized(self, event: AgentInitializedEvent):
        """Load recent conversation history when agent starts"""
        try:
            # Load the last 5 conversation turns from memory
            recent_turns = self.memory_client.get_last_k_turns(
                memory_id=self.memory_id,
                actor_id=self.actor_id,
                session_id=self.session_id,
                k=self.recent_turns
            )
            logger.info(f"✅ Loaded {len(recent_turns)} conversation turns:{recent_turns}")

            if recent_turns:
                # Format conversation history for context
                context_messages = []
                for turn in reversed(recent_turns):
                    last_role = ""
                    for message in turn:
                        role = message['role'].lower()
                        text = message['content']['text']
                        if last_role != role:
                            last_role = role
                            context_messages.append({"role":role,"content":[{'text':text}]})
                        else:#append to the exsting blocks
                            context_messages[-1]['content'].append({'text':text})
                            
                
                event.agent.messages = context_messages
                logger.info(f"✅ Initialized {len(context_messages)} conversation turns:{context_messages}")
                # Add context to agent's system prompt.
                # event.agent.system_prompt += f"\n\nRecent conversation:\n{context}"
                
        except Exception as e:
            logger.error(f"Memory load error: {e}")
    
    def on_message_added(self, event: MessageAddedEvent):
        """Store messages in memory"""
        messages = event.agent.messages
        # logger.info(f"on_message_added:{messages[-1]}")
        # only add text messages
        if "text" in messages[-1]["content"][0]:
            try:
                self.memory_client.create_event(
                    memory_id=self.memory_id,
                    actor_id=self.actor_id,
                    session_id=self.session_id,
                    messages=[(messages[-1]["content"][0]["text"], messages[-1]["role"])]
                )
            except Exception as e:
                logger.error(f"Memory save error: {e}")
    
    
    def save_conversations(self, event: AfterInvocationEvent):
        """Save all after agent response"""
        try:
            messages = event.agent.messages
            if len(messages) >= 2 and messages[-1]["role"] == "assistant":
                # Get last customer query and agent response
                customer_query = None
                agent_response = None
                
                for msg in reversed(messages):
                    if msg["role"] == "assistant" and not agent_response:
                        # only add text messages
                        agent_response = '\n'.join([block['text'] for block in msg["content"] if 'text' in block])
                    elif msg["role"] == "user" and not customer_query:
                        customer_query = '\n'.join([block['text'] for block in msg["content"] if 'text' in block])
                        break
                
                if customer_query and agent_response:
                    # Save the support interaction
                    self.memory_client.create_event(
                        memory_id=self.memory_id,
                        actor_id=self.actor_id,
                        session_id=self.session_id,
                        messages=[(customer_query, "USER"), (agent_response, "ASSISTANT")]
                    )
                    logger.info("Saved interaction to memory")
                    
        except Exception as e:
            logger.error(f"Failed to save interaction: {e}")
    
    def register_hooks(self, registry: HookRegistry) -> None:
        """Register agent memory hooks"""
        # registry.add_callback(MessageAddedEvent, self.retrieve_user_context)
        # 
        # Register memory hooks
        registry.add_callback(AfterInvocationEvent, self.save_conversations)
        # registry.add_callback(MessageAddedEvent, self.on_message_added)
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)
        logger.info("agent memory hooks registered")