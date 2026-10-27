"""Package five acceptance checks using synthetic inputs and fake providers only."""

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import ezdxf
import pytest
from pydantic import ValidationError

from src.assistant import AssistantSession
from src.utils.config import config_manager
from src.utils.coordination import IntentResolution
from src.utils.diagrams import parse_flow, png_flow, svg_flow
from src.utils.execution import ExecutionJournal, load_execution
from src.utils.ownership import RunLease
from src.utils.provider import RunRuntime, current_runtime, Completion
from src.utils.quality import assess_all, ComplianceAssessment
from src.utils.runs import RunStore
from src.utils.specialists import (SpecialistPolicy, IAMSnapshot, check_iam, ProblemCase,
    Hypothesis, assess_problem, MetricSpec, calculate_metric, SpecialistInputs)
from src.utils.domain_depth import iam_drift
from tests.test_coordination_package import chat, interrupted
from tests.test_phase01 import catalog, pipeline
from tests.test_specialist_package import source, evidence, snapshot, hypotheses, case


@pytest.mark.parametrize('message,agents', [
    ('اكتب إجراء مع الصلاحيات ومؤشرات الأداء', {'content_agent','access_agent','data_agent'}),
    ('اكتب SOP بدون MFA، مع KPI', {'content_agent','data_agent'}),
    ('لَيْسَ فَقَط الأمن لكن مؤشرات الأداء', {'access_agent','data_agent'}),
    ('لا تتجاهل الصلاحيات', {'access_agent'}),
    ('قارن خيارات التصميم الداخلي', {'research_agent','building_design_agent'}),
    ('الصلاحيات غير مطلوب، اكتب مسودة', {'content_agent'}),
    ('Prepare an agenda بدون security', {'content_agent'}),
])
def test_bilingual_intent_preserves_positive_and_negative_clauses(chat, message, agents):
    plan = chat.plan(message)
    assert plan.status == 'ready'
    assert {s.agent for s in plan.selections} == agents


@pytest.mark.parametrize('message', ['هل نبدأ بدون الصلاحيات؟', 'كملها', 'MFA but no MFA'])
def test_ambiguous_or_unresolved_requests_clarify(chat, message):
    assert chat.plan(message).status == 'needs_clarification'


def test_arabic_followup_inherits_active_roles_except_explicit_exclusions(chat):
    chat.task_context.objective = 'Shared rollout plan'
    chat.task_context.selected_specialists = ['data_agent','access_agent']
    plan = chat.plan('كملها بدون الصلاحيات')
    assert [s.agent for s in plan.selections] == ['data_agent']


@pytest.mark.asyncio
async def test_arabic_local_mutations_and_explicit_context_need_no_model(chat):
    await chat.reply('أضف مهمة: مراجعة الإجراء')
    await chat.reply('قرار: نستخدم الأدوات الحالية')
    await chat.reply('هدف: تحسين المتابعة')
    tasks = chat.agents['secretary_agent'].task_store('work').list(project='Alpha')
    assert tasks[0]['title'] == 'مراجعة الإجراء'
    assert chat.task_context.objective == 'تحسين المتابعة'
    assert any(f.text == 'نستخدم الأدوات الحالية' for f in chat.task_context.decisions.values())
    for agent in chat.agents.values(): agent._call_claude.assert_not_awaited()


def resolution(**updates):
    return {'intent':'advisory','agents':['access_agent'],'excluded_agents':[],
            'status':'ready','questions':[],'rationale':'Explicit supplied scope', **updates}


@pytest.mark.parametrize('updates', [
    {'agents':['send_email']}, {'agents':['access_agent','access_agent']},
    {'excluded_agents':['access_agent']}, {'intent':'local_action'},
    {'status':'needs_clarification','questions':[]},
])
def test_semantic_resolution_contract_rejects_unknown_or_actionable_dispatch(updates):
    with pytest.raises(ValidationError): IntentResolution.model_validate(resolution(**updates))


