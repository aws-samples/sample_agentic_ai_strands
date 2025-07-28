"""
Deep Research Swarm Team
A specialized multi-agent system for comprehensive research tasks using Strands Agents framework.
"""

import logging
from strands import Agent
from strands.multiagent import Swarm
from strands.types.content import ContentBlock
import asyncio
from typing import AsyncIterator,Dict,Any,Union
import json
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
)

class DeepResearchSwarm:
    """
    A specialized swarm for conducting deep research across multiple domains.
    """
    
    def __init__(self,model="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                 agent_hooks=[],
                 tools=[],
                 system_prompt=None,
                 callback_handler = None):
        self.callback_handler = callback_handler
        self.model = model
        self.agent_hook = agent_hooks
        self.tools = tools
        self.system_prompt = system_prompt
        self.agents = self._create_research_agents()
        self.swarm = self._create_swarm()
        
    
    def _create_research_agents(self):
        """Create specialized research agents with distinct roles."""
        original_system_prompt = f"""
        Here is the original system prompt setting from user:
        {self.system_prompt}
        """
        # Primary Research Coordinator
        research_coordinator = Agent(
            model=self.model,
            hooks=self.agent_hook,
            callback_handler = self.callback_handler,
            tools = self.tools,
            name="research_coordinator",
            system_prompt=f"""You are the Research Coordinator, responsible for:
            - Breaking down complex research topics into manageable subtasks
            - Coordinating between different research specialists
            - Synthesizing findings from multiple agents
            - Ensuring comprehensive coverage of the research topic
            - Identifying knowledge gaps and directing further investigation
            
            When you receive a research request, analyze it and delegate specific aspects 
            to appropriate specialists. Always maintain an overview of the entire research process.
            
            {original_system_prompt}
            """,
            load_tools_from_directory=False
        )
        
        # Academic Research Specialist
        academic_researcher = Agent(
            model=self.model,
            hooks=self.agent_hook,
            callback_handler = self.callback_handler,
            tools = self.tools,
            name="academic_researcher",
            system_prompt=f"""You are an Academic Research Specialist focused on:
            - Finding and analyzing peer-reviewed academic papers
            - Identifying key researchers and institutions in the field
            - Understanding theoretical frameworks and methodologies
            - Tracking citation networks and research trends
            - Evaluating research quality and credibility
            
            Provide rigorous, evidence-based analysis with proper citations.
            Focus on scholarly sources and academic perspectives.
            
            {original_system_prompt}
            """
        )
        
        # Industry Intelligence Analyst
        industry_analyst = Agent(
            model=self.model,
            hooks=self.agent_hook,
            callback_handler = self.callback_handler,
            tools = self.tools,
            name="industry_analyst",
            system_prompt=f"""You are an Industry Intelligence Analyst specializing in:
            - Market research and competitive analysis
            - Industry trends and business applications
            - Commercial implementations and case studies
            - Regulatory and policy implications
            - Economic impact and market opportunities
            
            Focus on practical applications, business value, and real-world implementations.
            Analyze market dynamics and commercial viability.
            
            {original_system_prompt}
            """
        )
        
        # Technical Deep-Dive Specialist
        technical_specialist = Agent(
            model=self.model,
            hooks=self.agent_hook,
            callback_handler = self.callback_handler,
            tools = self.tools,
            name="technical_specialist",
            system_prompt=f"""You are a Technical Deep-Dive Specialist responsible for:
            - Analyzing technical specifications and implementations
            - Understanding system architectures and design patterns
            - Evaluating performance metrics and benchmarks
            - Identifying technical challenges and limitations
            - Exploring emerging technologies and innovations
            
            Provide detailed technical analysis with focus on implementation details,
            performance characteristics, and technical feasibility.
            
            {original_system_prompt}
            """
        )
        
        # Data Mining & Analytics Expert
        data_analyst = Agent(
            model=self.model,
            hooks=self.agent_hook,
            callback_handler = self.callback_handler,
            tools = self.tools,
            name="data_analyst",
            system_prompt=f"""You are a Data Mining & Analytics Expert focused on:
            - Collecting and analyzing quantitative data
            - Identifying patterns and statistical trends
            - Creating data visualizations and insights
            - Validating findings through data analysis
            - Performing comparative analysis across datasets
            
            Use data-driven approaches to support research findings.
            Focus on metrics, statistics, and quantitative validation.
            
            {original_system_prompt}
            """
        )
        
        # Synthesis & Report Writer
        synthesis_writer = Agent(
            model=self.model,
            hooks=self.agent_hook,
            callback_handler = self.callback_handler,
            tools = self.tools,
            name="synthesis_writer",
            system_prompt=f"""You are a Synthesis & Report Writer responsible for:
            - Integrating findings from all research specialists
            - Creating comprehensive, well-structured reports
            - Identifying key insights and implications
            - Highlighting contradictions or gaps in research
            - Presenting findings in clear, accessible language
            
            Create executive summaries, detailed reports, and actionable recommendations.
            Ensure all perspectives are represented and properly attributed.
            
            {original_system_prompt}
            """
        )
        
        # Fact Checker & Validator
        fact_checker = Agent(
            model=self.model,
            hooks=self.agent_hook,
            callback_handler = self.callback_handler,
            tools = self.tools,
            name="fact_checker",
            system_prompt=f"""You are a Fact Checker & Validator focused on:
            - Verifying claims and statements made by other agents
            - Cross-referencing information across multiple sources
            - Identifying potential biases or inaccuracies
            - Ensuring research integrity and reliability
            - Flagging outdated or questionable information
            
            Maintain high standards for accuracy and reliability.
            Challenge assumptions and verify all significant claims.
            
            handoff to 'synthesis_writer' to incooperate all your inputs and let't him to write the final report
            
            {original_system_prompt}
            """
        )
        
        return {
            "research_coordinator": research_coordinator,
            "academic_researcher": academic_researcher,
            "industry_analyst": industry_analyst,
            "technical_specialist": technical_specialist,
            "data_analyst": data_analyst,
            "synthesis_writer": synthesis_writer,
            "fact_checker": fact_checker
        }
    
    def _create_swarm(self):
        """Create the research swarm with appropriate configuration."""
        return Swarm(
            list(self.agents.values()),
            max_handoffs=30,  # Allow more handoffs for complex research
            max_iterations=40,  # More iterations for thorough investigation
            execution_timeout=1800.0,  # 30 minutes for deep research
            node_timeout=600.0,  # 10 minutes per agent
            repetitive_handoff_detection_window=10, # There must be >= 4 unique agents in the last 10 handoffs
            repetitive_handoff_min_unique_agents=4
        )
        
    async def stream_async(self, prompt: Union[str, list[ContentBlock]], **kwargs: Any) -> AsyncIterator[Any]:
        """
        Stream research results as they become available.
        
        Args:
            prompt: Research topic/question as string or list of ContentBlocks
            **kwargs: Additional parameters like research_depth, specific_focus
        
        Yields:
            Dict: Streaming events with type and data
        """
        # Extract parameters from kwargs
        research_depth = kwargs.get("research_depth", "comprehensive")
        specific_focus = kwargs.get("specific_focus", None)
        
        # Handle different prompt types
        if isinstance(prompt, list):
            # If it's a list of ContentBlocks, extract text from the first text block
            topic = None
            for block in prompt:
                if hasattr(block, 'text') and block.text:
                    topic = block.text
                    break
            if not topic:
                topic = str(prompt[0]) if prompt else "Research request"
        else:
            topic = str(prompt)
        
        
        stream_queue = kwargs.get("stream_queue", None)
                
        def emit(event):
            if stream_queue:
                stream_queue.put(event)
            else:
                logger.info(event)
            
        def stream_callback(**kwargs):
            if 'message' in kwargs:
                message = kwargs['message']
                if message.get('role') == 'user' and message.get('content'):
                    content = message['content']
                    for content_block in content:
                        if 'toolResult' in content_block:
                            toolUseId = content_block['toolResult']['toolUseId']
                            emit({"type": "toolResult", "toolUseId":toolUseId,"data": content_block['toolResult']})
                    
            elif 'event' in kwargs:
                event = kwargs['event']
                # logger.info(event)
                # Handle message start
                if "messageStart" in event:
                    emit({"type": "message_start", "data": event["messageStart"]})
                    
                # Handle content block start
                if "contentBlockStart" in event:
                    block_start = event["contentBlockStart"]
                    emit({"type": "block_start", "data": block_start})              

                # Handle content block delta
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"]
                    emit({"type": "block_delta", "data": delta})  

                # Handle content block stop
                if "contentBlockStop" in event:
                    emit({"type": "block_stop", "data": event["contentBlockStop"]})   

                # Handle message stop
                if "messageStop" in event:
                    # need to ignore the end turn flog for the agent, unless the final result is done
                    if not event["messageStop"].get("stopReason") == "end_turn":
                        emit({"type": "message_stop", "data": event["messageStop"]})     

                # Handle metadata
                if "metadata" in event:
                    emit({"type": "metadata", "data": event["metadata"]})
        
        for agent in list(self.agents.values()):
            agent.callback_handler =  stream_callback         
        
        try:
            # Execute the research
            result = await self.research(
                topic=topic,
                research_depth=research_depth,
                specific_focus=specific_focus
            )
            logger.info(f"Swarm Research completed with: {result.status}")
            emit({"type": "message_stop", "data": {"stopReason":"end_turn"}})  
                
        except Exception as e:
            logger.error(f"Error during streaming research: {e}")
            yield {
                "type": "error",
                "data": {
                    "message": f"An error occurred during swarm execution:{str(e)}"
                }
            }
        
    
    async def research(self, topic, research_depth="comprehensive", specific_focus=None):
        """
        Conduct deep research on a given topic.
        
        Args:
            topic (str): The research topic or question
            research_depth (str): "overview", "detailed", or "comprehensive"
            specific_focus (list): Specific aspects to focus on
        """
        
        # Construct the research prompt
        prompt_parts = [f"Conduct {research_depth} research on: {topic}"]
        
        if specific_focus:
            prompt_parts.append(f"Pay special attention to: {', '.join(specific_focus)}")
        
        prompt_parts.extend([
            "\nResearch Requirements:",
            "1. Academic perspective with peer-reviewed sources",
            "2. Industry analysis with market insights",
            "3. Technical deep-dive with implementation details",
            "4. Data-driven analysis with quantitative insights",
            "5. Comprehensive synthesis with actionable recommendations",
            "6. Fact-checking and validation of all claims",
            "\nDeliver a structured report with executive summary, detailed findings, and recommendations."
        ])
        
        research_prompt = "\n".join(prompt_parts)
        
        # Execute the swarm
        result = await self.swarm.invoke_async(research_prompt)
        
        return result
    
    def research_with_context(self, topic, context_files=None, images=None):
        """
        Conduct research with additional context (files, images, etc.)
        
        Args:
            topic (str): The research topic
            context_files (list): List of file paths to include as context
            images (list): List of image data to analyze
        """
        
        content_blocks = [ContentBlock(text=f"Research topic: {topic}")]
        
        # Add file context if provided
        if context_files:
            for file_path in context_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        content_blocks.append(
                            ContentBlock(text=f"Context from {file_path}:\n{content}")
                        )
                except Exception as e:
                    print(f"Warning: Could not read {file_path}: {e}")
        
        # Add image context if provided
        if images:
            for img_data in images:
                content_blocks.append(
                    ContentBlock(image={"format": "png", "source": {"bytes": img_data}})
                )
        
        # Execute with multi-modal input
        result = self.swarm(content_blocks)
        
        return result
    
    def get_research_summary(self, result):
        """Extract and format a summary from the swarm result."""
        if result.status == "COMPLETED":
            summary = {
                "status": result.status,
                "agents_involved": [node.node_id for node in result.node_history],
                "total_iterations": result.execution_count,
                "execution_time_ms": result.execution_time,
                "token_usage": result.accumulated_usage,
                "final_result": result.result
            }
            
            # Extract results from specific agents if available
            agent_results = {}
            for agent_name in self.agents.keys():
                if agent_name in result.results:
                    agent_results[agent_name] = result.results[agent_name].result
            
            summary["agent_contributions"] = agent_results
            
            return summary
        else:
            return {"status": result.status, "error": "Research incomplete"}


