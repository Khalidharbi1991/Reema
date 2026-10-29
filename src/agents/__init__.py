"""Agents for REEMA personal assistance and IT documentation.

12 roles: Ahmad, Abdullah, eight numbered IT specialists, Agent 9
for building design, and Agent 10 for end-user computing. Ahmad consults chat
specialists directly; Abdullah leads only the SOP pipeline. Agent 9 currently
provides advisory, drawing-intake, and bounded concept-mesh capabilities, not
full-building BIM conversion. Agent 10 is advisory only.
"""

from .base_agent import BaseAgent
from .leader_agent import LeaderAgent
from .secretary_agent import SecretaryAgent
from .research_agent import ResearchAgent
from .standards_agent import StandardsAgent
from .content_agent import ContentAgent
from .review_agent import ReviewAgent
from .format_agent import FormatAgent
from .data_agent import DataAgent
from .access_agent import AccessAgent
from .problem_agent import ProblemAgent
from .building_design_agent import BuildingDesignAgent
from .euc_agent import EUCAgent

__all__ = [
    "BaseAgent",
    "LeaderAgent",
    "SecretaryAgent",
    "ResearchAgent",
    "StandardsAgent",
    "ContentAgent",
    "ReviewAgent",
    "FormatAgent",
    "DataAgent",
    "AccessAgent",
    "ProblemAgent",
    "BuildingDesignAgent",
    "EUCAgent",
]
