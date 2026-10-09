#!/usr/bin/env python3
"""Build the 範文 (model essays) section and the 答題框架 page.

Usage (from anywhere):
    pip install markdown
    python3 tools/build_essays.py            # sync sources from ~/jre, then build
    python3 tools/build_essays.py --no-sync  # build only from tools/src/

What it does (safe to re-run any number of times):
  1. Copies ~/jre/範文庫/NN-*.md and ~/jre/03-答題框架.md into tools/src/
     (so the repo is self-contained), unless --no-sync or the source is missing.
  2. Generates 範文/index.html, 範文/NN-slug/index.html (slug = 議題庫 folder)
     and 答題框架/index.html from tools/src/.
  3. Patches 議題庫/index.html (quick-nav links) and every
     議題庫/NN-slug/index.html (a pointer box at the top of the #exam section).
     Patches are wrapped in <!-- essay-gen:... --> markers and replaced in place,
     so they never duplicate.
"""
import argparse
import glob
import html
import os
import re
import shutil
import sys

try:
    import markdown
except ImportError:  # pragma: no cover
    sys.exit("Missing dependency: pip install markdown")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "tools", "src")
SRC_ESSAYS = os.path.join(SRC, "範文庫")
SRC_FRAMEWORK = os.path.join(SRC, "03-答題框架.md")
UPSTREAM = os.path.expanduser("~/jre")
TOPIC_DIR = os.path.join(REPO, "議題庫")
ESSAY_DIR = os.path.join(REPO, "範文")
FRAME_DIR = os.path.join(REPO, "答題框架")

CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8}
IDEO_SPACE = "\u3000"
SPACE_TOKEN = "\ue000"  # private-use char: survives Python-Markdown's lstrip()

FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+HK:wght@400;500;700'
         '&family=Noto+Serif+HK:wght@500;700;900&family=IBM+Plex+Mono:wght@400;600&display=swap">')

