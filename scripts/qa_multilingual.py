"""Offline synthetic Arabic/mixed-script export fixture; no generation or approval."""

import argparse
import asyncio
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


async def generate(output):
    from src.agents.format_agent import FormatAgent
    from src.utils.config import config_manager
    from src.utils.documents import SectionDraft, SectionBody
    from src.utils.quality import quality_report
    original=config_manager.document_profile
    titles=['المقدمة','التعريفات والمختصرات','الأدوار والمسؤوليات','نظرة عامة على الإجراء',
            'الخطوات التفصيلية','مسار العملية','مؤشرات الأداء','الأدوات والأنظمة','الضوابط والمعايير','الملاحق','ضبط الوثيقة']
    profile=original.model_copy(deep=True)
    profile.document_label='إجراء تشغيلي'
    for section,title in zip(profile.sections,titles): section.display_title=title
    flow={'kind':'graph','title':'مراجعة طلب الصلاحيات','lanes':[{'id':'user','label':'المستخدم'},{'id':'owner','label':'فريق الخدمة'}],
        'nodes':[{'id':'start','label':'تسجيل الطلب','owner':'المستخدم','lane':'user','row':0,'kind':'start'},
                 {'id':'check','label':'مراجعة الطلب','owner':'المالك','lane':'owner','row':1,'kind':'decision'},
                 {'id':'allow','label':'تفعيل الصلاحية','owner':'الدعم','lane':'owner','row':2,'kind':'end'},
                 {'id':'deny','label':'إبلاغ المستخدم','owner':'المستخدم','lane':'user','row':2,'kind':'end'}],
        'edges':[{'source':'start','target':'check'},{'source':'check','target':'allow','label':'موافق'},
                 {'source':'check','target':'deny','label':'مرفوض'}]}
    bodies=[
        'ينظم هذا الإجراء تسجيل طلبات الخدمة ومراجعتها. يحدد مالك الخدمة الموافقة المطلوبة قبل التنفيذ، ويحتفظ فريق الدعم بسجل القرار.\n\nThe service owner reviews each request before support acts. The example contains invented records only.',
        '| المصطلح | التعريف |\n|---|---|\n| MFA | التحقق متعدد العوامل |\n| REQ 104 | مرجع طلب تجريبي |',
        '| النشاط | مالك الخدمة | فريق الدعم |\n|---|---|---|\n| مراجعة الطلب | A | R |\n| توثيق القرار | A | R |',
        'يبدأ المسار بطلب موثق وينتهي بقرار مسجل. إذا كانت المعلومات ناقصة، يطلب مالك الخدمة توضيحها قبل اتخاذ القرار.\n\nInput: a request record. Output: a documented decision and follow-up action.',
        '1. يسجل المستخدم الطلب مع وصف الحاجة.\n2. يتحقق مالك الخدمة من المتطلبات والأدلة المتاحة.\n3. ينفذ الدعم القرار المصرح به ويوثق النتيجة.\n\nرقم الطلب REQ 104، موعد المراجعة 2026-10-16، والحالة قيد المراجعة.',
        'يوضح المسار قرار الموافقة والرفض والمسؤولية في كل مرحلة.\n\n```reema-flow\n'+json.dumps(flow,ensure_ascii=False)+'\n```',
        '| المؤشر | طريقة الحساب | الوحدة |\n|---|---|---|\n| نسبة الطلبات المكتملة | 100 × المكتمل ÷ الإجمالي | percent |\n| مدة المعالجة | النهاية ناقص البداية | hours |\n| المرجع الأخير | REQ 999 | record |\n\nالبيانات غير متاحة لهذا المثال؛ لا توجد نتائج أداء فعلية.',
        'يستخدم الفريق سجل الطلبات وأداة إدارة الخدمة المصرح بها. لا يمنح هذا المستند صلاحيات أو يرسل رسائل إلى أنظمة خارجية.\n\nThe tool name and access route require owner confirmation.',
        'متطلبات الموافقة وحفظ الأدلة تنتظر تأكيد مالك الضوابط. لا تعني الإشارة إلى معيار أن التطبيق الفعلي تم التحقق منه.\n\nCompliance and implementation evidence remain unverified.',
        'تتضمن قائمة التحقق مرجع الطلب، واسم المراجع، والقرار، وتاريخ المتابعة. يحتفظ الفريق بالمرفقات في الموقع الذي يحدده مالك الخدمة.',
        'الإصدار 1.0. المالك المقترح هو مالك الخدمة. المراجعة البشرية معلقة، والتوقيع غير مسجل.\n\nStatus: `awaiting_human_approval`. No person has approved these synthetic artifacts.'
    ]
    draft=SectionDraft(sections=[SectionBody(section_id=s.id,body=b) for s,b in zip(profile.sections,bodies)])
    records=[]
    try:
        for template in ['standard','compact']:
            profile.template=template
            config_manager.document_profile=profile
            content=draft.assemble('إدارة طلبات الخدمة',profile)
            quality=quality_report(content)
            if quality['errors']: raise ValueError(quality['errors'])
            agent=FormatAgent();agent.output_dir=output/template
            files=await agent.convert_to_formats(content,['markdown','html','docx','pdf'],'Synthetic Arabic Service')
            records.append({'template':template,'files':files,'checks':agent.last_export_checks})
            await agent.close()
    finally:
        config_manager.document_profile=original
    output.mkdir(parents=True,exist_ok=True)
    (output/'export-checks.json').write_text(json.dumps(records,ensure_ascii=False,indent=2,default=str)+'\n')
    print(output/'export-checks.json')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();asyncio.run(generate(args.output))