@pytest.mark.asyncio
async def test_opt_in_resolution_still_requires_input_consent(chat):
    chat.resolve_intent = True
    with pytest.raises(PermissionError): await chat.reply('Explain MFA')
    chat.agents['secretary_agent']._call_claude.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('message,answer', [
    ('Explain KPI without MFA', resolution(agents=['data_agent','access_agent'])),
    ('Explain MFA and KPI', resolution(agents=['access_agent'])),
])
async def test_semantic_resolution_cannot_override_explicit_scope(chat, message, answer):
    chat.resolve_intent = True
    chat.agents['secretary_agent']._call_claude.return_value = json.dumps(answer)
    with pytest.raises(ValueError): await chat.reply(message, allow_external_ai=True)
    chat.agents['access_agent']._call_claude.assert_not_awaited()


@pytest.mark.asyncio
async def test_opt_in_resolution_routes_bounded_advice_and_never_executes_actions(chat):
    chat.resolve_intent = True
    chat.agents['secretary_agent']._call_claude.side_effect = [
        json.dumps(resolution()), json.dumps({'advice':'Synthetic summary'})]
    result = await chat.reply('Explain MFA', allow_external_ai=True)
    assert result['consulted_agents'] == ['Agent 6']
    assert chat.agents['secretary_agent']._call_claude.await_count == 2
    before = chat.agents['secretary_agent']._call_claude.await_count
    result = await chat.reply('ارسل البريد', allow_external_ai=True)
    assert result['plan']['status'] == 'unsupported'
    assert chat.agents['secretary_agent']._call_claude.await_count == before


CHILD_OWNER = '''
import sys
from pathlib import Path
from src.utils.config import ConfigManager, SystemConfig
from src.utils.coordination import DocumentationRequest
from src.utils.runs import RunStore
from src.utils.execution import ExecutionJournal
root=Path(sys.argv[1])
config=ConfigManager(SystemConfig(_env_file=None, project_root=root, config_dir=root/'config', output_dir=root/'output'))
store=RunStore(root/'output/runs/child', 'Synthetic', ['markdown'])
request=DocumentationRequest(process_name='Synthetic',formats=['markdown'],objective='Synthetic checks')
journal=ExecutionJournal(store,config,request,{'synthetic':'same'})
store.state['usage']={'accounted_tokens':2048,'in_flight':[{'reserved_tokens':2048}]}
store.flush()
print('READY',flush=True)
sys.stdin.read()
'''


