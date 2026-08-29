from google.adk.agents import Agent
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from .prompts import EXTRACTION_INSTRUCTION, RESEARCH_RULE
from .tools import save_prices, lookup_container, save_container

research_agent = Agent(
    name="research_container",
    model="gemini-3.5-flash",
    description=(
        "Searches the web for how much a Nigerian market container holds "
        "of a given commodity, in kilograms."
    ),
    instruction=(
        "You research Nigerian market container capacities. Use google_search "
        "to find how many kilograms of the given commodity a container holds. "
        "Report every distinct figure you find and where it came from. "
        "Do NOT average or pick a winner - report the raw disagreement. "
        "If you find nothing, say so plainly. Never guess."
    ),
    tools=[google_search],
)

WORKFLOW = EXTRACTION_INSTRUCTION + """

## After extraction — do this without being asked
1. Call save_prices with your extracted records.
2. The result lists unresolved_containers. For each, call lookup_container.
3. If not_found, call research_container to find real figures.
4. Reconcile the figures it returns: state the disagreement, pick a
   defensible value, explain why. Confidence reflects how much the
   sources disagreed.
5. Call save_container with the value, the real conflicting_values, and
   your reasoning.
6. Report briefly what you saved and resolved.

A painter and a custard bucket hold the same VOLUME regardless of contents
but different WEIGHTS by commodity. Rice and garri differ in density.
Always research container plus commodity together.
""" + RESEARCH_RULE

root_agent = Agent(
    name="price_agent",
    model="gemini-3.5-flash",
    description="Extracts, stores and reconciles Nigerian market price data.",
    instruction=WORKFLOW,
    tools=[
        save_prices,
        lookup_container,
        save_container,
        AgentTool(agent=research_agent),
    ],
)
