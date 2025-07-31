"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
SPDX-License-Identifier: MIT-0
"""
import os
from dotenv import load_dotenv
from custom_tools.agent_core_memory import AgentCoreMemoryToolProvider
from strands import Agent

import pandas as pd
from constant import *
load_dotenv()  # load environment variables from .env
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
)
logger = logging.getLogger(__name__)
class ChatClient:
    """chat wrapper"""
    def __init__(self, credential_file='',user_id='', access_key_id='', secret_access_key='', region=''):
        self.env = {
            'AWS_ACCESS_KEY_ID': access_key_id or os.environ.get('BEDROCK_AWS_ACCESS_KEY_ID') or os.environ.get('AWS_ACCESS_KEY_ID'),
            'AWS_SECRET_ACCESS_KEY': secret_access_key or os.environ.get('BEDROCK_AWS_SECRET_ACCESS_KEY') or os.environ.get('AWS_SECRET_ACCESS_KEY'),
            'AWS_REGION': region or os.environ.get('BEDROCK_AWS_REGION') or os.environ.get('AWS_REGION'),
        }
        
        # self.max_history = int(os.environ.get('MAX_HISTORY_TURN',5))*2
        self.messages = [] # History messages without system message
        self.system = None
        self.agent = None
        self.user_id = user_id
        SESSION_ID = user_id
        if memory_id:=os.environ.get("MEMORY_ID"):
            self.memory_provider = AgentCoreMemoryToolProvider(
                            memory_id=memory_id,
                            actor_id=user_id,
                            session_id=SESSION_ID,
                            region=os.environ.get("AGENTCORE_REGION","us-west-2")
                            )
            logger.info(f"Initialized AgentCoreMemoryToolProvider with memory id:{memory_id}")
        else:
            self.memory_provider = None
    
    async def clear_history(self):
        """clear session message of this client"""
        self.messages = []
        self.system = None
        self.agent = None
        # 如果是其他类型的multiagent则直接设置成空
        # if not isinstance(self.agent,Agent):
        #     self.agent = None
        # elif self.agent:
        #     self.agent.messagas = []
        if self.memory_provider:
            self.memory_provider.delete_all_events(self.user_id)
    
    async def save_history(self):
        pass
        return 
    
        # use agentcore memory instead
        # if self.agent:
        #     self.messages = self.agent.messages
        #     if DDB_TABLE:
        #         await save_user_message(self.user_id,self.messages)
            
    async def load_history(self):
        pass
        return []
        # use agentcore memory instead
        # if DDB_TABLE:
        #     return await get_user_message(self.user_id)
        # else:
        #     return self.messages 

            
    
