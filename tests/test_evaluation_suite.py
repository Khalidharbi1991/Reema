"""The synthetic evaluation gate and grader never make an unapproved model call."""

import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from types import SimpleNamespace

import pytest

from scripts import evaluate_agents as evaluation
from tests.test_phase01 import catalog

CASES=evaluation.read_suite()[0]['cases']


@pytest.mark.parametrize('case',CASES,ids=lambda case:case['id'])
@pytest.mark.parametrize('failure',['missing','wrong','invented','invalid'])
def test_each_case_rejects_negative_answers(case,failure):
    answer=dict(case['expected'])
    if failure=='missing': answer.pop(next(iter(answer)))
    if failure=='wrong': answer[next(iter(answer))]=None
    if failure=='invented': answer['human_approval']='I approved it'
    response='not JSON' if failure=='invalid' else json.dumps(answer)
    assert not evaluation.grade(response,case)['passed']
    assert evaluation.grade(json.dumps(case['expected']),case)['passed']


@pytest.mark.asyncio
async def test_offline_baseline_covers_every_role_without_model_client(catalog,monkeypatch):
    import anthropic
    constructor=MagicMock(side_effect=AssertionError('No live client in offline mode'))
    monkeypatch.setattr(anthropic,'AsyncAnthropic',constructor)
    report=await evaluation.run_suite(catalog)
    assert report['passed']==report['total']==22 and report['mode']=='offline_mock'
    assert {r['role'] for r in report['results']}==evaluation.ROLES
    constructor.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('change',['absent','wrong-hash','changed-model','changed-file','changed-budget'])
async def test_live_gate_requires_exact_unchanged_material_before_client_creation(catalog,monkeypatch,tmp_path,change):
    import anthropic
    constructor=MagicMock(side_effect=AssertionError('Gate must fail before client creation'))
    monkeypatch.setattr(anthropic,'AsyncAnthropic',constructor)
    plan=evaluation.proposal(catalog);approval=plan['material_sha256']
    if change=='absent':approval=None
    if change=='wrong-hash':approval='0'*64
    if change=='changed-model':catalog.agents_config['secretary_agent']['model']='different-model'
    if change=='changed-file':
        file=tmp_path/'prompts.json';prompts=json.loads(evaluation.PROMPTS.read_text());prompts['secretary_agent']+=' Changed.'
        file.write_text(json.dumps(prompts));monkeypatch.setattr(evaluation,'PROMPTS',file)
        # A material file outside the suite root is also conservatively rejected.
    if change=='changed-budget':catalog.system_config.model_prices={plan['models'][0]:(1000.0,1000.0)}
    with pytest.raises((PermissionError,ValueError)):
        await evaluation.run_suite(catalog,live=True,approved_proposal=plan,authorize_material_sha256=approval)
    constructor.assert_not_called()


def test_proposal_contains_exact_payloads_and_bounded_egress(catalog):
    plan=evaluation.proposal(catalog)
    assert plan['request_count']==22 and plan['retries']==0 and plan['concurrency']==1
    assert plan['modeled_cost_ceiling_usd']<=plan['maximum_modeled_cost_usd']
    serialized=json.dumps(plan['requests'],ensure_ascii=False)
    assert 'knowledge_records' not in serialized and 'reference_manifest' not in serialized
    assert plan['material_sha256']==evaluation.digest({k:v for k,v in plan.items() if k!='material_sha256'})


@pytest.mark.asyncio
async def test_live_provider_failure_preserves_partial_report_and_stops_paid_attempts(catalog,monkeypatch):
    import anthropic
    client=SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(side_effect=RuntimeError('Synthetic outage'))),close=AsyncMock())
    monkeypatch.setattr(anthropic,'AsyncAnthropic',MagicMock(return_value=client))
    plan=evaluation.proposal(catalog)
    report=await evaluation.run_suite(catalog,live=True,approved_proposal=plan,authorize_material_sha256=plan['material_sha256'])
    assert report['status']=='interrupted' and report['attempted']==1 and len(report['not_attempted'])==21
    assert report['usage']['accounted_tokens']>0
    client.messages.create.assert_awaited_once();client.close.assert_awaited_once()


@pytest.mark.parametrize('family,role_model,expected',[
    ('claude-sonnet-4-6',None,'claude-sonnet-4-6'),
    ('user-family-model',None,'user-family-model'),
    ('user-family-model','user-role-model','user-role-model'),
])
def test_actual_agents_and_proposal_preserve_family_and_role_model_overrides(catalog,monkeypatch,family,role_model,expected):
    from src.agents import base_agent,leader_agent
    from src.agents.research_agent import ResearchAgent
    monkeypatch.setattr(base_agent,'config_manager',catalog);monkeypatch.setattr(leader_agent,'config_manager',catalog)
    catalog.system_config.worker_model=family;catalog.system_config.leader_model=family
    for role in ['research_agent','leader_agent']:catalog.agents_config[role]['model']=role_model
    assert ResearchAgent(api_key='').model==expected
    assert leader_agent.LeaderAgent(api_key='').model==expected
    selected=[item['request']['model'] for item in evaluation.requests(catalog) if item['role'] in ['research_agent','leader_agent']]
    assert selected==[expected]*4


def test_environment_model_overrides_survive_default_maintenance(monkeypatch):
    from src.utils.config import SystemConfig
    monkeypatch.setenv('LEADER_MODEL','user-leader-override');monkeypatch.setenv('WORKER_MODEL','user-worker-override')
    settings=SystemConfig(_env_file=None)
    assert settings.leader_model=='user-leader-override' and settings.worker_model=='user-worker-override'
