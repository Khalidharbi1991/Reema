"""A bounded sequence diagram, rendered locally without XML or resource fetches."""

from html import escape
from io import BytesIO
import json
import re
import textwrap
import unicodedata

from pydantic import Field, model_validator
from .documents import Contract


class FlowStep(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,30}$")
    label: str = Field(min_length=1, max_length=60)
    owner: str = Field(min_length=1, max_length=32)


class SequenceFlow(Contract):
    title: str = Field(min_length=1, max_length=60)
    steps: list[FlowStep] = Field(min_length=2, max_length=6)

    @model_validator(mode="after")
    def safe_labels(self):
        if len({s.id for s in self.steps}) != len(self.steps):
            raise ValueError("Diagram step IDs must be unique")
        validate_labels([self.title, *[t for s in self.steps for t in (s.label, s.owner)]])
        return self

    def description(self):
        return self.title + ": " + " -> ".join(f"{i}. {s.label} ({s.owner})" for i, s in enumerate(self.steps, 1))

    def dimensions(self): return (640, 55 + 106 * len(self.steps))


def validate_labels(labels):
    if any(any(not c.isprintable() or unicodedata.category(c) in {'Cf','Cs'} for c in text) for text in labels):
        raise ValueError("Diagram labels cannot contain invisible/control characters")


class Lane(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,30}$")
    label: str = Field(min_length=1, max_length=32)


class GraphNode(FlowStep):
    lane: str
    row: int = Field(ge=0, le=5)
    kind: str = Field(pattern=r"^(step|decision|end|start)$")


class GraphEdge(Contract):
    source: str
    target: str
    label: str | None = Field(default=None, max_length=24)


class GraphFlow(Contract):
    kind: str = Field(pattern=r"^graph$")
    title: str = Field(min_length=1, max_length=60)
    lanes: list[Lane] = Field(min_length=1, max_length=3)
    nodes: list[GraphNode] = Field(min_length=2, max_length=8)
    edges: list[GraphEdge] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def graph(self):
        ids = {n.id: n for n in self.nodes}
        lanes = {l.id for l in self.lanes}
        if len(ids) != len(self.nodes) or len(lanes) != len(self.lanes) or any(n.lane not in lanes for n in self.nodes):
            raise ValueError("Diagram IDs/lanes must be unique and known")
        if len({(n.lane,n.row) for n in self.nodes}) != len(self.nodes):
            raise ValueError("Diagram nodes cannot overlap in a lane/row")
        pairs = {(e.source,e.target) for e in self.edges}
        if len(pairs) != len(self.edges): raise ValueError("Duplicate diagram edge")
        incoming = {n:0 for n in ids}
        outgoing = {n:[] for n in ids}
        for edge in self.edges:
            if edge.source not in ids or edge.target not in ids or ids[edge.source].row >= ids[edge.target].row:
                raise ValueError("Diagram edges must connect known nodes in forward rows")
            incoming[edge.target] += 1
            outgoing[edge.source].append(edge)
        roots = [n for n in ids if not incoming[n]]
        if len(roots) != 1: raise ValueError("Diagram needs exactly one reachable start")
        reached = set(roots)
        for node in sorted(self.nodes,key=lambda n:n.row):
            if node.id in reached: reached.update(e.target for e in outgoing[node.id])
            count = len(outgoing[node.id])
            if node.kind == 'decision' and (count != 2 or any(not e.label or not e.label.strip() for e in outgoing[node.id])):
                raise ValueError("Decision needs two labelled branches")
            if node.kind != 'decision' and count > 1: raise ValueError("Only a decision may branch")
            if node.kind == 'end' and count: raise ValueError("End nodes cannot have outgoing edges")
        if reached != set(ids): raise ValueError("Diagram has unreachable nodes")
        validate_labels([self.title,*[l.label for l in self.lanes],*[t for n in self.nodes for t in (n.label,n.owner)],*[e.label for e in self.edges if e.label]])
        return self

    @property
    def steps(self): return self.nodes

    def dimensions(self): return (len(self.lanes)*300 + 160, 90 + (max(n.row for n in self.nodes)+1)*190)

    def description(self):
        nodes = {n.id:n for n in self.nodes}
        return self.title + ": " + "; ".join(f"{n.label} ({n.owner})" for n in self.nodes) + ". " + "; ".join(f"{nodes[e.source].label} -> {nodes[e.target].label} [{e.label or ''}]" for e in self.edges)