# ---------------------------------------------------------------- CSS
BASE_CSS = r"""
:root{--bg:#EDEFF3;--surface:#FFF;--surface-2:#F5F7FA;--surface-3:#E8ECF3;
--text:#141C2E;--dim:#54607A;--faint:#8892A6;--line:#D6DBE5;--line2:#B4BDCE;
--navy:#1B2C4F;--zh:#8A3324;--zh-bg:#F8E8E3;--en:#1D4E89;--en-bg:#E5ECF7;
--jade:#1B6A55;--jade-bg:#E2EFE9;--amber:#87560A;--amber-bg:#F8ECD6;--stamp:#A32A22}
@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){
--bg:#0D121C;--surface:#151C2A;--surface-2:#1A2231;--surface-3:#212A3B;
--text:#E4E9F2;--dim:#9CA8BE;--faint:#727F97;--line:#273245;--line2:#3A4660;
--navy:#A2BAE7;--zh:#E79484;--zh-bg:#331C17;--en:#8FB4E8;--en-bg:#15263C;
--jade:#5FC5A2;--jade-bg:#11332B;--amber:#E3AC4F;--amber-bg:#332710;--stamp:#EE8175}}
:root[data-theme="dark"]{
--bg:#0D121C;--surface:#151C2A;--surface-2:#1A2231;--surface-3:#212A3B;
--text:#E4E9F2;--dim:#9CA8BE;--faint:#727F97;--line:#273245;--line2:#3A4660;
--navy:#A2BAE7;--zh:#E79484;--zh-bg:#331C17;--en:#8FB4E8;--en-bg:#15263C;
--jade:#5FC5A2;--jade-bg:#11332B;--amber:#E3AC4F;--amber-bg:#332710;--stamp:#EE8175}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{background:var(--bg);color:var(--text);margin:0;font-size:15px;line-height:1.75;overflow-wrap:break-word;
font-family:"Noto Sans HK","PingFang HK","Microsoft JhengHei",system-ui,sans-serif;-webkit-font-smoothing:antialiased}
h1,h2,h3,h4{font-family:"Noto Serif HK",Georgia,serif;margin:0;text-wrap:balance}
.wrap{max-width:1240px;margin:0 auto;padding:0 22px 80px}
header{background:var(--surface);border-bottom:2px solid var(--navy)}
.hd{max-width:1240px;margin:0 auto;padding:24px 22px 20px;display:flex;gap:20px;align-items:flex-end;flex-wrap:wrap}
.hd .no{font-family:"IBM Plex Mono",monospace;font-size:38px;font-weight:600;color:var(--line2);line-height:1}
.hd h1{font-size:27px;font-weight:900;letter-spacing:.04em}
.hd .en-t{font-size:15px;color:var(--dim);margin-top:4px;font-family:"Noto Serif HK",Georgia,serif;font-weight:500}
.tag{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.09em;padding:3px 9px;border-radius:2px;
background:var(--amber-bg);color:var(--amber);margin-bottom:9px}
.hd .right{margin-left:auto;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.back{font-size:12.5px;color:var(--dim);text-decoration:none;border-bottom:1px solid var(--line2)}
.back:hover,.back:focus-visible{color:var(--navy);border-bottom-color:var(--navy);outline:none}
.hero{background:var(--surface);border-bottom:2px solid var(--navy)}
.hero .in{max-width:1240px;margin:0 auto;padding:30px 22px 26px;display:grid;gap:14px}
.eyebrow{font-size:11.5px;font-weight:700;letter-spacing:.12em;color:var(--amber)}
.hero h1{font-size:32px;font-weight:900;letter-spacing:.04em}
.hero .sub{font-family:"Noto Serif HK",Georgia,serif;color:var(--dim);font-size:15px}
.hero p.lede{max-width:72ch;margin:0;color:var(--text)}
.stats{display:flex;flex-wrap:wrap;gap:22px;margin-top:4px}
.stats div{font-size:12.5px;color:var(--dim)}
.stats b{display:block;font-family:"IBM Plex Mono",monospace;font-size:22px;color:var(--navy);font-weight:600;line-height:1.2}
.quicknav{position:sticky;top:0;z-index:20;background:var(--surface);border-bottom:1px solid var(--line2)}
.quicknav .in{max-width:1240px;margin:0 auto;padding:0 22px;display:flex;gap:2px;overflow-x:auto;scrollbar-width:none}
.quicknav .in::-webkit-scrollbar{display:none}
.quicknav a{flex:none;padding:11px 13px;font-size:12.5px;font-weight:700;letter-spacing:.03em;color:var(--dim);text-decoration:none;white-space:nowrap;border-bottom:2px solid transparent}
.quicknav a:hover,.quicknav a:focus-visible{color:var(--navy);border-bottom-color:var(--line2);outline:none}
.quicknav a.hot{color:var(--stamp)}
.quicknav a.cur{color:var(--navy);border-bottom-color:var(--navy)}
.quicknav .sep{flex:none;width:1px;background:var(--line2);margin:10px 6px}
.quicknav .zh{color:var(--zh)}.quicknav .en{color:var(--en)}
.hsec{margin-top:38px}
.hsec>h2{font-size:19px;font-weight:700;padding-bottom:8px;border-bottom:1px solid var(--line2);display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}
.hsec>h2 .e{font-size:12.5px;color:var(--faint);font-weight:500}
.hsec>h2 .hint{margin-left:auto;font-size:12px;color:var(--faint);font-family:"Noto Sans HK",sans-serif;font-weight:400}
.note{font-size:13.5px;color:var(--dim);margin:10px 0 0;max-width:80ch}
.caveat{background:var(--amber-bg);border:1px solid var(--amber);border-radius:3px;padding:12px 16px;font-size:13.5px;margin-top:14px;line-height:1.7}
.caveat b,.caveat strong{color:var(--amber)}
.caveat p{margin:0}.caveat p+p{margin-top:6px}
.pp{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.06em;padding:1px 8px;border-radius:2px;white-space:nowrap}
.pp.zh{background:var(--zh-bg);color:var(--zh)}
.pp.en{background:var(--en-bg);color:var(--en)}
.tbl{overflow-x:auto;-webkit-overflow-scrolling:touch;max-width:100%;margin:10px 0;border:1px solid var(--line);background:var(--surface)}
.tbl table{width:100%;border-collapse:collapse;font-size:13.5px;line-height:1.65;min-width:560px}
.tbl th,.tbl td{padding:8px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.tbl th{font-size:12px;letter-spacing:.04em;color:var(--faint);font-weight:600;background:var(--surface-2);white-space:nowrap}
.tbl tr:last-child td{border-bottom:none}
.tbl td:first-child{white-space:nowrap;color:var(--dim);font-family:"IBM Plex Mono","Noto Sans HK",monospace;font-size:12.5px}
.foot{margin-top:40px;padding-top:16px;border-top:1px solid var(--line2);font-size:12.5px;color:var(--faint);line-height:1.7}
.foot a{color:var(--navy)}
@media(max-width:820px){.hd .no{font-size:28px}.hd h1{font-size:22px}.hero h1{font-size:26px}}
@media(max-width:600px){
 .wrap,.hd,.hero .in,.quicknav .in{padding-left:16px;padding-right:16px}
 .hd .right{margin-left:0}
}
"""

INDEX_CSS = r"""
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,340px),1fr));gap:12px;margin-top:12px}
.card{display:flex;flex-direction:column;gap:8px;background:var(--surface);border:1px solid var(--line);padding:15px 17px 13px;border-radius:2px;transition:border-color .15s;min-width:0}
.card:hover,.card:focus-within{border-color:var(--navy)}
.card .top{display:flex;gap:10px;align-items:baseline}
.card .no{font-family:"IBM Plex Mono",monospace;font-weight:600;color:var(--line2);font-size:20px}
.card h3{font-size:16.5px;font-weight:700;line-height:1.35}
.card h3 a{color:var(--text);text-decoration:none;border-bottom:1px solid var(--line2)}
.card h3 a:hover,.card h3 a:focus-visible{border-bottom-color:var(--navy);outline:none}
.card .en-n{font-size:12.5px;color:var(--dim);font-family:"Noto Serif HK",Georgia,serif}
.card ol{list-style:none;margin:2px 0 0;padding:0;display:grid;gap:0}
.card li{display:grid;grid-template-columns:auto 1fr auto;gap:8px;align-items:baseline;padding:6px 0;border-top:1px dashed var(--line);font-size:13.5px;line-height:1.55}
.card li a{color:var(--text);text-decoration:none;min-width:0}
.card li a:hover,.card li a:focus-visible{color:var(--navy);text-decoration:underline;outline:none}
.card li .wc{font-family:"IBM Plex Mono",monospace;font-size:11.5px;color:var(--faint);white-space:nowrap}
.card .meta{margin-top:auto;padding-top:8px;border-top:1px solid var(--line);font-size:12px;display:flex;gap:14px;flex-wrap:wrap}
.card .meta a{color:var(--navy);text-decoration:none;border-bottom:1px solid var(--line2)}
.how{background:var(--surface);border:1px solid var(--line);border-top:none;padding:16px 20px}
.how ol{margin:0;padding-left:20px;font-size:14px;color:var(--dim);line-height:1.8;display:grid;gap:4px}
.how b{color:var(--text)}
"""

