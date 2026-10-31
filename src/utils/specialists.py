"""Bounded evidence and specialist checks. No production access or factual certification."""

from datetime import date, datetime
import math
import re
import json
from typing import Literal
from pydantic import Field, JsonValue, model_validator
from .documents import Contract, ControlEvidence


def iso_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Use an explicit ISO calendar date")
    return date.fromisoformat(value)


def instant(value):
    if not isinstance(value, str):
        raise ValueError("Evidence timestamps must be ISO strings")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Evidence timestamps need an explicit time zone")
    return result


class SpecialistPolicy(Contract):
    freshness_days: int = Field(default=365, ge=1, le=3650)
    max_claims: int = Field(default=100, ge=1, le=500)
    max_identities: int = Field(default=1000, ge=1, le=10000)
    max_observations: int = Field(default=500, ge=1, le=5000)
    max_metric_rows: int = Field(default=10000, ge=1, le=100000)
    require_privileged_mfa: bool = True
    require_approval_evidence: bool = True
    cad_max_bytes: int = Field(default=25000000, ge=1000, le=50000000)
    cad_max_entities: int = Field(default=50000, ge=1, le=100000)
    cad_max_segments: int = Field(default=5000, ge=1, le=10000)
    cad_wall_layers: list[str] = Field(default_factory=lambda: ['A-WALL'], min_length=1, max_length=10)
    separation_of_duties: list[list[str]] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def conflicts(self):
        if any(len(pair) != 2 or len(set(pair)) != 2 or any(not role.strip() for role in pair) for pair in self.separation_of_duties):
            raise ValueError("Separation of duties needs pairs of distinct role IDs")
        return self


def check_evidence(evidence, sources):
    for item in evidence:
        item = ControlEvidence.model_validate(item)
        source = sources.get(item.source_id)
        if not source or any(getattr(item, k) != source.get(k) for k in ("source", "location", "sha256")) or item.quote not in source.get("text", ""):
            raise ValueError("Specialist evidence must match an authorized located source excerpt")


class ResearchClaim(Contract):
    id: str = Field(pattern=r"^CLM-[A-Za-z0-9_-]+$")
    text: str = Field(min_length=1)
    kind: Literal["observation", "recommendation", "assumption"]
    evidence: list[ControlEvidence]


class ResearchAnalysis(Contract):
    raw_research: str = Field(min_length=1)
    claims: list[ResearchClaim] = Field(max_length=500)


def assess_claims(claims, sources, as_of, policy):
    today = iso_date(as_of)
    if len(claims) > policy.max_claims or len({c.id for c in claims}) != len(claims):
        raise ValueError("Research claims exceed the bound or repeat IDs")
    rows = []
    for claim in claims:
        check_evidence(claim.evidence, sources)
        dates = []
        for evidence in claim.evidence:
            published = sources[evidence.source_id].get("published_on")
            age = (today - iso_date(published)).days if published else None
            state = "unknown" if age is None else "future_date" if age < 0 else "stale" if age > policy.freshness_days else "within_age_limit"
            dates.append({"source_id": evidence.source_id, "published_on": published, "age_days": age, "freshness": state,
                          "date_basis": "user_supplied_metadata_unverified" if published else "not_supplied"})
        state = "unsupported" if not dates else "future_evidence" if any(d["freshness"] == "future_date" for d in dates) else "stale_support" if any(d["freshness"] == "stale" for d in dates) else "unknown_freshness" if any(d["freshness"] == "unknown" for d in dates) else "located_unverified"
        rows.append({**claim.model_dump(), "evidence_status": state, "source_dates": dates, "verification": "unverified"})
    return {"as_of": as_of, "freshness_days": policy.freshness_days, "claims": rows,
            "status": "claims_recorded" if rows else "no_typed_claims",
            "verification": "unverified", "source_freshness_is_not_factual_accuracy": True}


class Identity(Contract):
    id: str = Field(min_length=1)
    active: bool
    privileged: bool
    mfa_enabled: bool | None
    roles: list[str]


class ApprovalEvidence(Contract):
    subject_id: str
    role: str
    approved: bool
    approved_at: str
    evidence: list[ControlEvidence]

    @model_validator(mode="after")
    def timestamp(self):
        instant(self.approved_at)
        return self


class IAMGroup(Contract):
    id: str
    roles: list[str] = Field(default_factory=list, max_length=1000)
    members: list[str] = Field(default_factory=list, max_length=10000)
    member_groups: list[str] = Field(default_factory=list, max_length=1000)