# def message_buffer_handler(**kwargs):
#     # When a new message is created from the assistant, print its content
#      # Track tool usage
#     if "message" in kwargs and kwargs["message"].get("role") == "assistant":
#         print(json.dumps(kwargs["message"], indent=2))
# def event_queue_handler(**kwargs):
#     ## put the  event in a queue
#     event_queue.put(kwargs["event"])

async def main():
    """Example usage of the Deep Research Swarm."""
    
    # Create the research swarm
    research_team = DeepResearchSwarm(callback_handler=None)
    
    # Example 1: Basic research
    # print("=== Example 1: Basic Research ===")
    # result = await research_team.research(
    #     topic="The impact of artificial intelligence on software development practices",
    #     research_depth="comprehensive",
    #     specific_focus=["developer productivity", "code quality", "job market implications"]
    # )
    
   
    # summary = research_team.get_research_summary(result)
    # print(f"Research Status: {summary['status']}")
    # print(f"Agents Involved: {summary['agents_involved']}")
    # print(f"Final Result Preview: {summary['final_result'][:500]}...")
    
    # Example 2: Research with context files
    # print("\n=== Example 2: Research with Context ===")
    # This would work if you have context files
    # result = research_team.research_with_context(
    #     topic="Analysis of our current system architecture",
    #     context_files=["system_docs.md", "api_spec.json"]
    # )
    
    # Example 3: Streaming research
    print("\n=== Example 3: Streaming Research ===")
    async for event in research_team.stream_async(
        "The impact of AI on software development",
        research_depth="comprehensive",
        specific_focus=["developer productivity", "code quality"]
    ):
        print(event)        


if __name__ == "__main__":
    asyncio.run(main())