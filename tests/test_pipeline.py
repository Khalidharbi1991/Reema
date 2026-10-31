"""Integration tests for the REEMA pipeline."""



class TestAllAgentsImportable:
    """Test the remaining agent classes can be imported; Agents 1, 2, 6, 7 and 8 have no class."""

    def test_all_agents_importable(self):
        """Verify active classes can be imported from src.agents."""
        import src.agents as agents
        assert agents.__all__ == ["BaseAgent", "LeaderAgent", "SecretaryAgent", "ContentAgent", "ReviewAgent",
                                  "FormatAgent", "BuildingDesignAgent", "EUCAgent"]
        for name in ("ResearchAgent", "StandardsAgent", "AccessAgent", "ProblemAgent", "DataAgent"):
            assert not hasattr(agents, name)

    def test_agents_have_correct_names(self):
        """Verify agent names match expected team members."""
        from src.agents import (SecretaryAgent, ContentAgent, ReviewAgent, FormatAgent,
                                BuildingDesignAgent, EUCAgent)
        from src.utils.config import config_manager

        expected = {
            SecretaryAgent: "Ahmad",
            ContentAgent: "Agent 3",
            ReviewAgent: "Agent 4",
            FormatAgent: "Agent 5",
            BuildingDesignAgent: "Agent 9",
            EUCAgent: "Agent 10",
        }

        for agent_cls, expected_name in expected.items():
            assert agent_cls.AGENT_NAME == expected_name, \
                f"{agent_cls.__name__}.AGENT_NAME should be '{expected_name}'"
        # The roster keeps every role, including the five without a class.
        assert [config_manager.get_agent_config(key)["name"] for key in (
            "research_agent", "standards_agent", "access_agent", "problem_agent", "data_agent")] == [
            "Agent 1", "Agent 2", "Agent 6", "Agent 7", "Agent 8"]


def test_abdullah_keeps_pipeline_strategy_guidance():
    from src.agents.leader_agent import LeaderAgent
    leader = LeaderAgent()
    assert leader.name == "Abdullah"
    assert "IT strategy and roadmap development" in leader.strategic_guidance
