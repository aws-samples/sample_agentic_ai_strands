from strands.hooks import HookProvider,HookRegistry,AfterToolCallEvent,MessageAddedEvent,BeforeModelCallEvent
import logging
from strands.models import BedrockModel

# 配置日志格式
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class StrandsInterceptor(HookProvider):
    def __init__(self):
        super().__init__()
        
    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeModelCallEvent,self.add_message_cache)
        logger.info("registry add_message_cache")

    def add_message_cache(self, event:BeforeModelCallEvent) -> None:
        if isinstance(event.agent.model,BedrockModel) and event.agent.model.get_config().get('cache_prompt'):
            logger.info("add cache for messages")
            for message in event.agent.messages:
                content = message['content']
                if any(['cachePoint' in block for block in content]):
                    content = content[:-1]
                    message['content'] = content
            
            #add prompt cache to last message
            if event.agent.messages:
                event.agent.messages[-1]['content'] += [{
                    "cachePoint": {
                        "type": "default"
                    }
                }]