PAGE_CSS = r"""
.wrap.narrow,.hd.narrow,.quicknav .in.narrow{max-width:940px}
section{scroll-margin-top:56px}
.intro{margin-top:22px}
.qa{margin-top:42px}
.qh{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;padding-bottom:8px;border-bottom:1px solid var(--line2)}
.qh .qno{font-family:"Noto Serif HK",Georgia,serif;font-size:13px;font-weight:700;color:var(--faint);letter-spacing:.06em}
.qh h2{font-size:20px;font-weight:700;letter-spacing:.02em;flex:1 1 260px;min-width:0}
.qh .st{color:var(--amber);letter-spacing:2px;font-size:13px}
.qh .wc{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--faint);white-space:nowrap}
.qcard{margin-top:14px;background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--zh);padding:16px 20px;border-radius:0 2px 2px 0}
.qcard.en{border-left-color:var(--en)}
.qcard .ql{font-size:11px;font-weight:700;letter-spacing:.1em;color:var(--zh);margin-bottom:6px}
.qcard.en .ql{color:var(--en)}
.qcard .qb{font-family:"Noto Serif HK",Georgia,serif;font-weight:500;font-size:16px;line-height:1.9}
.qcard .qb[lang="en"]{font-family:Georgia,"Noto Serif HK",serif;font-weight:400;font-size:15.5px;line-height:1.75}
.qcard .qb p{margin:0 0 .8em}.qcard .qb p:last-child{margin-bottom:0}
.qcard .qb .lb{font-family:"IBM Plex Mono",monospace;font-size:11.5px;font-weight:600;letter-spacing:.12em;color:var(--en);margin:1.1em 0 .4em}
.qcard .qb .lb:first-child{margin-top:0}
.qnote{margin-top:10px;font-size:13.5px;color:var(--dim)}
.qnote p{margin:0 0 .5em}
details.sx{margin-top:12px;background:var(--surface);border:1px solid var(--line);border-radius:2px}
details.sx>summary{cursor:pointer;list-style:none;padding:10px 16px;font-weight:700;font-size:14px;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
details.sx>summary::-webkit-details-marker{display:none}
details.sx>summary::before{content:"▸";color:var(--navy);font-size:12px;transition:transform .15s;display:inline-block}
details.sx[open]>summary::before{transform:rotate(90deg)}
details.sx>summary .s{font-weight:400;font-size:12px;color:var(--faint)}
details.sx>summary:focus-visible{outline:2px solid var(--navy);outline-offset:-2px}
details.sx .bd{padding:2px 18px 14px;border-top:1px dashed var(--line);font-size:14.5px}
details.sx .bd p{margin:.7em 0}
details.sx .bd strong{color:var(--navy)}
details.sx .bd ul,details.sx .bd ol{padding-left:1.4em}
details.sx.how2 summary{color:var(--jade)}
details.sx.how2 summary::before{color:var(--jade)}
.essay{margin-top:18px;background:var(--surface);border:1px solid var(--line);border-top:3px solid var(--navy);padding:22px 24px 26px}
.essay .eh{display:flex;gap:10px;align-items:baseline;font-size:11.5px;font-weight:700;letter-spacing:.1em;color:var(--navy);margin-bottom:12px}
.essay .eh .wc{font-family:"IBM Plex Mono",monospace;font-weight:400;color:var(--faint);letter-spacing:0}
.essay .body{max-width:72ch;font-family:"Noto Serif HK",Georgia,serif;font-size:17px;line-height:2.05;font-weight:500}
.essay .body p{margin:0 0 .85em}
.essay .body[lang="en"]{font-family:Georgia,"Noto Serif HK",serif;font-weight:400;font-size:16.5px;line-height:1.8}
.essay .body[lang="en"] p{margin:0 0 1em}
.essay .body .lb{font-family:"IBM Plex Mono",monospace;font-size:13px;font-weight:600;letter-spacing:.06em;margin:1.4em 0 .5em;color:var(--text)}
.essay .body ol{padding-left:2.2em;margin:0 0 1em}
.essay .body li{margin:0 0 .6em}
.essay .body li p{margin:0 0 .6em}
.essay .body em{color:var(--dim)}
.toplink{display:inline-block;margin-top:10px;font-size:12px;color:var(--faint);text-decoration:none}
.toplink:hover{color:var(--navy)}
.pager{display:flex;justify-content:space-between;gap:12px;margin-top:40px;flex-wrap:wrap}
.pager a{color:var(--navy);text-decoration:none;font-size:13.5px;border-bottom:1px solid var(--line2)}
@media(max-width:600px){
 .qcard{padding:14px 14px}
 .essay{padding:16px 14px 20px}
 .essay .body{font-size:16.5px;line-height:1.95}
 details.sx .bd{padding:2px 12px 12px}
}
"""

