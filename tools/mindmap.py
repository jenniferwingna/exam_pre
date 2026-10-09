"""Mind-map rendering for the 範文 pages.

Data: tools/src/mindmaps/NN.json, one per topic:
  {"topic": "01", "title": "...", "questions": [
     {"q": 1, "paper": "zh"|"en", "center": "...", "stance": "...",
      "branches": [{"label": "...", "d": "...", "items": [{"t": "...", "c": ["..."], "d": "..."}]}]}]}

Two views per map, switched by a small inline script (state kept per viewer):
  簡圖  horizontal connector tree, keywords only (default on wide screens)
  詳解  vertical indented tree that also shows each item's "d" explanation
        (always used on phones, where a horizontal tree would not fit)
Each branch label folds/unfolds its subtree; toolbar buttons fold or unfold all.
"""
import html
import json
import os

PALETTE = ["zh", "en", "jade", "amber", "navy", "stamp"]

# vertical-tree rules, applied both on phones and in 詳解 view (prefix .mmv)
_VERT = r"""
{p}.mm{{display:block;min-width:0}}
{p}.mm .root{{max-width:none;text-align:left}}
{p}.mm .tree,{p}.mm .tree.l2,{p}.mm .tree.l3{{padding-left:14px}}
{p}.mm .tree::before{{display:none}}
{p}.mm .tree>li{{display:block;padding:6px 0 0 14px}}
{p}.mm .tree>li::before,{p}.mm .tree>li:first-child::before{{top:0;bottom:auto;height:100%;display:block}}
{p}.mm .tree>li:last-child::before{{bottom:auto;height:19px}}
{p}.mm .tree>li::after{{top:19px}}
{p}.mm .tree.l3>li::after{{top:14px}}
{p}.mm .tree.l3>li:last-child::before{{height:14px}}
{p}.mm .br{{width:auto;display:inline-block}}
{p}.mm .it,{p}.mm .sub{{max-width:none;display:inline-block}}
{p}.mm .d{{display:block}}
{p}.mm .bd{{display:block}}
"""

MINDMAP_CSS = r"""
.mm-wrap{margin-top:14px;background:var(--surface);border:1px solid var(--line);border-radius:2px;padding:14px;overflow-x:auto}
.mm-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
.mm-stance{flex:1 1 260px;font-size:13.5px;color:var(--dim);margin:0;padding-left:10px;border-left:3px solid var(--line2)}
.mm-stance b{color:var(--text)}
.mm-btn{font:inherit;font-size:12px;padding:3px 10px;border:1px solid var(--line2);background:var(--surface-2);color:var(--dim);border-radius:2px;cursor:pointer}
.mm-btn[aria-pressed="true"]{background:var(--navy);color:var(--surface);border-color:var(--navy)}
.mm-seg{display:inline-flex}.mm-seg .mm-btn+.mm-btn{border-left:none}
.mm{display:flex;align-items:center;min-width:max-content}
.mm ul{list-style:none;margin:0;padding:0;flex:none}
.mm .root{flex:none;max-width:170px;padding:10px 14px;background:var(--navy);color:var(--surface);font-family:"Noto Serif HK",Georgia,serif;font-weight:700;font-size:15px;line-height:1.45;border-radius:3px;text-align:center}
.mm .root.en{background:var(--en)}
.mm .tree{position:relative;padding-left:26px}
.mm .tree::before{content:"";position:absolute;left:0;top:50%;width:13px;border-top:2px solid var(--line2)}
.mm .tree>li{position:relative;display:flex;align-items:center;padding:3px 0 3px 13px}
.mm .tree>li::before{content:"";position:absolute;left:0;top:0;bottom:0;border-left:2px solid var(--line2)}
.mm .tree>li:first-child::before{top:50%}
.mm .tree>li:last-child::before{bottom:50%}
.mm .tree>li:only-child::before{display:none}
.mm .tree>li::after{content:"";position:absolute;left:0;top:50%;width:13px;border-top:2px solid var(--line2)}
.mm .br{flex:none;width:122px;padding:6px 10px;font:inherit;font-weight:700;font-size:13px;line-height:1.4;text-align:left;border-radius:3px;background:var(--c-bg);color:var(--c);border:1px solid var(--c);cursor:pointer}
.mm .br::after{content:" ▾";font-size:11px;opacity:.7}
.mm li.fold>.br::after{content:" ▸"}
.mm li.fold>.tree,.mm li.fold>.bd{display:none}
.mm li.fold>.br{border-style:dashed}
.mm .bd{display:none;font-size:12.5px;color:var(--dim);margin:4px 0 0 2px}
.mm .it{flex:none;max-width:250px;padding:4px 9px;font-size:13px;line-height:1.5;background:var(--surface-2);border:1px solid var(--line);border-left:3px solid var(--c);border-radius:2px}
.mm .it .d{display:none;font-size:12.5px;line-height:1.65;color:var(--dim);margin-top:2px;font-weight:400}
.mm .sub{flex:none;max-width:250px;font-size:12.5px;line-height:1.5;color:var(--dim);padding:2px 6px}
.mm .tree.l2,.mm .tree.l3{padding-left:22px}
.mm .tree.l2::before,.mm .tree.l3::before{width:11px}
.mm .tree.l3>li::after{width:9px}
.mm .c-zh{--c:var(--zh);--c-bg:var(--zh-bg)}
.mm .c-en{--c:var(--en);--c-bg:var(--en-bg)}
.mm .c-jade{--c:var(--jade);--c-bg:var(--jade-bg)}
.mm .c-amber{--c:var(--amber);--c-bg:var(--amber-bg)}
.mm .c-navy{--c:var(--navy);--c-bg:var(--surface-3)}
.mm .c-stamp{--c:var(--stamp);--c-bg:var(--zh-bg)}
.mmv .mm .it{display:block;max-width:62ch}
""" + _VERT.format(p=".mmv ") + "@media (max-width:760px){.mm-wrap{padding:12px}.mm-seg{display:none}" + _VERT.format(p="") + ".mm .it{display:block}}\n"

