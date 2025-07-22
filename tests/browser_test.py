from strands import Agent
from strands_tools.browser import AgentCoreBrowser
from dotenv import load_dotenv
from strands.models import BedrockModel
from botocore.config import Config
import os
import time
import boto3
load_dotenv("../.env")

import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from bedrock_agentcore.tools.browser_client import BrowserClient
from bedrock_agentcore.tools.browser_client import browser_session

import sys
sys.path.append(str(Path(__file__).parent.parent))
from src.interactive_tools.browser_viewer import BrowserViewerServer

console = Console()


env = {
            'AWS_ACCESS_KEY_ID':  os.environ.get('BEDROCK_AWS_ACCESS_KEY_ID') or os.environ.get('AWS_ACCESS_KEY_ID'),
            'AWS_SECRET_ACCESS_KEY':  os.environ.get('BEDROCK_AWS_SECRET_ACCESS_KEY') or os.environ.get('AWS_SECRET_ACCESS_KEY'),
            'AWS_REGION': os.environ.get('BEDROCK_AWS_REGION') or os.environ.get('AWS_REGION'),
        }

session = boto3.Session(
                    aws_access_key_id=env['AWS_ACCESS_KEY_ID'],
                    aws_secret_access_key=env['AWS_SECRET_ACCESS_KEY'],
                    region_name=env['AWS_REGION']
                )

model = BedrockModel(
                model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                boto_session=session,
                max_tokens=5000,
                temperature=0.7,
                boto_client_config=Config(
                read_timeout=900,
                connect_timeout=900,
                retries=dict(max_attempts=3, mode="adaptive"),
                ),
            )
# try:
#     # Create browser tool
#     browser = AgentCoreBrowser(region='us-west-2')
#     agent = Agent(model=model,tools=[browser.browser])

#     result = agent('go to Amazon.com')

#     # Keep running
#     while True:
#         time.sleep(1)
# except KeyboardInterrupt:
#     # Close browser
#     print("closing browser")
#     agent.tool.browser({"action":{"type":"close", "session_name":""}})



def live_view_with_nova_act(prompt, starting_page, nova_act_key, region="us-west-2"):
    """Run the browser live viewer with display sizing."""
    console.print(
        Panel(
            "[bold cyan]Browser Live Viewer[/bold cyan]\n\n"
            "This demonstrates:\n"
            "• Live browser viewing with DCV\n"
            "• Configurable display sizes (not limited to 900×800)\n"
            "• Proper display layout callbacks\n\n"
            "[yellow]Note: Requires Amazon DCV SDK files[/yellow]",
            title="Browser Live Viewer",
            border_style="blue",
        )
    )
    result = None
    try:
        # Step 1: Create browser session
        with browser_session(region) as client:
            ws_url, headers = client.generate_ws_headers()

            # Step 2: Start viewer server
            console.print("\n[cyan]Step 3: Starting viewer server...[/cyan]")
            viewer = BrowserViewerServer(client, port=8000)
            viewer_url = viewer.start(open_browser=True)

            # Step 3: Show features
            console.print("\n[bold green]Viewer Features:[/bold green]")
            console.print(
                "• Default display: 1600×900 (configured via displayLayout callback)"
            )
            console.print("• Size options: 720p, 900p, 1080p, 1440p")
            console.print("• Real-time display updates")
            console.print("• Take/Release control functionality")

            console.print("\n[yellow]Press Ctrl+C to stop[/yellow]")

            # Step 4: Use Nova Act to interact with the browser
            with NovaAct(
                cdp_endpoint_url=ws_url,
                cdp_headers=headers,
                preview={"playwright_actuation": True},
                nova_act_api_key=nova_act_key,
                starting_page=starting_page,
            ) as nova_act:
                result = nova_act.act(prompt)
                console.print(f"\n[bold green]Nova Act Result:[/bold green] {result}")

    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
    finally:
        console.print("\n\n[yellow]Shutting down...[/yellow]")
        if "client" in locals():
            client.stop()
            console.print("✅ Browser session terminated")
    return result


if __name__ == "__main__":
    import argparse
    from nova_act import NovaAct
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True, help="Browser Search instruction")
    parser.add_argument("--starting-page", required=True, help="Starting URL")
    parser.add_argument("--region", default="us-west-2", help="AWS region")
    args = parser.parse_args()
    nova_act_key = os.environ.get("NOVA_ACT_API_KEY")
    result = live_view_with_nova_act(
        args.prompt, args.starting_page, nova_act_key, "us-west-2"
    )

    console.print(f"\n[bold green]Nova Act Result:[/bold green] {result}")