class IAMSnapshot(Contract):
    snapshot_id: str
    observed_at: str
    roles: list[str] = Field(max_length=1000)
    identities: list[Identity] = Field(max_length=10000)
    approvals: list[ApprovalEvidence] = Field(max_length=10000)
    groups: list[IAMGroup] = Field(default_factory=list, max_length=1000)
    privileged_roles: list[str] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def unique(self):
        instant(self.observed_at)
        if len(set(self.roles)) != len(self.roles) or len({i.id for i in self.identities}) != len(self.identities):
            raise ValueError("IAM snapshot has duplicate roles or identities")
        if any(len(set(i.roles)) != len(i.roles) for i in self.identities):
            raise ValueError("IAM identity has duplicate role grants")
        if any(not r.strip() for r in self.roles) or any(not r.strip() for i in self.identities for r in i.roles):
            raise ValueError("IAM role identifiers cannot be blank")
        keys = [(a.subject_id, a.role) for a in self.approvals]
        if len(set(keys)) != len(keys):
            raise ValueError("IAM approval records are ambiguous")
        return self


def check_iam(snapshot, sources, policy):
    if snapshot is None:
        return {"status": "missing_environment", "checks": [], "production_operation": "not_verified"}
    snapshot = IAMSnapshot.model_validate(snapshot)
    if len(snapshot.identities) > policy.max_identities:
        raise ValueError("IAM snapshot exceeds the identity limit")
    from .domain_depth import effective_roles
    grants = effective_roles(snapshot)
    if set(snapshot.privileged_roles) - set(snapshot.roles):
        raise ValueError("Unknown privileged role")
    checks = []
    identities = {i.id for i in snapshot.identities}
    for approval in snapshot.approvals:
        check_evidence(approval.evidence, sources)
        if approval.subject_id not in identities or approval.role not in snapshot.roles or instant(approval.approved_at) > instant(snapshot.observed_at):
            raise ValueError("IAM approval has an unknown subject/role or a future timestamp")
    approvals = {(a.subject_id, a.role): a for a in snapshot.approvals}
    for identity in snapshot.identities:
        roles = grants[identity.id]
        if set(roles) - set(snapshot.roles):
            checks.append({"identity": identity.id, "check": "role_exists", "result": "fail"})
        if not identity.active and roles:
            checks.append({"identity": identity.id, "check": "inactive_account_grants", "result": "fail"})
        if identity.active and (identity.privileged or set(roles) & set(snapshot.privileged_roles)) and policy.require_privileged_mfa:
            checks.append({"identity": identity.id, "check": "privileged_mfa", "result": "unknown" if identity.mfa_enabled is None else "pass" if identity.mfa_enabled else "fail"})
        for pair in policy.separation_of_duties:
            if set(pair) <= set(roles):
                checks.append({"identity": identity.id, "check": "separation_of_duties", "roles": pair, "result": "fail"})
        for role in roles:
            approval = approvals.get((identity.id, role))
            state = "missing" if not approval else "denied" if not approval.approved else "recorded_unverified" if approval.evidence else "missing_evidence"
            checks.append({"identity": identity.id, "role": role, "check": "approval_record", "result": state})
    gaps = any(c["result"] in {"fail", "unknown", "denied"} or policy.require_approval_evidence and c["result"] in {"missing", "missing_evidence"} for c in checks)
    return {"snapshot_id": snapshot.snapshot_id, "observed_at": snapshot.observed_at,
            "status": "empty_snapshot" if not snapshot.identities else "gaps_found" if gaps else "snapshot_consistent", "checks": checks,
            "production_operation": "not_verified", "grant_access": False, "effective_roles": grants}


class Observation(Contract):
    id: str = Field(pattern=r"^OBS-[A-Za-z0-9_-]+$")
    observed_at: str
    description: str
    evidence: list[ControlEvidence]

    @model_validator(mode="after")
    def timestamp(self):
        instant(self.observed_at)
        return self


class CausalTest(Contract):
    id: str = Field(pattern=r"^TEST-[A-Za-z0-9_-]+$")
    hypothesis_id: str = Field(pattern=r"^HYP-[A-Za-z0-9_-]+$")
    observed_at: str
    criterion: str
    outcome: Literal['supporting', 'refuting', 'inconclusive']
    evidence: list[ControlEvidence]

    @model_validator(mode="after")
    def timestamp(self):
        instant(self.observed_at)
        return self