def parse_flow(text):
    data = json.loads(text)
    return GraphFlow.model_validate(data) if isinstance(data,dict) and data.get('kind') == 'graph' else SequenceFlow.model_validate(data)


FLOW_FENCE = re.compile(r"(?m)^```reema-flow[ \t]*\n(.*?)^```[ \t]*$", re.S)


def extract_flows(content):
    matches = list(FLOW_FENCE.finditer(content))
    if len(matches) != len(re.findall(r"(?m)^```reema-flow\b", content)):
        raise ValueError("Unclosed sequence diagram fence")
    return [(m, parse_flow(m.group(1))) for m in matches]


def svg_flow(flow):
    validate_render_text(flow)
    if isinstance(flow,GraphFlow): return graph_svg(flow)
    height = 55 + 106 * len(flow.steps)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="{height}" viewBox="0 0 640 {height}" role="img">',
             f'<title>{escape(flow.description())}</title>', '<g font-family="DejaVu Sans, sans-serif" fill="#222222">',
             svg_text(flow.title,320,24,18)]
    for i, step in enumerate(flow.steps):
        y = 44 + i * 106
        parts.append(f'<rect x="70" y="{y}" width="500" height="80" rx="5" fill="#f5f7fa" stroke="#777777"/>')
        for line, text in enumerate(textwrap.wrap(f"{i + 1}. {step.label}", 50)):
            parts.append(svg_text(text,320,y+22+line*19,16))
        parts.append(svg_text(step.owner,320,y+66,14))
        if i < len(flow.steps) - 1:
            parts.append(f'<path d="M320 {y+80} v20 m-5 -6 l5 6 5 -6" fill="none" stroke="#333333" stroke-width="2"/>')
    return "".join(parts) + "</g></svg>"


def png_flow(flow, font_name="DejaVu Sans"):
    validate_render_text(flow)
    if isinstance(flow,GraphFlow): return graph_png(flow)
    from PIL import Image, ImageDraw, ImageFont
    from ..formatters.typography import diagram_font, drawing_direction
    # Pillow's packaged default is scalable and requires no host font path.
    image = Image.new("RGB", (1280, (55 + 106 * len(flow.steps)) * 2), "white")
    draw = ImageDraw.Draw(image)
    text = ' '.join([flow.title,*[s.label+' '+s.owner for s in flow.steps]])
    font, small, title = [diagram_font(text,n) for n in (32,28,36)]
    draw.text((640, 48), flow.title, font=title, fill="#222222", anchor="ms", **drawing_direction(flow.title))
    for i, step in enumerate(flow.steps):
        y = (44 + i * 106) * 2
        draw.rounded_rectangle((140, y, 1140, y + 160), radius=10, fill="#f5f7fa", outline="#777777", width=2)
        for line, text in enumerate(textwrap.wrap(f"{i + 1}. {step.label}", 50)):
            draw.text((640, y + 44 + line * 38), text, font=font, fill="#222222", anchor="ms", **drawing_direction(text))
        draw.text((640, y + 132), step.owner, font=small, fill="#222222", anchor="ms", **drawing_direction(step.owner))
        if i < len(flow.steps) - 1:
            draw.line((640, y + 160, 640, y + 200), fill="#333333", width=4)
            draw.line((630, y + 188, 640, y + 200, 650, y + 188), fill="#333333", width=4)
    stream = BytesIO()
    image.save(stream, format="PNG")
    stream.seek(0)
    return stream


def svg_text(text,x,y,size):
    from ..formatters.typography import direction, has_arabic
    from .config import config_manager
    family = config_manager.document_profile.style.arabic_font if has_arabic(text) else 'DejaVu Sans'
    return f'<text x="{x}" y="{y}" text-anchor="middle" font-family="{escape(family)}" font-size="{size}" direction="{direction(text)}" unicode-bidi="plaintext">{escape(text)}</text>'


def graph_geometry(flow):
    lanes = {l.id:i for i,l in enumerate(flow.lanes)}
    return {n.id:(190+lanes[n.lane]*300,80+n.row*190) for n in flow.nodes}


def validate_render_text(flow):
    from ..formatters.typography import diagram_font, drawing_direction
    def fits(text,width,size):
        if diagram_font(text,size).getlength(text,**drawing_direction(text)) > width:
            raise ValueError('Shorten diagram text to fit its readable bounded layout')
    graph=isinstance(flow,GraphFlow)
    fits(flow.title,flow.dimensions()[0]-40,22 if graph else 18)
    for step in flow.steps:
        fits(step.owner,242 if graph else 470,16 if graph else 14)
        for line in textwrap.wrap(step.label,23 if graph else 50):
            fits(line,242 if graph else 470,20 if graph else 16)