DOC_CSS = r"""
.wrap.narrow,.hd.narrow{max-width:1000px}
.toc{margin-top:24px;background:var(--surface);border:1px solid var(--line);border-top:3px solid var(--navy);padding:14px 20px 16px}
.toc .t{font-size:11.5px;font-weight:700;letter-spacing:.1em;color:var(--navy);margin-bottom:6px}
.toc ol{list-style:none;margin:0;padding:0;columns:2 280px;column-gap:28px}
.toc li{break-inside:avoid;font-size:13.5px;line-height:1.6;padding:2px 0}
.toc li.l2{font-weight:700;margin-top:8px;font-family:"Noto Serif HK",Georgia,serif;font-size:14.5px}
.toc li.l2:first-child{margin-top:0}
.toc li.l3{padding-left:1em}
.toc a{color:var(--text);text-decoration:none}
.toc a:hover,.toc a:focus-visible{color:var(--navy);text-decoration:underline;outline:none}
.doc h2,.doc h3,.doc h4{scroll-margin-top:16px}
.doc h2{margin-top:44px;font-size:21px;font-weight:900;padding-bottom:8px;border-bottom:2px solid var(--navy);letter-spacing:.03em}
.doc h3{margin-top:30px;font-size:17.5px;font-weight:700;padding-bottom:6px;border-bottom:1px solid var(--line2)}
.doc h4{margin-top:20px;font-size:15.5px;font-weight:700;color:var(--navy)}
.doc p{margin:.7em 0;max-width:80ch}
.doc ul,.doc ol{padding-left:1.5em;max-width:80ch}
.doc li{margin:.25em 0}
.doc strong{color:var(--navy)}
.doc blockquote{margin:14px 0;background:var(--amber-bg);border-left:3px solid var(--amber);padding:10px 16px;border-radius:0 2px 2px 0}
.doc blockquote p{margin:.3em 0}
.doc pre{background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--en);padding:12px 16px;overflow-x:auto;max-width:100%;
font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace;font-size:12.5px;line-height:1.6;color:var(--text)}
.doc code{font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace;font-size:.88em;background:var(--surface-3);padding:1px 5px;border-radius:2px}
.doc pre code{background:none;padding:0;font-size:inherit}
.doc hr{border:none;border-top:1px solid var(--line2);margin:28px 0}
.doc .tbl td:first-child{white-space:normal;font-family:inherit;font-size:13.5px;color:var(--text)}
.doc .tbl table{min-width:520px}
"""

HINT_STYLE = ("margin:12px 0 0;padding:11px 16px;background:var(--jade-bg);border:1px solid var(--jade);"
              "border-radius:3px;font-size:13.5px;line-height:1.7;color:var(--text)")


# ---------------------------------------------------------------- helpers
def esc(s):
    return html.escape(s, quote=True)


def md_to_html(text):
    """Markdown -> HTML, keeping leading ideographic spaces (段首全形空格)."""
    text = re.sub(r"^([\u3000]+)", lambda m: SPACE_TOKEN * len(m.group(1)), text, flags=re.M)
    out = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"], output_format="html")
    out = out.replace(SPACE_TOKEN, IDEO_SPACE)
    out = re.sub(r"<table>", '<div class="tbl"><table>', out)
    out = out.replace("</table>", "</table></div>")
    return out


def bold_labels(h):
    """<p><strong>LABEL</strong></p> -> <p class="lb">LABEL</p> (case/paper headings)."""
    return re.sub(r"<p><strong>([^<]{1,120})</strong></p>", r'<p class="lb">\1</p>', h)


def strip_rules(text):
    lines = text.strip("\n").split("\n")
    while lines and lines[-1].strip() in ("---", "***", ""):
        lines.pop()
    while lines and lines[0].strip() in ("---", "***", ""):
        lines.pop(0)
    return "\n".join(lines)


def count_words(text, english):
    plain = re.sub(r"[*_#>|`]", "", text)
    if english:
        return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-]*", plain))
    return len(re.findall(r"[\u3400-\u9fff\uf900-\ufaff]", plain)) + len(re.findall(r"[A-Za-z0-9]+", plain))


def load_topics():
    """NN -> {slug, name, en} from the 議題庫 folder and its index cards."""
    topics = {}
    for d in sorted(os.listdir(TOPIC_DIR)):
        m = re.match(r"^(\d\d)-([a-z0-9-]+)$", d)
        if m and os.path.isfile(os.path.join(TOPIC_DIR, d, "index.html")):
            topics[m.group(1)] = {"slug": d, "name": "", "en": ""}
    idx = open(os.path.join(TOPIC_DIR, "index.html"), encoding="utf-8").read()
    for m in re.finditer(r'<a class="card[^"]*" href="(\d\d)-[^/"]+/index\.html">.*?<h3>(.*?)</h3><div class="en">(.*?)</div>', idx, re.S):
        if m.group(1) in topics:
            topics[m.group(1)].update(name=html.unescape(m.group(2)), en=html.unescape(m.group(3)))
    return topics