class ProblemCase(Contract):
    case_id: str
    observations: list[Observation] = Field(max_length=5000)
    test_outcomes: list[CausalTest] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def unique(self):
        if len({o.id for o in self.observations}) != len(self.observations):
            raise ValueError("Problem observations need unique IDs")
        return self


class Hypothesis(Contract):
    id: str = Field(pattern=r"^HYP-[A-Za-z0-9_-]+$")
    explanation: str
    supporting_observation_ids: list[str]
    contradicting_observation_ids: list[str]
    next_tests: list[str] = Field(min_length=1)


class ProblemAnalysis(Contract):
    problem_research: str
    hypotheses: list[Hypothesis] = Field(min_length=2, max_length=20)
    root_cause_status: Literal["unconfirmed"] = "unconfirmed"


def assess_problem(case, hypotheses, sources, policy):
    case = ProblemCase.model_validate(case) if case is not None else None
    observations = case.observations if case else []
    if len(observations) > policy.max_observations or len({h.id for h in hypotheses}) != len(hypotheses):
        raise ValueError("Problem assessment exceeds bounds or repeats hypothesis IDs")
    ids = {o.id for o in observations}
    for observation in observations:
        check_evidence(observation.evidence, sources)
    for hypothesis in hypotheses:
        pro, con = set(hypothesis.supporting_observation_ids), set(hypothesis.contradicting_observation_ids)
        if ((pro | con) - ids or pro & con or len(pro) != len(hypothesis.supporting_observation_ids)
                or len(con) != len(hypothesis.contradicting_observation_ids) or any(not t.strip() for t in hypothesis.next_tests)):
            raise ValueError("Hypothesis refers to unknown or contradictory observation IDs")
    from .domain_depth import evaluate_causal_tests
    causal = evaluate_causal_tests(case, hypotheses, sources)
    return {"case_id": case.case_id if case else None, "status": "observations_supplied" if observations else "missing_observations",
            "timeline": [{**o.model_dump(), "status": "located_unverified" if o.evidence else "user_reported_unverified"}
                         for o in sorted(observations, key=lambda o: instant(o.observed_at))],
            "hypotheses": [h.model_dump() for h in hypotheses], "root_cause_status": "unconfirmed", "causal_tests": causal}


class BusinessCalendar(Contract):
    timezone: str
    weekdays: list[int] = Field(min_length=1, max_length=7)
    start_minute: int = Field(ge=0, lt=1440)
    end_minute: int = Field(gt=0, le=1440)
    holidays: list[str] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def valid(self):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try: ZoneInfo(self.timezone)
        except (ValueError, ZoneInfoNotFoundError): raise ValueError("Unknown calendar time zone") from None
        if self.start_minute >= self.end_minute or len(set(self.weekdays)) != len(self.weekdays) or any(d < 0 or d > 6 for d in self.weekdays):
            raise ValueError("Calendar needs distinct weekdays and same-day increasing work hours")
        for day in self.holidays: iso_date(day)
        return self


class MetricSpec(Contract):
    id: str = Field(pattern=r"^MET-[A-Za-z0-9_-]+$")
    name: str
    kind: Literal["ratio", "duration_mean", "sum", "count", "difference", "weighted_mean", "business_duration_mean"]
    unit: Literal["percent", "seconds", "minutes", "hours", "count", "number"]
    owner: str
    source: str
    cadence: str
    numerator_field: str | None = None
    denominator_field: str | None = None
    value_field: str | None = None
    start_field: str | None = None
    end_field: str | None = None
    exclude_field: str | None = None
    missing_policy: Literal["error", "exclude"] = "error"
    subtrahend_field: str | None = None
    weight_field: str | None = None
    calendar: BusinessCalendar | None = None
    evidence: list[ControlEvidence] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def operands(self):
        needed = {"ratio": ["numerator_field", "denominator_field"], "duration_mean": ["start_field", "end_field"], "business_duration_mean": ["start_field", "end_field"], "difference": ["value_field", "subtrahend_field"], "weighted_mean": ["value_field", "weight_field"], "sum": ["value_field"], "count": []}[self.kind]
        fields = ["numerator_field", "denominator_field", "value_field", "start_field", "end_field", "subtrahend_field", "weight_field"]
        if any(not getattr(self, k) for k in needed) or any(getattr(self, k) is not None for k in fields if k not in needed):
            raise ValueError("Metric operands must match its supported calculation")
        units = {"ratio": {"percent"}, "duration_mean": {"seconds", "minutes", "hours"}, "business_duration_mean": {"seconds", "minutes", "hours"}, "difference": {"number"}, "weighted_mean": {"number"}, "sum": {"number", "count"}, "count": {"count"}}
        if self.unit not in units[self.kind]:
            raise ValueError("Metric unit does not match its calculation")
        if len({getattr(self, k) for k in needed}) != len(needed):
            raise ValueError("Metric operands must refer to distinct fields")
        if (self.kind == 'business_duration_mean') != (self.calendar is not None):
            raise ValueError("Only business duration requires an explicit calendar")
        return self


