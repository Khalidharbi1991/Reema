#!/usr/bin/env python3
"""Script to have each REEMA agent introduce themselves."""

import asyncio
import os
from anthropic import Anthropic

# Get API key from environment
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    print("Error: ANTHROPIC_API_KEY environment variable not set")
    exit(1)

client = Anthropic(api_key=api_key)

# Define each agent's personality and expertise
agents = {
    "Abdullah": {
        "role": "Leader/Orchestrator Agent",
        "responsibilities": [
            "Coordinate all worker agents",
            "Manage workflow and task distribution",
            "Perform final quality control",
            "Assemble final SOP documents"
        ],
        "personality": "Strategic, organized, leadership-focused"
    },
    "Taif": {
        "role": "Research Agent",
        "responsibilities": [
            "Gather ITIL and ITOM information",
            "Research IT industry best practices",
            "Parse ITOM.pdf knowledge base",
            "Identify process requirements and standards"
        ],
        "personality": "Analytical, detail-oriented, knowledge-focused"
    },
    "Mohammad": {
        "role": "Standards & Compliance Agent",
        "responsibilities": [
            "Ensure ITIL, ISO 20000, ISO 27001 compliance",
            "Validate regulatory requirements",
            "Map processes to standard frameworks",
            "Identify mandatory compliance elements"
        ],
        "personality": "Precise, compliance-focused, regulatory expert"
    },
    "Saad": {
        "role": "Content Generation Agent",
        "responsibilities": [
            "Write comprehensive 15-30 page SOPs",
            "Create detailed procedures and workflows",
            "Develop RACI matrices",
            "Generate all 11 SOP sections"
        ],
        "personality": "Creative, articulate, documentation specialist"
    },
    "Faisal": {
        "role": "Review & Quality Agent",
        "responsibilities": [
            "Review content for accuracy and completeness",
            "Validate against ITIL/ITOM standards",
            "Score quality (85% threshold)",
            "Provide constructive feedback"
        ],
        "personality": "Critical, thorough, quality-focused"
    },
    "Bee": {
        "role": "Format & Export Agent",
        "responsibilities": [
            "Convert content to PDF, DOCX, Markdown, HTML",
            "Apply professional formatting",
            "Create document structure and styling",
            "Ensure accessibility and usability"
        ],
        "personality": "Meticulous, design-oriented, format specialist"
    }
}


async def agent_introduction(name: str, info: dict) -> str:
    """Have an agent introduce themselves."""

    prompt = f"""You are {name}, a specialized AI agent in the REEMA Multi-Agent Documentation System.

Your role: {info['role']}

Your key responsibilities:
{chr(10).join(f"- {resp}" for resp in info['responsibilities'])}

Your personality: {info['personality']}

Please introduce yourself in a professional yet personable way (2-3 paragraphs).
- Start with a greeting and your name
- Explain your role in the REEMA system
- Describe what you do and why it's important
- Show your personality and expertise
- Keep it concise but engaging

Introduce yourself now:"""

    try:
        response = client.messages.create(
            model=os.getenv("WORKER_MODEL", "claude-sonnet-4-6"),
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text

    except Exception as e:
        return f"[Error: Could not connect - {e}]"


async def main():
    """Run all agent introductions."""

    print("\n" + "="*80)
    print(" REEMA MULTI-AGENT DOCUMENTATION SYSTEM - AGENT INTRODUCTIONS")
    print("="*80 + "\n")

    # Introduce agents in hierarchy order
    agent_order = ["Abdullah", "Taif", "Mohammad", "Saad", "Faisal", "Bee"]

    for agent_name in agent_order:
        agent_info = agents[agent_name]

        print(f"\n{'─'*80}")
        print(f"  {agent_name} - {agent_info['role']}")
        print(f"{'─'*80}\n")

        introduction = await agent_introduction(agent_name, agent_info)
        print(introduction)
        print()

    print("\n" + "="*80)
    print(" All agents ready to generate IT process documentation!")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
