"""The synthetic evaluation grader, offline only; no model call."""

import json

import pytest

from scripts import evaluate_agents as evaluation

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


def test_offline_baseline_covers_every_role():
    report=evaluation.run_suite()
    assert report['passed']==report['total']==24 and report['mode']=='offline_fixture'
    assert {r['role'] for r in report['results']}==evaluation.ROLES
    assert set(report['files'])=={'evaluations/v1/cases.json','evaluations/v1/prompts.json','scripts/evaluate_agents.py'}