# ---------------------------------------------------------------- parsing
def parse_essay_file(path):
    text = open(path, encoding="utf-8").read().replace("\r\n", "\n")
    m = re.search(r"^# (\d\d)｜(.+?)(?:：範文)?\s*$", text, re.M)
    if not m:
        raise ValueError(f"{path}: missing '# NN｜議題：範文' title")
    doc = {"nn": m.group(1), "title": m.group(2).strip(), "intro": "", "qs": []}
    body = text[m.end():]
    parts = re.split(r"^## (.+)$", body, flags=re.M)
    doc["intro"] = strip_rules(parts[0])
    for i in range(1, len(parts), 2):
        doc["qs"].append(parse_question(parts[i].strip(), parts[i + 1], path))
    return doc


def parse_question(heading, body, path):
    m = re.match(r"^(題[一二三四五六七八\d]+)\s*[｜|]\s*[（(]\s*(中文卷|英文卷)\s*([★☆]*)\s*[）)]\s*(.*)$", heading)
    if not m:
        raise ValueError(f"{path}: cannot parse question heading: {heading!r}")
    label, paper, stars, short = m.groups()
    q = {"label": label, "paper": paper, "stars": stars, "short": short.strip(),
         "english": paper == "英文卷", "pre": "", "question": "", "qkind": "題目",
         "analysis": None, "analysis_title": "審題", "essay": "", "essay_title": "範文",
         "count": "", "notes": None, "extra": []}
    n = label[1:]
    q["n"] = CN_NUM.get(n, int(n) if n.isdigit() else 0)
    subs = re.split(r"^### (.+)$", body, flags=re.M)
    q["pre"] = strip_rules(subs[0])
    for i in range(1, len(subs), 2):
        h, content = subs[i].strip(), strip_rules(subs[i + 1])
        if h.startswith("定稿題目") or h.startswith("題目"):
            q["question"] = content
            q["qkind"] = "定稿題目" if h.startswith("定稿題目") else "題目"
        elif h.startswith("審題"):
            q["analysis"] = content
            sub = re.search(r"[（(](.+?)[）)]", h)
            q["analysis_sub"] = sub.group(1) if sub else ""
        elif h.startswith("範文"):
            q["essay"] = content
            cm = re.search(r"[（(](.+?)[）)]", h)
            raw = cm.group(1) if cm else ""
            num = re.search(r"\d[\d,]*", raw)
            unit = "words" if q["english"] else "字"
            if num:
                approx = "約 " if "約" in raw else ""
                q["count"] = f"{approx}{num.group(0)} {unit}"
            else:
                c = count_words(content, q["english"])
                q["count"] = f"約 {c:,} {unit}" if unit == "words" else f"約 {c:,} 字"
        elif h.startswith("這篇在做什麼"):
            q["notes"] = content
        else:
            q["extra"].append((h, content))
    if not q["question"] or not q["essay"]:
        raise ValueError(f"{path}: {heading!r} lacks a 題目 or 範文 block")
    return q


# ---------------------------------------------------------------- rendering
def page(title, css, body, lang="zh-Hant-HK", desc=""):
    meta = f'<meta name="description" content="{esc(desc)}">\n' if desc else ""
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
{meta}{FONTS}
<style>{BASE_CSS}{css}</style>
</head>
<body>
{body}
</body>
</html>
"""


def render_topic_page(doc, topic, prev_t, next_t):
    nn, slug = doc["nn"], topic["slug"]
    name = topic["name"] or doc["title"]
    n_zh = sum(1 for q in doc["qs"] if not q["english"])
    n_en = len(doc["qs"]) - n_zh
    nav = []
    for q in doc["qs"]:
        cls = "en" if q["english"] else "zh"
        nav.append(f'<a href="#q{q["n"]}"><span class="{cls}">{esc(q["label"])}</span> {esc(q["short"])}</a>')
    out = [f"""<header><div class="hd narrow">
  <div class="no">{nn}</div>
  <div>
    <div class="tag">範文 · 中文卷 {n_zh} 篇 · 英文卷 {n_en} 篇</div>
    <h1>{esc(name)}</h1>
    <div class="en-t">{esc(topic["en"])}{' · ' if topic["en"] else ''}Model essays</div>
  </div>
  <div class="right">
    <a class="back" href="../index.html">← 範文首頁</a>
    <a class="back" href="../../議題庫/{slug}/index.html#exam">對應議題頁 →</a>
    <a class="back" href="../../答題框架/index.html">答題框架</a>
  </div>
