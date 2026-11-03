"""Versioned synthetic role evaluation, offline only: grades the canonical answers. REEMA makes no model call."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATASET = ROOT / 'evaluations/v1/cases.json'
PROMPTS = ROOT / 'evaluations/v1/prompts.json'
ROLES = {'secretary_agent','leader_agent','research_agent','standards_agent','content_agent',
         'review_agent','format_agent','access_agent','problem_agent','data_agent','building_design_agent',
         'euc_agent'}


def read_suite():
    dataset=json.loads(DATASET.read_text(encoding='utf-8'))
    prompts=json.loads(PROMPTS.read_text(encoding='utf-8'))
    if dataset['version'] != 1 or set(prompts) != ROLES:
        raise ValueError('Evaluation version/role inventory is invalid')
    cases=dataset['cases']
    if (len(cases)>50 or len({c['id'] for c in cases})!=len(cases)
            or {c['role'] for c in cases}!=ROLES
            or any(not c['expected'] or not c['rubric'] for c in cases)):
        raise ValueError('Evaluation needs bounded unique cases, every role, expected facts and rubrics')
    return dataset,prompts


def grade(response, case):
    """Exact supplied facts and authority boundaries; prose quality is a human rubric."""
    try:
        answer=json.loads(response)
        if not isinstance(answer,dict) or set(answer)-set(case['expected'])-{'explanation'}:
            raise ValueError('Unexpected answer fields')
        checks={key: type(answer.get(key)) is type(value) and answer.get(key)==value
                for key,value in case['expected'].items()}
        if 'explanation' in answer and (not isinstance(answer['explanation'],str) or len(answer['explanation'])>2000):
            raise ValueError('Invalid explanation')
    except (ValueError,TypeError):
        checks={key:False for key in case['expected']}
    return {'case_id':case['id'],'role':case['role'],'passed':all(checks.values()),
            'fact_checks':checks,'rubric':case['rubric'],'human_quality_review':'not_performed'}


def run_suite():
    """Grade every case's expected answer: proves the fixtures and the grader, never a model."""
    dataset,_=read_suite()
    answers=[grade(json.dumps(case['expected'],ensure_ascii=False),case) for case in dataset['cases']]
    files={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [DATASET,PROMPTS,Path(__file__).resolve()]}
    return {'version':1,'recorded_at':datetime.now(timezone.utc).isoformat(),'mode':'offline_fixture','files':files,
            'status':'complete','passed':sum(a['passed'] for a in answers),'total':len(dataset['cases']),'results':answers,
            'interpretation':'Offline results verify the expected-answer fixtures and the grader only. They do not measure any model or agent. Rubrics need human review.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['offline'])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=run_suite()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(args.output)


if __name__=='__main__': main()