def owner_child(catalog):
    process = subprocess.Popen([sys.executable,'-c',CHILD_OWNER,str(catalog.system_config.project_root)],
        cwd=Path(__file__).resolve().parents[1], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # A finite readiness timeout also exposes an import/config failure cleanly.
    import selectors
    selector=selectors.DefaultSelector(); selector.register(process.stdout,selectors.EVENT_READ)
    try:
        if not selector.select(10): raise AssertionError('Owner subprocess did not start')
        assert process.stdout.readline().strip() == 'READY'
    except BaseException:
        process.kill(); process.wait(timeout=5); raise
    finally: selector.close()
    return process, catalog.system_config.output_dir/'runs/child'


def test_real_owner_blocks_reads_and_hard_kill_releases_authenticated_running_recovery(catalog):
    process, directory = owner_child(catalog)
    try:
        with pytest.raises(RuntimeError, match='active owner'): load_execution(directory,catalog)
        process.kill(); process.wait(timeout=5)
        # Simulate a kill between the unsigned run write and the signed commit.
        (directory/'run.json').write_text('{partial unsigned write')
        record,_ = load_execution(directory,catalog)
        assert record.run_state['status'] == 'running'
        assert record.usage['accounted_tokens'] == 2048 and record.usage['in_flight']
    finally:
        if process.poll() is None: process.kill(); process.wait(timeout=5)
        for stream in [process.stdin,process.stdout,process.stderr]: stream.close()


@pytest.mark.asyncio
async def test_concurrent_resumer_cannot_enter_parent_while_first_resume_is_running(pipeline):
    leader,config,workers=pipeline
    directory=await interrupted(pipeline)
    entered,release=asyncio.Event(),asyncio.Event()
    original=leader.generate_documentation
    async def blocked(*args,**kwargs):
        entered.set(); await release.wait(); return await original(*args,**kwargs)
    leader.generate_documentation=blocked
    task=asyncio.create_task(leader.resume_execution(directory,allow_external_ai=True))
    await asyncio.wait_for(entered.wait(),2)
    try:
        with pytest.raises(RuntimeError,match='active owner'): load_execution(directory,config)
    finally:
        release.set(); await task


def test_ownership_refuses_cross_host_and_symlink(tmp_path):
    with RunLease(tmp_path) as lease:
        with pytest.raises(ValueError,match='Cross-host'): lease.permits(tmp_path,{'host':'other-host'})
        with pytest.raises(RuntimeError,match='already held'): lease.__enter__()
    (tmp_path/'.owner.lock').unlink()
    (tmp_path/'.owner.lock').symlink_to(tmp_path/'other')
    with pytest.raises(ValueError,match='symlink'): RunLease(tmp_path).__enter__()


@pytest.mark.asyncio
async def test_provider_reservation_is_durable_before_transmission_and_unknown_usage_remains_charged(catalog):
    runtime=RunRuntime(catalog.system_config)
    saved=[]; runtime.on_event=lambda summary:saved.append(json.loads(json.dumps(summary)))
    class Provider:
        async def complete(self,**request):
            assert saved[-1]['in_flight'] and saved[-1]['accounted_tokens']>0
            assert 'private body' not in json.dumps(saved[-1])
            raise ValueError('Synthetic response loss')
    with pytest.raises(RuntimeError):
        await runtime.call(Provider(),agent='Test',model='synthetic',max_tokens=100,messages=[{'role':'user','content':'private body'}])
    assert not saved[-1]['in_flight'] and saved[-1]['accounted_tokens']>0
    assert saved[-1]['calls'][0]['unknown_usage_reserved_tokens'] == saved[0]['accounted_tokens']


@pytest.mark.asyncio
async def test_failed_reservation_write_never_transmits(catalog):
    runtime=RunRuntime(catalog.system_config)
    def fail(summary): raise OSError('Synthetic disk failure')
    runtime.on_event=fail
    provider=SimpleNamespace(complete=AsyncMock())
    with pytest.raises(OSError): await runtime.call(provider,agent='Test',model='synthetic',max_tokens=100)
    provider.complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_review_chunk_checkpoint_survives_interruption_and_revalidates_cached_results(catalog,monkeypatch):
    monkeypatch.setattr(config_manager.system_config,'review_chunk_chars',1000)
    from src.utils.coordination import DocumentationRequest
    store=RunStore(catalog.system_config.output_dir/'runs/chunks','Synthetic',['markdown'])
    request=DocumentationRequest(process_name='Synthetic',formats=['markdown'],objective='Synthetic')
    journal=ExecutionJournal(store,catalog,request,{'synthetic':'stable'})
    runtime=RunRuntime(catalog.system_config);runtime.execution_journal=journal
    token=current_runtime.set(runtime)
    answer=json.dumps({'compliant':False,'findings':['Needs owner evidence'],'summary':'Unverified'})
    worker=SimpleNamespace(name='Review',model='synthetic',_build_system_prompt=lambda:'Synthetic system',
        _call_claude=AsyncMock(side_effect=[answer,RuntimeError('Synthetic outage')]))
    content=('First excerpt. '*60)+'\n\n'+('Second excerpt. '*60)
    try:
        with pytest.raises(RuntimeError): await assess_all(worker,content,ComplianceAssessment,'Review supplied data')
        assert len(journal.data['completed_assessments']) == 1
        before=worker._call_claude.await_count
        worker._call_claude.side_effect=None;worker._call_claude.return_value=answer
        results,coverage=await assess_all(worker,content,ComplianceAssessment,'Review supplied data')
        assert coverage['chunks_reviewed']>=2 and worker._call_claude.await_count-before == len(results)-1
        checkpointed=worker._call_claude.await_count
        def invalid(result,offset,part): raise ValueError('Synthetic invalid location')
        with pytest.raises(ValueError): await assess_all(worker,content,ComplianceAssessment,'Review supplied data',invalid)
        assert worker._call_claude.await_count == checkpointed
        await assess_all(worker,content,ComplianceAssessment,'Changed review instructions')
        assert worker._call_claude.await_count > checkpointed
    finally:
        current_runtime.reset(token);store.close()


def graph():
    return {'kind':'graph','title':'طلب الصلاحيات','lanes':[{'id':'user','label':'المستخدم'},{'id':'owner','label':'المالك'}],
        'nodes':[{'id':'start','label':'تسجيل الطلب','owner':'المستخدم','lane':'user','row':0,'kind':'start'},
                 {'id':'check','label':'الموافقة على الطلب','owner':'المالك','lane':'owner','row':1,'kind':'decision'},
                 {'id':'allow','label':'تفعيل الصلاحية','owner':'الدعم','lane':'owner','row':2,'kind':'end'},
                 {'id':'deny','label':'إبلاغ المستخدم','owner':'المستخدم','lane':'user','row':2,'kind':'end'}],
        'edges':[{'source':'start','target':'check'}, {'source':'check','target':'allow','label':'موافق'},
                 {'source':'check','target':'deny','label':'مرفوض'}]}


def test_multilingual_graph_renders_both_branches_and_terminal_owners():
    flow=parse_flow(json.dumps(graph()));svg=svg_flow(flow)
    assert 'موافق' in svg and 'مرفوض' in svg and 'direction="rtl"' in svg
    assert 'الدعم' in flow.description()
    assert png_flow(flow).read(8) == b'\x89PNG\r\n\x1a\n'


@pytest.mark.parametrize('change',['cycle','missing','overlap','unlabelled','unknown','control','nondecision'])
def test_invalid_graphs_fail_before_rendering(change):
    value=graph()
    if change=='cycle': value['edges'][0]={'source':'check','target':'start'}
    if change=='missing': value['edges']=value['edges'][:1]
    if change=='overlap': value['nodes'][3]['lane']='owner'
    if change=='unlabelled': value['edges'][1].pop('label')
    if change=='unknown': value['edges'][1]['target']='absent'
    if change=='control': value['title']='Hidden\u202e'
    if change=='nondecision': value['nodes'][1]['kind']='step'
    with pytest.raises(ValueError): parse_flow(json.dumps(value))


def grouped():
    value=snapshot();value['roles']=['operator','approver'];value['identities'][0].update(roles=[],privileged=False,mfa_enabled=False)
    value['groups']=[{'id':'parent','roles':['operator'],'members':[],'member_groups':['child']},
                     {'id':'child','roles':['approver'],'members':['account-1'],'member_groups':[]}]
    value['privileged_roles']=['operator']
    return value


def test_iam_inherited_roles_privilege_conflicts_and_supplied_drift():
    value=grouped();policy=SpecialistPolicy(separation_of_duties=[['operator','approver']])
    result=check_iam(value,{'SRC-fixture':source()},policy)
    assert result['effective_roles']['account-1']==['approver','operator']
    assert any(c['check']=='privileged_mfa' and c['result']=='fail' for c in result['checks'])
    assert any(c['check']=='separation_of_duties' for c in result['checks'])
    old=snapshot();old['observed_at']='2026-10-14T12:00:00+03:00'
    drift=iam_drift(IAMSnapshot.model_validate(old),IAMSnapshot.model_validate(value))
    assert drift['changes'][0]['added_roles']==['approver'] and drift['production_operation']=='not_verified'
    assert drift['privileged_roles_added']==['operator'] and drift['role_catalog_added']==['approver']


@pytest.mark.parametrize('change',['cycle','unknown-member','unknown-role','future-baseline'])
def test_invalid_iam_group_or_drift_inputs_are_rejected(change):
    value=grouped()
    if change=='cycle':value['groups'][1]['member_groups']=['parent']
    if change=='unknown-member':value['groups'][1]['members']=['absent']
    if change=='unknown-role':value['groups'][0]['roles']=['absent']
    with pytest.raises(ValueError):
        if change=='future-baseline': iam_drift(IAMSnapshot.model_validate(value),IAMSnapshot.model_validate(value))
        else: check_iam(value,{'SRC-fixture':source()},SpecialistPolicy())


def test_causal_support_refutation_conflicts_never_confirm_real_root_cause():
    value=case();value['test_outcomes']=[{'id':'TEST-support','hypothesis_id':'HYP-config','observed_at':'2026-10-15T11:00:00Z',
        'criterion':'Replay under the supplied condition','outcome':'supporting','evidence':[evidence()]},
        {'id':'TEST-refute','hypothesis_id':'HYP-config','observed_at':'2026-10-15T12:00:00Z',
        'criterion':'Repeat without the condition','outcome':'refuting','evidence':[evidence()]}]
    result=assess_problem(ProblemCase.model_validate(value),[Hypothesis.model_validate(h) for h in hypotheses()],{'SRC-fixture':source()},SpecialistPolicy())
    assert result['causal_tests']['hypothesis_checks'][0]['evidence_grade']=='conflicting'
    assert result['root_cause_status']=='unconfirmed'
    value['test_outcomes'][0]['hypothesis_id']='HYP-absent'
    with pytest.raises(ValueError): assess_problem(value,[Hypothesis.model_validate(h) for h in hypotheses()],{'SRC-fixture':source()},SpecialistPolicy())


def newmetric(kind,**kwargs):
    return MetricSpec(id='MET-new',name='Synthetic',kind=kind,unit='number',owner='Owner',source='Supplied rows',cadence='Weekly',**kwargs)


def test_explicit_formulas_and_located_lineage_are_recomputed():
    spec=newmetric('weighted_mean',value_field='value',weight_field='weight',evidence=[evidence()])
    result=calculate_metric(spec,[{'value':10,'weight':1},{'value':20,'weight':3}],SpecialistPolicy(),{'SRC-fixture':source()})
    assert result['value']==17.5 and result['lineage_status']=='located_unverified'
    assert calculate_metric(newmetric('difference',value_field='a',subtrahend_field='b'),[{'a':2,'b':5}],SpecialistPolicy())['value']==-3
    assert calculate_metric(spec,[{'value':1,'weight':0}],SpecialistPolicy())['status']=='undefined_zero_denominator'
    with pytest.raises(ValueError): calculate_metric(spec,None,SpecialistPolicy(),{})


def calendar_metric(**updates):
    return MetricSpec.model_validate({'id':'MET-work','name':'Working duration','kind':'business_duration_mean',
        'unit':'hours','owner':'Owner','source':'Supplied timestamps','cadence':'Weekly','start_field':'start','end_field':'end',
        'calendar':{'timezone':'Asia/Riyadh','weekdays':[6,0,1,2,3],'start_minute':540,'end_minute':1020,'holidays':['2026-10-18']},**updates})


def test_calendar_excludes_weekends_holidays_and_preserves_explicit_timezone():
    rows=[{'start':'2026-10-15T16:00:00+03:00','end':'2026-10-19T10:00:00+03:00'}]
    assert calculate_metric(calendar_metric(),rows,SpecialistPolicy())['value']==2
    with pytest.raises(ValueError): calculate_metric(calendar_metric(),[{'start':'2024-01-01T00:00:00Z','end':'2026-01-01T00:00:00Z'}],SpecialistPolicy())
    with pytest.raises(ValueError): calendar_metric(calendar={'timezone':'Unknown/Zone','weekdays':[0],'start_minute':600,'end_minute':500})


def test_calendar_rejects_ambiguous_dst_work_boundary():
    from src.utils.domain_depth import business_seconds
    from src.utils.specialists import BusinessCalendar, instant
    cal=BusinessCalendar(timezone='America/New_York',weekdays=[6],start_minute=90,end_minute=180)
    with pytest.raises(ValueError,match='Ambiguous'):
        business_seconds(instant('2026-11-01T00:00:00-04:00'),instant('2026-11-01T04:00:00-05:00'),cal)


@pytest.mark.asyncio
async def test_retrieval_does_not_erase_pinned_excerpt_text(catalog):
    from src.agents import ResearchAgent
    agent=ResearchAgent(api_key='synthetic')
    agent.source_records=[source()];agent.knowledge_records=[]
    runtime=RunRuntime(catalog.system_config);runtime.sources={'SRC-fixture':source()}
    runtime.call=AsyncMock(return_value='Synthetic')
    token=current_runtime.set(runtime)
    try:
        await agent._call_claude([{'role':'user','content':'decision record'}])
        assert runtime.sources['SRC-fixture']['text']==source()['text']
    finally:
        current_runtime.reset(token);await agent.close()


def test_explicit_cad_units_layers_and_proxy_rotation_are_retained(tmp_path,monkeypatch):
    from src.utils.cad_model import generate_concept_model
    drawing=ezdxf.new();drawing.header['$INSUNITS']=4
    drawing.layers.new('WALL-CUSTOM');drawing.layers.new('FURNITER')
    drawing.modelspace().add_line((1000,1000),(5000,1000),dxfattribs={'layer':'WALL-CUSTOM'})
    drawing.blocks.new('FURN');drawing.modelspace().add_blockref('FURN',(3000,3000),dxfattribs={'layer':'FURNITER','rotation':45})
    path=tmp_path/'synthetic.dxf';drawing.saveas(path)
    monkeypatch.setattr(config_manager.specialist_policy,'cad_wall_layers',['WALL-CUSTOM'])
    result=generate_concept_model(path,tmp_path/'model',(0,0,6,6),source_units='millimetres')
    checks=result['geometry_checks'];entry=checks['selected_region_evidence'][0]
    assert entry['selected_start']==[1.0,1.0] and entry['raw_start']==[1000.0,1000.0]
    assert checks['insert_transforms'][0]['rotation_deg']==45 and result['furniture_proxies']==1
    with pytest.raises(ValueError,match='units'): generate_concept_model(path,tmp_path/'wrong',(0,0,6,6))


@pytest.mark.asyncio
async def test_pdf_presence_checks_keep_arabic_headings_cells_and_mixed_identifiers(tmp_path):
    from src.formatters.pdf_formatter import PDFFormatter
    from src.utils.export_quality import inspect_export
    content='# موجز الخدمة\n\n## 10. المقدمة\n\nتم تسجيل الطلب REQ 104 للمراجعة.\n\n| المؤشر | القيمة |\n|---|---|\n| نسبة الطلبات | REQ 999 |\n'
    file=tmp_path/'synthetic.pdf'
    await PDFFormatter().convert(content,file,'Synthetic')
    assert inspect_export('pdf',file,content)['status']=='passed'
    with pytest.raises(ValueError,match='heading'):
        inspect_export('pdf',file,content.replace('المقدمة','عنوان مفقود'))
    with pytest.raises(ValueError,match='table cell'):
        inspect_export('pdf',file,content.replace('REQ 999','REQ 998'))


def test_graph_wide_text_fails_instead_of_clipping():
    value=graph();value['nodes'][0]['label']='W'*60
    with pytest.raises(ValueError,match='Shorten'): png_flow(parse_flow(json.dumps(value)))


def test_pdf_raster_resources_are_generated_locally_and_untrusted_images_stay_escaped():
    from src.formatters.safe_html import render_markdown
    resources={}
    html=render_markdown('```reema-flow\n'+json.dumps(graph())+'\n```\n<img src="file:///private/customer">',raster_resources=resources)
    assert len(resources)==1 and next(iter(resources.values())).startswith(b'\x89PNG')
    assert 'class="flow-raster"' in html and '<img src="file:' not in html


@pytest.mark.asyncio
async def test_word_rtl_uses_logical_start_and_matching_complex_script_style(tmp_path):
    from src.formatters.docx_formatter import DOCXFormatter
    from docx import Document
    from docx.oxml.ns import qn
    path=tmp_path/'synthetic.docx'
    await DOCXFormatter().convert('# مراجعة الخدمة\n\nهذا طلب تجريبي.\n',path,'Synthetic')
    document=Document(path)
    paragraph=document.paragraphs[1]
    assert paragraph._p.find(qn('w:pPr')).find(qn('w:jc')).get(qn('w:val'))=='start'
    caption=document.styles['Caption'].element.get_or_add_rPr()
    assert caption.find(qn('w:bCs')).get(qn('w:val'))=='0'


@pytest.mark.asyncio
async def test_mixed_rtl_dates_and_identifiers_are_isolated_without_changing_text(tmp_path):
    from src.formatters.safe_html import render_markdown
    from src.formatters.docx_formatter import DOCXFormatter
    from docx import Document
    from docx.oxml.ns import qn
    from bs4 import BeautifulSoup
    text='رقم الطلب REQ 104، موعد المراجعة 2026-10-16، والحالة قيد المراجعة.'
    soup=BeautifulSoup(render_markdown(text),'html.parser')
    assert soup.find('bdi',string='2026-10-16')['dir']=='ltr'
    assert soup.get_text().strip()==text
    file=tmp_path/'synthetic.docx'
    await DOCXFormatter().convert(text,file,'Synthetic')
    paragraph=Document(file).paragraphs[0]
    assert paragraph.text.replace('\u200e','')==text
    date=next(run for run in paragraph.runs if run.text.strip('\u200e')=='2026-10-16')
    assert date.text=='\u200e2026-10-16\u200e'
    assert date._r.get_or_add_rPr().find(qn('w:rtl')).get(qn('w:val'))=='0'