</div></header>
<nav class="quicknav" aria-label="本頁四題"><div class="in narrow">{''.join(nav)}</div></nav>
<div class="wrap narrow">"""]
    if doc["intro"]:
        out.append(f'<div class="caveat intro">{md_to_html(doc["intro"]).replace("<blockquote>", "").replace("</blockquote>", "")}</div>')
    for q in doc["qs"]:
        cls = "en" if q["english"] else "zh"
        lang_attr = ' lang="en"' if q["english"] else ""
        stars = f'<span class="st" aria-label="可能性">{esc(q["stars"])}</span>' if q["stars"] else ""
        s = [f'<section class="qa" id="q{q["n"]}">',
             f'<div class="qh"><span class="qno">{esc(q["label"])}</span><span class="pp {cls}">{q["paper"]}</span>{stars}'
             f'<h2>{esc(q["short"])}</h2><span class="wc">範文 {esc(q["count"])}</span></div>']
        if q["pre"]:
            s.append(f'<div class="qnote">{md_to_html(q["pre"])}</div>')
        s.append(f'<div class="qcard {cls}"><div class="ql">{esc(q["qkind"])}</div>'
                 f'<div class="qb"{lang_attr}>{bold_labels(md_to_html(q["question"]))}</div></div>')
        if q["analysis"] is not None:
            sub = q.get("analysis_sub") or ""
            s.append(f'<details class="sx"><summary>審題<span class="s">{esc(sub)}{"　·　" if sub else ""}預設收起：先自己審題，再展開對照</span></summary>'
                     f'<div class="bd">{md_to_html(q["analysis"])}</div></details>')
        for h, c in q["extra"]:
            s.append(f'<details class="sx"><summary>{esc(h)}</summary><div class="bd">{md_to_html(c)}</div></details>')
        s.append(f'<article class="essay"><div class="eh">範文<span class="wc">{esc(q["count"])}</span></div>'
                 f'<div class="body"{lang_attr}>{bold_labels(md_to_html(q["essay"]))}</div></article>')
        if q["notes"] is not None:
            s.append(f'<details class="sx how2" open><summary>這篇在做什麼<span class="s">逐段拆解</span></summary>'
                     f'<div class="bd">{md_to_html(q["notes"])}</div></details>')
        s.append('<a class="toplink" href="#top">↑ 回到頂部</a></section>')
        out.append("\n".join(s))
    pager = ['<div class="pager">']
    pager.append(f'<a href="../{prev_t["slug"]}/index.html">← {prev_t["nn"]} {esc(prev_t["name"])}</a>' if prev_t else "<span></span>")
    pager.append(f'<a href="../{next_t["slug"]}/index.html">{next_t["nn"]} {esc(next_t["name"])} →</a>' if next_t else "<span></span>")
    pager.append("</div>")
    out.append("".join(pager))
    out.append(f'<div class="foot">範文按考場手寫篇幅寫，建議先看題目自己寫一次，再展開審題、最後才讀範文。題目及事實以《香港特別行政區經濟和社會發展第一個五年規劃（2026—2030年）》及《行政長官2026年施政報告》為本；英文卷個案為虛構城市 City of Jade。出題為備考推斷，並非真題；本頁為備考筆記，不代表政府立場。'
               f'<br><a href="../../議題庫/{slug}/index.html">議題庫：{esc(name)}</a> · <a href="../index.html">全部範文</a> · <a href="../../答題框架/index.html">答題框架</a></div>')
    out.append("</div>")
    body = '<div id="top"></div>\n' + "\n".join(out)
    return page(f"{name}｜JRE 範文", PAGE_CSS, body, desc=f"{name}：四篇定稿題目範文、審題與逐段拆解")


def render_index(docs, topics):
    n_q = sum(len(d["qs"]) for d in docs)
    n_en = sum(1 for d in docs for q in d["qs"] if q["english"])
    cards = []
    for d in docs:
        t = topics[d["nn"]]
        rows = []
        for q in d["qs"]:
            cls = "en" if q["english"] else "zh"
            rows.append(f'<li><span class="pp {cls}">{q["paper"]}</span><a href="{t["slug"]}/index.html#q{q["n"]}">{esc(q["short"])}</a>'
                        f'<span class="wc">{esc(q["count"])}</span></li>')
        cards.append(f'<div class="card"><div class="top"><span class="no">{d["nn"]}</span><div><h3><a href="{t["slug"]}/index.html">{esc(t["name"] or d["title"])}</a></h3>'
                     f'<div class="en-n">{esc(t["en"])}</div></div></div><ol>{"".join(rows)}</ol>'
                     f'<div class="meta"><a href="{t["slug"]}/index.html">讀範文 →</a><a href="../議題庫/{t["slug"]}/index.html">議題頁</a></div></div>')
    body = f"""<header class="hero"><div class="in">
 <div class="eyebrow">2026 聯合招聘考試 · 定稿題目＋範文＋審題＋逐段拆解</div>
 <h1>JRE 範文</h1>
 <div class="sub">Model Essays — one per likely question, written to exam length</div>
 <p class="lede">每個議題四題（中文卷三題、英文卷一題）。題目已按施政報告及五年規劃原文修訂；每篇附「審題」（任務拆解、立場一句話、段落與字數預算）和「這篇在做什麼」（逐段要學的動作）。用法：先看題目自己寫，再展開審題對照，最後才讀範文。</p>
 <div class="stats"><div><b>{len(docs)}</b>議題</div><div><b>{n_q}</b>篇範文</div><div><b>{n_q - n_en}</b>中文卷</div><div><b>{n_en}</b>英文卷</div></div>