def graph_svg(flow):
    from ..formatters.typography import has_arabic
    width,height = flow.dimensions()
    pos = graph_geometry(flow)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
             '<title>'+escape(flow.description())+'</title>',svg_text(flow.title,width/2,25,22)]
    for i,lane in enumerate(flow.lanes):
        parts += [f'<rect x="{40+i*300}" y="40" width="300" height="{height-45}" fill="#fafafa" stroke="#cccccc"/>', svg_text(lane.label,190+i*300,64,18)]
    for node in flow.nodes:
        x,y = pos[node.id]
        parts.append(f'<rect x="{x-130}" y="{y}" width="260" height="120" rx="5" fill="#f0f3f6" stroke="#444" stroke-width="{3 if node.kind == "decision" else 1}"/>')
        if node.kind == 'decision': parts.append(svg_text('قرار' if has_arabic(flow.description()) else 'Decision',x,y+18,14))
        for j,line in enumerate(textwrap.wrap(node.label,23)):
            if j > 2: raise ValueError("Shorten diagram labels to fit three readable lines")
            parts.append(svg_text(line,x,y+40+j*22,20))
        parts.append(svg_text(node.owner,x,y+108,16))
    for i,edge in enumerate(flow.edges):
        x,y = pos[edge.source]; tx,ty = pos[edge.target]
        gutter = width-20-i*4
        slot = [e for e in flow.edges if e.source == edge.source].index(edge)
        sy = y+140+slot*24
        parts.append(f'<path d="M{x} {y+120} V{sy} H{gutter} V{ty-12} H{tx} V{ty} m-5 -7 l5 7 5 -7" fill="none" stroke="#444" stroke-width="1.5"/>')
        if edge.label: parts.append(svg_text(edge.label,(x+gutter)/2,sy-3,14))
    return ''.join(parts)+'</svg>'


def graph_png(flow):
    from PIL import Image, ImageDraw
    from ..formatters.typography import diagram_font, drawing_direction, has_arabic
    width,height = flow.dimensions(); scale=2
    image = Image.new('RGB',(width*scale,height*scale),'white'); draw=ImageDraw.Draw(image)
    tag = 'قرار' if has_arabic(flow.description()) else 'Decision'
    all_text = flow.description()+' '+' '.join(l.label for l in flow.lanes)+' '+tag
    def text(value,x,y,size):
        draw.text((x*scale,y*scale),value,font=diagram_font(all_text,size*scale),fill='#222',anchor='ms',**drawing_direction(value))
    text(flow.title,width/2,25,22)
    for i,lane in enumerate(flow.lanes):
        draw.rectangle(((40+i*300)*scale,40*scale,(340+i*300)*scale,(height-5)*scale), fill='#fafafa',outline='#ccc',width=2)
        text(lane.label,190+i*300,64,18)
    pos=graph_geometry(flow)
    for node in flow.nodes:
        x,y=pos[node.id]
        draw.rounded_rectangle(((x-130)*scale,y*scale,(x+130)*scale,(y+120)*scale),radius=10,fill='#f0f3f6',outline='#444',width=6 if node.kind=='decision' else 2)
        if node.kind=='decision': text(tag,x,y+18,14)
        for j,line in enumerate(textwrap.wrap(node.label,23)):
            if j>2: raise ValueError('Shorten diagram labels to fit three readable lines')
            text(line,x,y+40+j*22,20)
        text(node.owner,x,y+108,16)
    for i,edge in enumerate(flow.edges):
        x,y=pos[edge.source]; tx,ty=pos[edge.target]; gutter=width-20-i*4
        slot=[e for e in flow.edges if e.source==edge.source].index(edge); sy=y+140+slot*24
        draw.line([(px*scale,py*scale) for px,py in [(x,y+120),(x,sy),(gutter,sy),(gutter,ty-12),(tx,ty-12),(tx,ty)]],fill='#444',width=3)
        draw.line(((tx-5)*scale,(ty-7)*scale,tx*scale,ty*scale,(tx+5)*scale,(ty-7)*scale),fill='#444',width=3)
        if edge.label: text(edge.label,(x+gutter)/2,sy-3,14)
    stream=BytesIO(); image.save(stream,format='PNG');stream.seek(0);return stream
