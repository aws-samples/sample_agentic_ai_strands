from browser_use import Agent as BrowserUseAgent
from browser_use import Controller
from browser_use.browser.types import ViewportSize
from browser_use.browser.session import BrowserSession
from bedrock_agentcore.tools.browser_client import BrowserClient
from browser_use.browser import BrowserProfile
# from browser_use.llm import ChatAWSBedrock
from langchain_aws import ChatBedrockConverse
from contextlib import suppress
import asyncio
from strands import tool
from strands.types.tools import AgentTool
import sys
from boto3.session import Session
import os
from typing import Optional,Dict,List
from pydantic import BaseModel
import time
import logging
# sys.path.append("../interactive_tools")
from .interactive_tools.browser_viewer import BrowserViewerServer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
)
# Set up logging
logger = logging.getLogger(__name__)

SCREEN_WIDTH, SCREEN_HEIGHT = 1366, 768

class Content(BaseModel):
    title: str
    content: str
    url: str

controller = Controller(output_model=Content)

async def run_browser_task(
    browser_session: BrowserSession, llm: ChatBedrockConverse,use_vision:bool, task: str
) -> str:
    """
    Run a browser automation task using browser_use

    Args:
        browser_session: Existing browser session to reuse
        bedrock_chat: Bedrock chat model instance
        task: Natural language task for the agent
        
    """
    try:
        # Create and run the agent
        agent = BrowserUseAgent(task=task,controller=controller, llm=llm,use_vision=use_vision, browser_session=browser_session)
        history = await agent.run()
        result = history.final_result()
        if result:
            content: Content = Content.model_validate_json(result)

            logger.info('\n--------------------------------')
            logger.info(f'Title:            {content.title}')
            logger.info(f'URL:              {content.url}')
            logger.info(f'Content:         {content.content}')
            return result
        else:
            logger.info('No result')
            return "No result"
        
    except Exception as e:
        logger.error(f"❌ Error during task execution:[/bold red] {str(e)}")
        import traceback
        traceback.print_exc()
        

async def live_view_with_browser_use(prompt,client:BrowserClient, model_id:str , use_vision: bool, region:str):
    """
    Main function that demonstrates live browser viewing with Agent automation.

    Workflow:
    1. Creates Amazon Bedrock AgentCore browser client in us-west-2 region
    2. Waits for browser initialization (10-second required delay)
    3. Starts DCV-based live viewer server on port 8000 with browser control
    4. Configures multiple display size options (720p to 1440p)
    5. Establishes browser session for AI agent automation via CDP WebSocket
    6. Executes AI-driven tasks using Claude 3.5 Sonnet model
    7. Properly closes all sessions and stops browser client

    Features:
    - Real-time browser viewing through web interface
    - Manual take/release control functionality
    - AI automation with browser-use library
    - Configurable display layouts and sizes
    """
    result = ""
    try:
        # Step 1: Create browser session        
        ws_url, headers = client.generate_ws_headers()

        # Step 2: Start viewer server
        logger.info("tarting viewer server...")

        # Step 4: Use browser-use to interact with browser
        # Create persistent browser session and model
        browser_session = None
        try:
            # Create browser profile with headers
            browser_profile = BrowserProfile(
                headers=headers,
                timeout=1500000,  # 150 seconds timeout
                window_size={'width': SCREEN_WIDTH, 'height': SCREEN_HEIGHT}
            )

            # Create a browser session with CDP URL and keep_alive=True for persistence
            t1 = time.time()
            browser_session = BrowserSession(
                cdp_url=ws_url,
                browser_profile=browser_profile,
                keep_alive=True,  # Keep browser alive between tasks
            )
            logging.info(f"Browser session created in {time.time() - t1} seconds")

            # Initialize the browser session
            await browser_session.start()

            # Create ChatBedrockConverse once
            llm = ChatBedrockConverse(
                model_id=model_id,
                region_name=region,
            )
            logger.debug(
                "[green]✅ Browser session initialized and ready for tasks[/green]\n"
            )


            result = await run_browser_task(browser_session, llm, use_vision, prompt)

        finally:
            # Close the browser session
            if browser_session:
                logger.debug("\n[yellow]🔌 Closing browser session...[/yellow]")
                with suppress(Exception):
                    await browser_session.close()
                logger.debug("[green]✅ Browser session closed[/green]")

    except Exception as e:
        logger.debug(f"\n[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()

    finally:
        return result
        # if "client" in locals():
        #     client.stop()


class BrowserUseTool:
    
    def __init__(self,region:str,model_id:str, use_vision:bool=True):
        self.region = region
        self.model_id = model_id
        self.client = None
        self.viewer_url = None
        self.use_vision = use_vision
    
    @property
    def tools(self) -> List[AgentTool]:
        """Extract all @tool decorated methods from this instance."""
        tools = []

        for attr_name in dir(self):
            if attr_name == "tools":
                continue
            attr = getattr(self, attr_name)
            # Also check the original way for regular AgentTool instances
            if isinstance(attr, AgentTool):
                tools.append(attr)

        return tools
    
    def close_platform(self):
        if self.client:
            self.client.stop()
            self.client = None
            self.viewer_url = None
            logger.info("Browser client stopped")
        
    @tool
    def browser_init(self) -> str:
        """
        Initialize the browser client, before use browser tool
        """
        logger.info(f"BrowserUseTool: browser_init")
        if self.client is None:
            self.client = BrowserClient(self.region)
            self.client.start()
            viewer = BrowserViewerServer(self.client, port=8000)
            self.viewer_url = viewer.start(open_browser=True)
            return "Browser client initialized"
        else:
            return "Browser client has already initialized"
    @tool
    def browse(self,task:str) -> str: 
        """
        This tool will delegate the task to an agent that can run a browser automation task using browsers, please make sure to initialize the browser client ahead.

        Args:
            task: Natural language task for the agent
            
        Returns:
            the task result defined in a structured json with title, url, content
        """
        logger.info(f"BrowserUseTool: {task}")
        if self.client is None:
            ret = self.browser_init()
            logger.info(ret)

        
        result = asyncio.run(live_view_with_browser_use(prompt=task, client=self.client, model_id = self.model_id, use_vision=self.use_vision, region = self.region))
        return result

if __name__ == "__main__":
    browser = BrowserUseTool('us-west-2',model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0")
    browser.browser_init()
    browser.browse(task="find the top 1 sales bluetooth headphones in Amazon")
    browser.close_platform()
    