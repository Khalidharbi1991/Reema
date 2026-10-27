"""Bounded interpretation of supplied domain evidence, never production proof."""

from collections import deque
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def effective_roles(snapshot):
    groups = {g.id: g for g in snapshot.groups}
    identities = {i.id: set(i.roles) for i in snapshot.identities}
    roles = set(snapshot.roles)
    if len(groups) != len(snapshot.groups) or sum(len(g.member_groups) + len(g.members) for g in groups.values()) > 20000:
        raise ValueError("IAM groups repeat IDs or exceed the membership bound")
    incoming = {g: 0 for g in groups}
    inherited = {g.id: set(g.roles) for g in groups.values()}
    for group in groups.values():
        if (set(group.roles) - roles or set(group.members) - identities.keys()
                or set(group.member_groups) - groups.keys()
                or len(set(group.members)) != len(group.members)
                or len(set(group.member_groups)) != len(group.member_groups)):
            raise ValueError("IAM group has unknown or repeated roles/members/groups")
        for child in group.member_groups:
            incoming[child] += 1
    queue = deque(g for g, count in incoming.items() if not count)
    visited = 0
    while queue:
        key = queue.popleft()
        visited += 1
        group = groups[key]
        for identity in group.members:
            identities[identity].update(inherited[key])
        for child in group.member_groups:
            inherited[child].update(inherited[key])
            incoming[child] -= 1
            if not incoming[child]: queue.append(child)
    if visited != len(groups):
        raise ValueError("IAM group inheritance contains a cycle")
    if sum(map(len, identities.values())) > 20000:
        raise ValueError("Effective IAM grants exceed the bounded comparison")
    return {key: sorted(value) for key, value in identities.items()}


def iam_drift(previous, current):
    from .specialists import instant
    if instant(previous.observed_at) >= instant(current.observed_at):
        raise ValueError("IAM baseline must precede the current snapshot")
    before, after = effective_roles(previous), effective_roles(current)
    old, new = {i.id: i for i in previous.identities}, {i.id: i for i in current.identities}
    changes = []
    for key in sorted(before.keys() | after.keys()):
        gained = sorted(set(after.get(key, [])) - set(before.get(key, [])))
        lost = sorted(set(before.get(key, [])) - set(after.get(key, [])))
        states = {field: {"before": getattr(old[key], field), "after": getattr(new[key], field)}
                  for field in ('active', 'privileged', 'mfa_enabled')
                  if key in old and key in new and getattr(old[key], field) != getattr(new[key], field)}
        if gained or lost or states or key not in old or key not in new:
            changes.append({"identity": key, "added_roles": gained, "removed_roles": lost,
                            "state_changes": states, "membership": 'added' if key not in old else 'removed' if key not in new else 'retained'})
    return {"baseline": previous.snapshot_id, "current": current.snapshot_id,
            "role_catalog_added": sorted(set(current.roles)-set(previous.roles)),
            "role_catalog_removed": sorted(set(previous.roles)-set(current.roles)),
            "privileged_roles_added": sorted(set(current.privileged_roles)-set(previous.privileged_roles)),
            "privileged_roles_removed": sorted(set(previous.privileged_roles)-set(current.privileged_roles)),
            "changes": changes, "basis": "supplied_snapshots_only", "production_operation": "not_verified"}


def evaluate_causal_tests(case, hypotheses, sources):
    from .specialists import check_evidence
    outcomes = case.test_outcomes if case else []
    if len({t.id for t in outcomes}) != len(outcomes):
        raise ValueError("Causal tests need unique IDs")
    ids = {h.id for h in hypotheses}
    if hypotheses and any(t.hypothesis_id not in ids for t in outcomes):
        raise ValueError("Causal test refers to an unknown hypothesis")
    for test in outcomes:
        check_evidence(test.evidence, sources)
    result = []
    for key in sorted(ids):
        tests = [t for t in outcomes if t.hypothesis_id == key]
        support = sum(t.outcome == 'supporting' and bool(t.evidence) for t in tests)
        refute = sum(t.outcome == 'refuting' and bool(t.evidence) for t in tests)
        grade = 'conflicting' if support and refute else 'refuted_by_supplied_tests' if refute else 'supported_by_supplied_tests' if support else 'unconfirmed'
        result.append({"hypothesis_id": key, "supporting_located_tests": support,
                       "refuting_located_tests": refute, "evidence_grade": grade})
    return {"tests": [t.model_dump() for t in outcomes], "hypothesis_checks": result,
            "verification": "supplied_outcomes_unverified", "root_cause_status": "unconfirmed"}


def business_seconds(start, end, calendar):
    """Intersect at most 367 local dates with explicit working hours and holidays."""
    if end < start or end - start > timedelta(days=366):
        raise ValueError("Business duration must be nonnegative and at most 366 days")
    zone = ZoneInfo(calendar.timezone)
    day, last = start.astimezone(zone).date(), end.astimezone(zone).date()
    total = 0.0
    while day <= last:
        if day.weekday() in calendar.weekdays and day.isoformat() not in calendar.holidays:
            def boundary(minutes):
                naive = datetime.combine(day, datetime.min.time()) + timedelta(minutes=minutes)
                local = naive.replace(tzinfo=zone)
                if local.utcoffset() != naive.replace(tzinfo=zone, fold=1).utcoffset():
                    raise ValueError("Ambiguous working-hour boundary needs an unambiguous calendar")
                if local.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != naive:
                    raise ValueError("Nonexistent working-hour boundary needs an unambiguous calendar")
                return local.astimezone(timezone.utc)
            low = max(start.astimezone(timezone.utc), boundary(calendar.start_minute))
            high = min(end.astimezone(timezone.utc), boundary(calendar.end_minute))
            total += max(0, (high-low).total_seconds())
        day += timedelta(days=1)
    return total