class AnalyticsAnalysis(Contract):
    analytics_framework: str
    metrics: list[MetricSpec] = Field(max_length=20)


def calculate_metric(spec, rows, policy, sources=None):
    spec = MetricSpec.model_validate(spec)
    if sources is not None: check_evidence(spec.evidence, sources)
    lineage = {"lineage_status": "located_unverified" if spec.evidence and sources is not None else "not_checked" if spec.evidence else "missing", "lineage": [e.model_dump() for e in spec.evidence]}
    if rows is None:
        return {"metric_id": spec.id, "status": "no_data", "value": None, "unit": spec.unit, **lineage}
    if len(rows) > policy.max_metric_rows:
        raise ValueError("Metric data exceeds the row limit")
    eligible, excluded, missing = [], 0, 0
    fields = [getattr(spec, k) for k in ("numerator_field", "denominator_field", "value_field", "start_field", "end_field", "subtrahend_field", "weight_field") if getattr(spec, k)]
    for row in rows:
        if spec.exclude_field:
            exclusion = row.get(spec.exclude_field)
            if type(exclusion) is not bool:
                raise ValueError("Metric exclusion flags must be explicit booleans")
            if exclusion:
                excluded += 1
                continue
        if any(row.get(f) is None for f in fields):
            if spec.missing_policy == "error":
                raise ValueError("Metric row has missing required data")
            missing += 1
            continue
        eligible.append(row)
    def number(value):
        try:
            valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
        except OverflowError:
            valid = False
        if not valid or spec.unit == "count" and value % 1:
            raise ValueError("Metric numeric inputs must be finite nonnegative numbers")
        return value
    value, denominator = None, None
    formula = {"ratio": "100 * sum(numerator) / sum(denominator)", "duration_mean": "mean(end - start)", "business_duration_mean": "mean(working_seconds(start, end, calendar))", "difference": "sum(value - subtrahend)", "weighted_mean": "sum(value * weight) / sum(weight)", "sum": "sum(value)", "count": "count(eligible rows)"}[spec.kind]
    if spec.kind == "count": value = len(eligible)
    elif spec.kind == "sum": value = sum(number(r[spec.value_field]) for r in eligible) if eligible else None
    elif spec.kind == "difference": value = sum(number(r[spec.value_field]) - number(r[spec.subtrahend_field]) for r in eligible) if eligible else None
    elif spec.kind == "weighted_mean":
        pairs = [(number(r[spec.value_field]), number(r[spec.weight_field])) for r in eligible]
        denominator = sum(w for _, w in pairs)
        numerator = sum(v*w for v,w in pairs)
        if not math.isfinite(denominator) or not math.isfinite(numerator): raise ValueError("Metric aggregation overflowed")
        value = numerator / denominator if denominator else None
    elif spec.kind == "ratio":
        pairs = [(number(r[spec.numerator_field]), number(r[spec.denominator_field])) for r in eligible]
        if any(n > d for n, d in pairs): raise ValueError("Ratio numerator exceeds its denominator")
        denominator = sum(d for _, d in pairs)
        numerator = sum(n for n, _ in pairs)
        if not math.isfinite(denominator) or not math.isfinite(numerator): raise ValueError("Metric aggregation overflowed")
        value = (numerator / denominator) * 100 if denominator else None
    else:
        from .domain_depth import business_seconds
        durations = [business_seconds(instant(r[spec.start_field]), instant(r[spec.end_field]), spec.calendar) if spec.calendar else (instant(r[spec.end_field]) - instant(r[spec.start_field])).total_seconds() for r in eligible]
        if any(v < 0 for v in durations): raise ValueError("Metric end precedes start")
        value = sum(durations) / len(durations) / {"seconds": 1, "minutes": 60, "hours": 3600}[spec.unit] if durations else None
    if value is not None and not math.isfinite(value): raise ValueError("Metric calculation overflowed")
    return {"metric_id": spec.id, "status": "calculated" if value is not None else "undefined_zero_denominator" if denominator == 0 and eligible else "no_eligible_data",
            "value": value, "unit": spec.unit, "formula": formula, "eligible_rows": len(eligible),
            "excluded_rows": excluded, "missing_rows": missing, "denominator": denominator,
            "verification": "calculated_from_supplied_data_only", **lineage}