</div></header>
<nav class="quicknav"><div class="in">
 <a href="../議題庫/index.html">← 議題庫</a>
 <a href="#topics" class="cur">範文</a>
 <a href="../答題框架/index.html">答題框架</a>
 <span class="sep"></span>
 <a href="#howto">怎樣用</a>
</div></nav>
<div class="wrap">
<section class="hsec" id="topics"><h2>{len(docs)}個議題的範文<span class="e">Model essays by topic</span><span class="hint"><span class="pp zh">中文卷</span> <span class="pp en">英文卷</span></span></h2>
<div class="grid">{''.join(cards)}</div>
</section>
<section class="hsec" id="howto"><h2>怎樣用<span class="e">How to use</span></h2>
<div class="how"><ol>
<li><b>先寫後讀：</b>打開議題範文頁，只看題目卡片；「審題」預設收起，先自己用一分鐘拆任務、定立場。</li>
<li><b>限時寫：</b>中文卷約 1,100–1,500 字、英文卷約 900 words，照考場時間手寫一次。</li>
<li><b>對照審題：</b>展開「審題」，比較任務拆解、立場一句話和段落預算，看自己漏了哪一層。</li>
<li><b>讀範文和拆解：</b>最後才讀範文，對照「這篇在做什麼」，把可遷移的動作抄進自己的句式庫。</li>
<li><b>回到框架：</b>結構不穩時，翻<a href="../答題框架/index.html">答題框架</a>的模板和檢查清單。</li>
</ol></div>
</section>
<div class="foot">範文為備考練習，題目為備考推斷，並非真題；本頁為備考筆記，不代表政府立場。<br><a href="../議題庫/index.html">議題庫</a> · <a href="../答題框架/index.html">答題框架</a></div>
</div>"""
    return page("JRE 範文", INDEX_CSS, body, desc="16個議題、64篇定稿題目範文")


def render_framework(path):
    text = open(path, encoding="utf-8").read().replace("\r\n", "\n")
    m = re.search(r"^# (.+)$", text, re.M)
    title = m.group(1).strip() if m else "答題框架"
    rest = text[m.end():] if m else text
    # demote headings one level: '# 甲部' -> h2, '##' -> h3, '###' -> h4 (outside code fences)
    lines, fence = [], False
    for line in rest.split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
        if not fence and re.match(r"^#{1,5} ", line):
            line = "#" + line
        lines.append(line)
    h = md_to_html("\n".join(lines))
    toc, counter = [], [0]

    def add_id(mm):
        lvl, inner = mm.group(1), mm.group(2)
        counter[0] += 1
        hid = f"s{counter[0]}"
        if lvl in ("2", "3"):
            toc.append((lvl, hid, re.sub(r"<[^>]+>", "", inner)))
        return f'<h{lvl} id="{hid}">{inner}</h{lvl}>'
    h = re.sub(r"<h([234])>(.*?)</h\1>", add_id, h)
    toc_html = "".join(f'<li class="l{lvl}"><a href="#{hid}">{esc(html.unescape(t))}</a></li>' for lvl, hid, t in toc)
    clean_title = re.sub(r"^\d+｜", "", title)
    nav = "".join(f'<a href="#{hid}">{esc(html.unescape(t)).split("：")[0].split(" —")[0]}</a>' for lvl, hid, t in toc if lvl == "2")
    body = f"""<header><div class="hd narrow" id="top">
  <div class="no">框</div>
  <div>
    <div class="tag">英文卷公文模板 · 中文卷七段式 · 分析框架 · 考場檢查清單</div>
    <h1>{esc(clean_title)}</h1>
    <div class="en-t">Answer Frameworks, Templates and Phrase Bank</div>
  </div>
  <div class="right">
    <a class="back" href="../議題庫/index.html">← 議題庫</a>
    <a class="back" href="../範文/index.html">範文</a>
  </div>
