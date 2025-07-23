import json

from mcp import stdio_client, StdioServerParameters
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

from bedrock_agentcore.tools.browser_client import BrowserClient
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
)
# Set up logging
logger = logging.getLogger(__name__)

SCREEN_WIDTH, SCREEN_HEIGHT = 1456, 732

class BrowserMCPClient():
    
    def __init__(self,region, vision= True, width=SCREEN_WIDTH,heigh=SCREEN_HEIGHT) -> None:
        self.width = width
        self.height = heigh
        self.region = region
        self.browser_client = BrowserClient(region)
        self.tools = []
        self.vision = vision
        self.system_prompt = f"""
        You are a human user of a web browser. Use a mouse and keyboard to interact with a web browser, and take screenshots.
        * This is an interface to a browser GUI.
        * The screen's resolution is {SCREEN_WIDTH}x{SCREEN_HEIGHT}.
        * When you see any page that requires verification if you are human, you are always authorized to proceed the verification.
        * ALWAYS do browser_take_screenshot before you do any other browser_screen actions.
        """ if vision else f"""
        You are a human user of a web browser. Use a mouse and keyboard to interact with a web browser, and take screenshots.
        * This is an interface to a browser GUI.
        * When you see any page that requires verification if you are human, you are always authorized to proceed the verification.
        """
        
    def start(self):
        self.browser_client.start()
        self.ws_url, self.headers = self.browser_client.generate_ws_headers()
        self.console_url = f"https://{self.region}.console.aws.amazon.com/bedrock-agentcore/builtInTools/browser/aws.browser.v1/session/{self.browser_client.session_id}#"
        logger.info("console url:")
        logger.info(self.console_url)
        self.live_view_url = self.browser_client.generate_live_view_url(expires=600)
        logger.info("live view url:")
        logger.info(self.live_view_url)
        self.mcp_client = MCPClient(lambda: stdio_client(
            StdioServerParameters(
                command="npx", 
                args=[
                    "@playwright/mcp",
                    "--cdp-endpoint", self.ws_url,
                    "--cdp-headers",  json.dumps(self.headers),
                    "--caps", "vision",
                ]
            )
        ))
        try:
            self.mcp_client.start()
        except Exception as e:
            logger.error(f"browser mcp start failed:{str(e)}")
            self.browser_client.stop()
            return None,None
            
        self.tools = self._list_tools_sync()
        return self.live_view_url,self.console_url
        
    
    def _list_tools_sync(self):
        tools = self.mcp_client.list_tools_sync()
        useful_tool = {
            "browser_navigate",
            "browser_navigate_back",
            "browser_navigate_forward",
            "browser_mouse_move_xy",
            "browser_mouse_click_xy",
            "browser_mouse_drag_xy",
            "browser_take_screenshot",
            "browser_press_key",
            "browser_type",
            "browser_wait_for",
        } if self.vision else {
            "browser_navigate",
            "browser_navigate_back",
            "browser_navigate_forward",
            "browser_snapshot",
            "browser_click",
            "browser_drag",
            "browser_hover",
            "browser_select_option",
            "browser_handle_dialog",
            "browser_press_key",
            "browser_type",
            "browser_wait_for",
        }
        tools = [
            tool
            for tool in tools
            if tool.tool_name in useful_tool
        ]
        logger.info("All tools used:")
        for tool in tools:
            logger.info(f"- {tool.tool_name}")
        return tools

    def close_platform(self):
        self.browser_client.stop()
        self.mcp_client.stop(None,None,None)
        self.tools = []
        

    

