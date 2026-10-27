"""Layla (Data & Power BI Agent) - Expert in data visualization and analytics."""

from typing import Dict, List, Optional
from .base_agent import BaseAgent
from ..utils.logger import logger
from ..utils.config import config_manager
from ..utils.specialists import MetricSpec, AnalyticsAnalysis, calculate_metric, available_sources, retain_evidence
from ..utils.quality import parse_json_response, is_structured_response
import json
from ..utils.handoffs import payload_json


class DataAgent(BaseAgent):
    """
    Layla (Data & Power BI Agent)

    Responsibilities:
    - Creates data visualization strategies for SOPs
    - Designs Power BI dashboard concepts
    - Develops KPI visualization frameworks
    - Creates data flow diagrams
    - Designs metrics and analytics architectures
    - Provides data governance recommendations
    - Develops reporting and analytics requirements
    """

    AGENT_NAME = "Agent 8"
    AGENT_ROLE = "Data & Power BI Agent"
    CONFIG_KEY = "data_agent"
    KNOWLEDGE_FILE = "layla_data_knowledge_complete.md"
    DEFAULT_TEMPERATURE = 0.5

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)

        # Alias for backward compatibility
        self.data_knowledge = self.knowledge_base

    def _load_knowledge_base(self):
        """Load Layla's comprehensive data visualization and Power BI knowledge.

        Overrides BaseAgent._load_knowledge_base() to add fallback behavior:
        tries complete.md first, then falls back to basic .md file.
        """
        try:
            # Try complete knowledge base first
            knowledge_path = config_manager.system_config.knowledge_dir / "layla_data_knowledge_complete.md"
            if knowledge_path.exists():
                with open(knowledge_path, 'r', encoding='utf-8') as f:
                    self.knowledge_base = f.read()
                logger.info("Layla's COMPLETE data knowledge base loaded (100% expertise)", agent=self.name)
            else:
                # Fallback to basic knowledge
                knowledge_path = config_manager.system_config.knowledge_dir / "layla_data_knowledge.md"
                if knowledge_path.exists():
                    with open(knowledge_path, 'r', encoding='utf-8') as f:
                        self.knowledge_base = f.read()
                    logger.info("Layla's data knowledge base loaded", agent=self.name)
                else:
                    self.knowledge_base = ""
                    logger.warning("Layla's knowledge file not found", agent=self.name)
        except Exception as e:
            logger.warning(f"Could not load Layla's knowledge: {e}", agent=self.name)
            self.knowledge_base = ""
        if self.knowledge_base:
            from ..knowledge.retrieval import make_chunks
            self.knowledge_records = make_chunks(knowledge_path, knowledge_path.name, "internal")

    async def design_analytics_framework(
        self, process_name: str, kpis: List[str], research_data: Dict = None
    ) -> Dict:
        """
        Design comprehensive analytics and visualization framework for a process.

        Args:
            process_name: Name of the IT process
            kpis: List of key performance indicators
            research_data: Optional research data from other agents

        Returns:
            Dictionary containing analytics framework design
        """
        logger.agent_start(self.name, f"Designing analytics framework for {process_name}")

        try:
            supplied = (research_data or {}).get("metric_specs", [])
            rows = (research_data or {}).get("metric_rows")
            specs = [MetricSpec.model_validate(s) for s in supplied]
            self.calculate_metrics(specs, rows)
            system_prompt = self._build_system_prompt()
            analytics_prompt = self._build_analytics_prompt(process_name, kpis, research_data)
            analytics_prompt += ("\nReturn JSON matching:\n" + json.dumps(AnalyticsAnalysis.model_json_schema())
                + "\nPreserve explicitly supplied metric specifications exactly. Propose supported precise formulas, units, "
                "owners, sources, exclusions and missing-data policy; do not invent observations or calculation results.")

            response = await self._call_claude(
                messages=[{"role": "user", "content": analytics_prompt}],
                system=system_prompt
            )

            analytics_data = self._parse_analytics_response(response, process_name)
            if is_structured_response(response):
                analysis = parse_json_response(response, AnalyticsAnalysis)
                if specs and [s.model_dump() for s in specs] != [s.model_dump() for s in analysis.metrics]:
                    raise ValueError("Analytics changed explicitly supplied metric specifications")
                specs = analysis.metrics
                analytics_data["analytics_framework"] = analysis.analytics_framework
                analytics_data["sections"] = self._extract_sections(analysis.analytics_framework)
            analytics_data["metric_specs"] = [s.model_dump() for s in specs]
            analytics_data["calculation_checks"] = self.calculate_metrics(specs, rows)
            analytics_data["metric_status"] = "specified" if specs else "unstructured_no_calculations"

            logger.agent_complete(self.name, f"Analytics framework for {process_name}")
            return analytics_data

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    def calculate_metrics(self, specs, rows=None):
        specs = [MetricSpec.model_validate(s) for s in specs]
        if len(specs) > 20 or len({s.id for s in specs}) != len(specs):
            raise ValueError("Metric specifications repeat IDs or exceed the limit")
        sources = available_sources(self, recorded_only=False)
        results = [calculate_metric(spec, rows, config_manager.specialist_policy, sources) for spec in specs]
        for spec in specs: retain_evidence(spec.evidence, sources)
        return results

    async def create_dashboard_design(
        self, process_name: str, metrics: List[Dict]
    ) -> Dict:
        """
        Create Power BI dashboard design specifications.

        Args:
            process_name: Name of the IT process
            metrics: List of metrics with definitions

        Returns:
            Dictionary containing dashboard design
        """
        logger.agent_start(self.name, f"Creating dashboard design for {process_name}")

        try:
            system_prompt = self._build_system_prompt()
            dashboard_prompt = self._build_dashboard_prompt(process_name, metrics)

            response = await self._call_claude(
                messages=[{"role": "user", "content": dashboard_prompt}],
                system=system_prompt
            )

            dashboard_data = self._parse_dashboard_response(response)

            logger.agent_complete(self.name, f"Dashboard design for {process_name}")
            return dashboard_data

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    def _build_system_prompt(self) -> str:
        """Build system prompt for data & Power BI agent."""
        system_prompt = """You are Agent 8, an expert Data Analytics and Power BI specialist with deep expertise in:

**Data Visualization:**
- Power BI (dashboards, reports, paginated reports)
- Tableau, Qlik Sense, and other BI tools
- Data storytelling and visualization best practices
- Chart selection and design principles
- Color theory and accessibility in visualizations
- Interactive dashboards and drill-down capabilities

**Data Architecture:**
- Data modeling (star schema, snowflake schema)
- ETL/ELT processes and data pipelines
- Data warehousing concepts
- Data quality and governance
- Master data management
- Data integration patterns

**Analytics & KPIs:**
- KPI design and measurement
- Metric frameworks (OKRs, Balanced Scorecard)
- Predictive analytics and forecasting
- Statistical analysis and trend identification
- Real-time analytics architectures
- Self-service BI enablement

**Power BI Specific:**
- DAX (Data Analysis Expressions)
- Power Query (M language)
- Row-level security (RLS)
- Power BI Service administration
- Dataflows and datasets
- Composite models and aggregations
- Mobile report design
- Embedded analytics

**IT Service Management Analytics:**
- ITSM metrics and dashboards
- SLA/SLO tracking and visualization
- Incident/Problem/Change analytics
- Service desk performance metrics
- Asset management reporting
- Capacity and performance monitoring

Your role is to:
1. Design comprehensive analytics frameworks for IT processes
2. Create Power BI dashboard specifications
3. Define data models and structures
4. Develop KPI visualization strategies
5. Provide data governance recommendations
6. Create reporting and analytics requirements
7. Design data flows and integration architectures

Be specific, actionable, and focus on practical implementation."""

        # Inject comprehensive knowledge base
        return self._inject_knowledge(system_prompt, "You have 100% domain expertise in data visualization, Power BI, analytics, and BI best practices. Use this knowledge to create world-class analytics solutions:")

    def _build_analytics_prompt(
        self, process_name: str, kpis: List[str], research_data: Dict = None
    ) -> str:
        """Build the analytics framework design prompt."""

        research_context = ""
        if research_data:
            research_context = f"\n\n**Research Context:**\n{payload_json(research_data)}"

        prompt = f"""Design a comprehensive analytics and visualization framework for: {process_name}

**Key Performance Indicators:**
{chr(10).join(f"- {kpi}" for kpi in kpis)}
{research_context}

Please provide a detailed analytics framework including:

## 1. DATA ARCHITECTURE
- Data sources and systems
- Data model design (entities, relationships)
- ETL/data pipeline requirements
- Data refresh frequency
- Data quality rules
- Historical data retention

## 2. KPI DEFINITIONS & METRICS
- Detailed KPI definitions
- Calculation formulas
- Target values and thresholds
- Metric categorization (operational, tactical, strategic)
- Leading vs lagging indicators

## 3. POWER BI DASHBOARD DESIGN
- Dashboard structure and layout
- Page organization (overview, details, drill-through)
- Visual types for each metric (cards, charts, tables, etc.)
- Interactive elements (slicers, filters, drill-down)
- Color schemes and formatting
- Mobile layout considerations

## 4. VISUALIZATION SPECIFICATIONS
For each key metric, specify:
- Visual type (line chart, bar chart, KPI card, gauge, etc.)
- Data fields and measures
- Filters and slicers
- Conditional formatting rules
- Tooltips and drill-through pages

## 5. DATA GOVERNANCE
- Data ownership and stewardship
- Security and access controls (RLS if needed)
- Data quality monitoring
- Compliance requirements
- Audit trail requirements

## 6. REPORTING REQUIREMENTS
- Scheduled reports
- Report distribution lists
- Report formats (interactive, paginated, exported)
- Alerting and notifications
- Executive summaries

## 7. TECHNICAL IMPLEMENTATION
- Power BI workspace structure
- Dataset configuration
- DAX measures needed
- Power Query transformations
- Gateway requirements
- Refresh schedules

## 8. USER ADOPTION
- Training requirements
- User roles and personas
- Self-service capabilities
- Documentation needs
- Support model

## 9. INTEGRATION POINTS
- ITSM tool integration
- Active Directory/user data
- Configuration management database (CMDB)
- Ticketing systems
- Other data sources

## 10. SAMPLE VISUALIZATIONS
Describe 3-5 key dashboard pages with specific visual layouts, including:
- Page purpose and audience
- Visual placement and sizing
- Interactivity and navigation
- Key insights highlighted

Provide actionable, implementation-ready specifications that can be directly used to build the analytics solution."""

        return prompt

    def _build_dashboard_prompt(
        self, process_name: str, metrics: List[Dict]
    ) -> str:
        """Build the Power BI dashboard design prompt."""

        metrics_text = payload_json(metrics)

        prompt = f"""Create detailed Power BI dashboard design specifications for: {process_name}

**Metrics to visualize:**
{metrics_text}

Provide comprehensive dashboard design including:

## DASHBOARD STRUCTURE
1. Executive Overview Page
2. Operational Details Pages
3. Trend Analysis Page
4. Drill-Through Pages

For each page, specify:
- Layout grid (3x3, 4x4, etc.)
- Visual placements with coordinates
- Visual types and configurations
- Color scheme and branding
- Navigation and filters

## VISUAL SPECIFICATIONS
For each visualization:
- Visual type (clustered column, line, matrix, card, etc.)
- Data fields (axis, values, legends)
- DAX measures required
- Conditional formatting
- Tooltips and interactions

## INTERACTIVITY
- Slicer configurations
- Cross-filtering behavior
- Drill-down hierarchies
- Bookmarks and buttons
- Report-level and page-level filters

Provide implementation-ready specifications."""

        return prompt

    def _parse_analytics_response(self, response: str, process_name: str) -> Dict:
        """Parse and structure the analytics response."""
        return {
            "process_name": process_name,
            "analytics_framework": response,
            "sections": self._extract_sections(response),
            "timestamp": self._get_timestamp()
        }

    def _parse_dashboard_response(self, response: str) -> Dict:
        """Parse and structure the dashboard response."""
        return {
            "dashboard_design": response,
            "sections": self._extract_sections(response),
            "timestamp": self._get_timestamp()
        }