</div></header>
<nav class="quicknav" aria-label="本頁章節"><div class="in">{nav}<span class="sep"></span><a href="#toc">目錄</a></div></nav>
<div class="wrap narrow">
<nav class="toc" id="toc" aria-label="目錄"><div class="t">目錄</div><ol>{toc_html}</ol></nav>
<div class="doc">{h}</div>
<div class="foot">由備考資料《{esc(title)}》生成。配合<a href="../範文/index.html">範文</a>使用：每篇範文的「審題」和「這篇在做什麼」都按本頁的模板拆解。本頁為備考筆記，不代表政府立場。</div>
</div>"""
    return page(f"{clean_title}｜JRE", DOC_CSS, body, desc="英文卷公文模板、中文卷七段式、分析框架及考場檢查清單")


# ---------------------------------------------------------------- patching existing pages
def replace_marked(s, key, block, anchor_fn):
    """Insert or replace <!-- essay-gen:key -->...<!-- /essay-gen:key -->."""
    start, end = f"<!-- essay-gen:{key} -->", f"<!-- /essay-gen:{key} -->"
    wrapped = f"{start}{block}{end}"
    if start in s and end in s:
        i, j = s.index(start), s.index(end) + len(end)
        return s[:i] + wrapped + s[j:]
    pos = anchor_fn(s)
    if pos is None:
        return None
    return s[:pos] + wrapped + s[pos:]


def patch_topic_index():
    path = os.path.join(TOPIC_DIR, "index.html")
    s = open(path, encoding="utf-8").read()
    block = ('<span class="sep" style="flex:none;width:1px;background:var(--line2);margin:10px 6px"></span>'
             '<a href="../範文/index.html" id="nav-essays">範文</a>'
             '<a href="../答題框架/index.html" id="nav-framework">答題框架</a>')

    def anchor(t):
        i = t.find('<nav class="quicknav">')
        if i < 0:
            return None
        j = t.find("</div></nav>", i)
        return None if j < 0 else j
    new = replace_marked(s, "nav", block, anchor)
    if new is None:
        print("WARN: quicknav not found in 議題庫/index.html")
        return False
    if new != s:
        open(path, "w", encoding="utf-8").write(new)
    return True


def patch_topic_pages(topics, built):
    done = []
    for nn, t in sorted(topics.items()):
        if nn not in built:
            continue
        path = os.path.join(TOPIC_DIR, t["slug"], "index.html")
        s = open(path, encoding="utf-8").read()
        block = (f'<div id="essay-link" style="{HINT_STYLE}">本頁題目已按施政報告及五年規劃原文修訂，定稿題目及範文見 → '
                 f'<a href="../../範文/{t["slug"]}/index.html" style="color:var(--jade);font-weight:700">範文頁</a></div>')

        def anchor(x):
            i = x.find('<section id="exam">')
            if i < 0:
                return None
            k = x.find('<div class="sh">', i)
            j = x.find("</div>", k) if k >= 0 else -1
            return None if j < 0 else j + len("</div>")
        new = replace_marked(s, "essay-link", block, anchor)
        if new is None:
            print(f"WARN: #exam section not found in {path}")
            continue
        if new != s:
            open(path, "w", encoding="utf-8").write(new)
        done.append(t["slug"])
    return done


# ---------------------------------------------------------------- main
def sync_sources():
    up_essays = os.path.join(UPSTREAM, "範文庫")
    os.makedirs(SRC_ESSAYS, exist_ok=True)
    copied = 0
    if os.path.isdir(up_essays):
        for f in sorted(glob.glob(os.path.join(up_essays, "[0-9][0-9]-*.md"))):
            shutil.copy2(f, os.path.join(SRC_ESSAYS, os.path.basename(f)))
            copied += 1
    else:
        print(f"note: {up_essays} not found; using existing tools/src copies")
    up_frame = os.path.join(UPSTREAM, "03-答題框架.md")
    if os.path.isfile(up_frame):
        shutil.copy2(up_frame, SRC_FRAMEWORK)
        copied += 1
    print(f"synced {copied} source file(s) into tools/src/")


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
    if old != content:
        open(path, "w", encoding="utf-8").write(content)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-sync", action="store_true", help="do not copy sources from ~/jre; build from tools/src only")
    ap.add_argument("--upstream", default=None, help="upstream folder (default ~/jre)")
    args = ap.parse_args()
    global UPSTREAM
    if args.upstream:
        UPSTREAM = os.path.abspath(os.path.expanduser(args.upstream))
    if not args.no_sync:
        sync_sources()

    topics = load_topics()
    files = sorted(glob.glob(os.path.join(SRC_ESSAYS, "[0-9][0-9]-*.md")))
    docs = []
    for f in files:
        d = parse_essay_file(f)
        if d["nn"] not in topics:
            print(f"WARN: {os.path.basename(f)} has no matching 議題庫 folder; skipped")
            continue
        topics[d["nn"]].setdefault("nn", d["nn"])
        topics[d["nn"]]["nn"] = d["nn"]
        if not topics[d["nn"]]["name"]:
            topics[d["nn"]]["name"] = d["title"]
        docs.append(d)
    docs.sort(key=lambda d: d["nn"])
    for i, d in enumerate(docs):
        t = topics[d["nn"]]
        prev_t = topics[docs[i - 1]["nn"]] if i > 0 else None
        next_t = topics[docs[i + 1]["nn"]] if i + 1 < len(docs) else None
        write(os.path.join(ESSAY_DIR, t["slug"], "index.html"), render_topic_page(d, t, prev_t, next_t))
    write(os.path.join(ESSAY_DIR, "index.html"), render_index(docs, topics))
    print(f"built 範文/index.html + {len(docs)} topic page(s); {sum(len(d['qs']) for d in docs)} essays")

    if os.path.isfile(SRC_FRAMEWORK):
        write(os.path.join(FRAME_DIR, "index.html"), render_framework(SRC_FRAMEWORK))
        print("built 答題框架/index.html")
    else:
        print("WARN: tools/src/03-答題框架.md missing; 答題框架 page not built")

    patch_topic_index()
    patched = patch_topic_pages(topics, {d["nn"] for d in docs})
    print(f"patched 議題庫/index.html quick-nav and {len(patched)} topic page(s)")


if __name__ == "__main__":
    main()
