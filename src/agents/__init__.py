"""Agents for REEMA personal assistance and IT documentation.

12 roles: Ahmad, Abdullah, eight numbered IT specialists, Agent 9 for building design, and
Agent 10 for end-user computing. Ahmad is the main Claude Code session and Abdullah leads the
SOP jobs. Agents 1, 2, 6, 7 and 8 have no class: they remain configured roles whose knowledge
files are source material. The classes here make no model call; Claude Code writes the text.
Agent 9 provides drawing intake and bounded concept meshes, not full-building BIM conversion.
"""

from .base_agent import BaseAgent
from .leader_agent import LeaderAgent
from .secretary_agent import SecretaryAgent
from .content_agent import ContentAgent
from .review_agent import ReviewAgent
from .format_agent import FormatAgent
from .building_design_agent import BuildingDesignAgent
from .euc_agent import EUCAgent

__all__ = [
    "BaseAgent",
    "LeaderAgent",
    "SecretaryAgent",
    "ContentAgent",
    "ReviewAgent",
    "FormatAgent",
    "BuildingDesignAgent",
    "EUCAgent",
]