MINDMAP_JS = r"""<script>
(function(){
  var KEY='jre-mm-view', view='brief';
  try{view=localStorage.getItem(KEY)||'brief'}catch(e){}
  function apply(v){
    view=v;
    document.querySelectorAll('.mm-wrap').forEach(function(w){
      w.classList.toggle('mmv',v==='detail');
      w.querySelectorAll('[data-view]').forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.view===v))});
    });
  }
  document.addEventListener('click',function(e){
    var t=e.target.closest('button');
    if(!t||!t.closest('.mm-wrap'))return;
    var w=t.closest('.mm-wrap');
    if(t.classList.contains('br')){var li=t.parentNode;li.classList.toggle('fold');t.setAttribute('aria-expanded',String(!li.classList.contains('fold')));return}
    if(t.dataset.view){apply(t.dataset.view);try{localStorage.setItem(KEY,t.dataset.view)}catch(e){}return}
    if(t.dataset.fold){var f=t.dataset.fold==='all';w.querySelectorAll('.mm li.b').forEach(function(li){li.classList.toggle('fold',f);li.querySelector('.br').setAttribute('aria-expanded',String(!f))})}
  });
  apply(view);
})();
</script>"""


def esc(s):
    return html.escape(str(s), quote=True)


def load_mindmaps(src_dir):
    maps = {}
    for f in sorted(os.listdir(src_dir)) if os.path.isdir(src_dir) else []:
        if not f.endswith(".json"):
            continue
        try:
            d = json.load(open(os.path.join(src_dir, f), encoding="utf-8"))
        except Exception as e:  # keep the build going; report the bad file
            print(f"WARN: mindmap {f} unreadable: {e}")
            continue
        nn = str(d.get("topic", f[:2])).zfill(2)
        maps[nn] = {int(q["q"]): q for q in d.get("questions", [])}
    return maps


def render_mindmap(m, english=False):
    """HTML for one question's map, or '' if no data."""
    if not m:
        return ""
    lang = ' lang="en"' if english else ""
    L = (("Stance", "Brief", "Detail", "Expand all", "Collapse all") if english
         else ("立場", "簡圖", "詳解", "全部展開", "全部收起"))
    out = [f'<div class="mm-wrap"{lang}><div class="mm-bar">']
    out.append(f'<p class="mm-stance"><b>{L[0]}：</b>{esc(m.get("stance", ""))}</p>')
    out.append(f'<span class="mm-seg"><button type="button" class="mm-btn" data-view="brief" aria-pressed="true">{L[1]}</button>'
               f'<button type="button" class="mm-btn" data-view="detail" aria-pressed="false">{L[2]}</button></span>'
               f'<button type="button" class="mm-btn" data-fold="none">{L[3]}</button>'
               f'<button type="button" class="mm-btn" data-fold="all">{L[4]}</button></div>')
    out.append(f'<div class="mm"><div class="root{" en" if english else ""}">{esc(m.get("center", ""))}</div><ul class="tree">')
    for i, b in enumerate(m.get("branches", [])):
        c = PALETTE[i % len(PALETTE)]
        out.append(f'<li class="b c-{c}"><button type="button" class="br" aria-expanded="true">{esc(b.get("label", ""))}</button>')
        if b.get("d"):
            out.append(f'<div class="bd">{esc(b["d"])}</div>')
        items = b.get("items", [])
        if items:
            out.append('<ul class="tree l2">')
            for it in items:
                if isinstance(it, str):
                    it = {"t": it}
                d = f'<span class="d">{esc(it["d"])}</span>' if it.get("d") else ""
                out.append(f'<li><div class="it">{esc(it.get("t", ""))}{d}</div>')
                subs = [s for s in it.get("c", []) or [] if s]
                if subs:
                    out.append('<ul class="tree l3">' + "".join(f'<li><div class="sub">{esc(s)}</div></li>' for s in subs) + "</ul>")
                out.append("</li>")
            out.append("</ul>")
        out.append("</li>")
    out.append("</ul></div></div>")
    return "".join(out)
