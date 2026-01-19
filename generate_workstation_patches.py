"""
Generate Workstation Security Patches SOP Documentation
This script runs the multi-agent system to create the documentation.
"""
import asyncio
import os
from pathlib import Path

# Set your Anthropic API key here
# IMPORTANT: Replace with your actual API key
API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

if not API_KEY:
    print("ERROR: Please set your ANTHROPIC_API_KEY environment variable")
    print("Example: set ANTHROPIC_API_KEY=your-api-key-here")
    exit(1)

# Set the API key in the environment
os.environ["ANTHROPIC_API_KEY"] = API_KEY

from src.agents.leader_agent import LeaderAgent
from src.agents.research_agent import ResearchAgent
from src.agents.standards_agent import StandardsAgent
from src.agents.content_agent import ContentAgent
from src.agents.review_agent import ReviewAgent
from src.agents.format_agent import FormatAgent
from src.utils.logger import logger

async def main():
    """Main function to generate the documentation."""

    print("\n" + "="*80)
    print("REEMA - Multi-Agent Documentation System")
    print("Generating: Workstation Security Patches SOP")
    print("="*80 + "\n")

    # Initialize leader agent
    print("🤖 Initializing Abdullah (Leader Agent)...")
    leader = LeaderAgent(api_key=API_KEY)

    # Initialize and register worker agents
    print("🔬 Initializing Taif (Research Agent)...")
    research = ResearchAgent(api_key=API_KEY)
    leader.register_worker("ResearchAgent", research)

    print("📋 Initializing Mohammad (Standards Agent)...")
    standards = StandardsAgent(api_key=API_KEY)
    leader.register_worker("StandardsAgent", standards)

    print("✍️  Initializing Saad (Content Agent)...")
    content = ContentAgent(api_key=API_KEY)
    leader.register_worker("ContentAgent", content)

    print("🔍 Initializing Faisal (Review Agent)...")
    review = ReviewAgent(api_key=API_KEY)
    leader.register_worker("ReviewAgent", review)

    print("📄 Initializing Bee (Format Agent)...")
    format_agent = FormatAgent()
    leader.register_worker("FormatAgent", format_agent)

    print("\n✅ All agents initialized successfully!\n")

    # Generate documentation
    process_name = "Workstation Security Patches"
    output_formats = ["docx", "pdf", "html"]  # DOCX, PDF, and HTML as requested

    print(f"📝 Starting documentation generation for: {process_name}")
    print(f"📦 Output formats: {', '.join(output_formats)}\n")

    try:
        output_files = await leader.generate_documentation(
            process_name=process_name,
            output_formats=output_formats
        )

        print("\n" + "="*80)
        print("✅ DOCUMENTATION GENERATED SUCCESSFULLY!")
        print("="*80 + "\n")

        print("📁 Generated Files:")
        for fmt, file_path in output_files.items():
            print(f"  • {fmt.upper()}: {file_path}")

        print("\n" + "="*80 + "\n")

        return output_files

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        logger.error(f"Documentation generation failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