class SpecialistInputs(Contract):
    as_of: str | None = None
    iam_environment: IAMSnapshot | None = None
    iam_previous: IAMSnapshot | None = None
    problem_case: ProblemCase | None = None
    metric_specs: list[MetricSpec] = Field(default_factory=list, max_length=20)
    metric_rows: list[dict[str, JsonValue]] | None = None

    @model_validator(mode="after")
    def unique(self):
        if self.as_of: iso_date(self.as_of)
        if self.iam_previous is not None and self.iam_environment is None:
            raise ValueError("IAM baseline requires a current snapshot")
        if len({m.id for m in self.metric_specs}) != len(self.metric_specs): raise ValueError("Metric IDs must be unique")
        if self.metric_rows is not None and not self.metric_specs:
            raise ValueError("Metric rows require explicit metric specifications")
        return self

    def required_specialists(self):
        return ({"access"} if self.iam_environment is not None else set()) | ({"problem"} if self.problem_case is not None else set()) | ({"data"} if self.metric_specs else set())

    def validate_limits(self, policy):
        from .domain_depth import effective_roles, iam_drift
        for snapshot in [self.iam_environment, self.iam_previous]:
            if snapshot:
                if len(snapshot.identities) > policy.max_identities: raise ValueError("IAM snapshot exceeds the identity limit")
                effective_roles(snapshot)
        if self.iam_previous: iam_drift(self.iam_previous, self.iam_environment)
        if self.problem_case and len(self.problem_case.observations) > policy.max_observations:
            raise ValueError("Problem observations exceed the configured limit")
        for spec in self.metric_specs:
            calculate_metric(spec, self.metric_rows, policy)
        return self


def validate_analytics_result(result, supplied, policy, sources=None):
    """Recompute typed worker calculations before caching or downstream use."""
    if not isinstance(result, dict) or not ({"metric_specs", "calculation_checks"} & result.keys()):
        return  # Public legacy narrative workers carry no certified numbers.
    if not {"metric_specs", "calculation_checks"} <= result.keys():
        raise ValueError("Analytics handoff needs both specifications and calculation checks")
    specs = [MetricSpec.model_validate(s) for s in result["metric_specs"]]
    if len(specs) > 20 or len({s.id for s in specs}) != len(specs):
        raise ValueError("Analytics handoff has duplicate or excessive metric specifications")
    supplied = supplied or {}
    if supplied.get("metric_specs") and [s.model_dump() for s in specs] != supplied["metric_specs"]:
        raise ValueError("Analytics handoff changed supplied metric specifications")
    expected = [calculate_metric(s, supplied.get("metric_rows"), policy, sources) for s in specs]
    if json.dumps(result["calculation_checks"], sort_keys=True, allow_nan=False) != json.dumps(expected, sort_keys=True, allow_nan=False):
        raise ValueError("Analytics calculation checks do not match the supplied data")


def specialist_checks(inputs, sources, policy):
    """The local checks on supplied specialist data (IAM, problem case, metrics), as data; no model call."""
    from .domain_depth import iam_drift
    inputs = SpecialistInputs.model_validate(inputs)
    checks = {}
    if inputs.iam_environment is not None:
        checks["iam"] = check_iam(inputs.iam_environment, sources, policy)
        if inputs.iam_previous is not None:
            check_iam(inputs.iam_previous, sources, policy)
            checks["iam"]["drift"] = iam_drift(inputs.iam_previous, inputs.iam_environment)
    if inputs.problem_case is not None:
        checks["problem"] = assess_problem(inputs.problem_case, [], sources, policy)
    if inputs.metric_specs:
        checks["metrics"] = [calculate_metric(spec, inputs.metric_rows, policy, sources) for spec in inputs.metric_specs]
    return checks
