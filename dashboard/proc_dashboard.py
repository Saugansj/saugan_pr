"""Local process dashboard (Windows). Run: python dashboard/proc_dashboard.py, open http://127.0.0.1:8765"""
import json
import re
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8765
TRACKED = re.compile(r"^(python|pythonw|node)(\.exe)?$", re.I)
PS = (
    "Get-CimInstance Win32_Process | "
    "Select-Object ProcessId,Name,CommandLine,WorkingSetSize | ConvertTo-Json -Compress"
)


def scan():
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", PS],
        capture_output=True, text=True, timeout=20, check=True,
    ).stdout
    rows = json.loads(out)
    return rows if isinstance(rows, list) else [rows]


def summarise(rows):
    mb = lambda r: (r["WorkingSetSize"] or 0) / 1048576
    groups = {}
    for r in rows:
        name = r["Name"] or "?"
        g = groups.setdefault(name, {"name": name, "count": 0, "mb": 0.0, "tracked": bool(TRACKED.match(name))})
        g["count"] += 1
        g["mb"] += mb(r)
    top = sorted(groups.values(), key=lambda g: -g["mb"])[:12]
    for g in top:
        g["mb"] = round(g["mb"], 1)
    tracked = sorted(
        ({"pid": r["ProcessId"], "name": r["Name"], "mb": round(mb(r), 1), "cmd": r["CommandLine"] or ""}
         for r in rows if TRACKED.match(r["Name"] or "")),
        key=lambda t: -t["mb"],
    )
    return {"total": len(rows), "mb": round(sum(mb(r) for r in rows)), "top": top, "tracked": tracked}


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Processes</title>
<style>
:root{color-scheme:light;--surface:#fcfcfb;--panel:#f4f3f0;--ink:#0b0b0b;--ink2:#52514e;--grid:#e4e2dc;--s1:#2a78d6;--s2:#eb6834}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--surface:#1a1a19;--panel:#242422;--ink:#fff;--ink2:#c3c2b7;--grid:#34332f;--s1:#3987e5;--s2:#d95926}}
*{box-sizing:border-box}
body{margin:0;background:var(--surface);color:var(--ink);font:14px/1.4 system-ui,sans-serif}
main{max-width:1000px;margin:0 auto;padding:24px 16px}
h1{font-size:20px;margin:0}h2{font-size:15px;margin:0 0 12px}
header{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:20px}
#stamp{color:var(--ink2);font-size:13px}#stamp.err{color:var(--ink);font-weight:600}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:20px}
.tile,.card{background:var(--panel);border-radius:8px;padding:16px}
.tile .v{font-size:30px;font-weight:600}.tile .l{color:var(--ink2);font-size:13px}
.card{margin-bottom:20px}
.legend{display:flex;gap:16px;color:var(--ink2);font-size:13px;margin-bottom:12px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
.row{display:grid;grid-template-columns:150px 1fr 90px;align-items:center;gap:10px;padding:3px 0}
.row .n{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.row .val{text-align:right;color:var(--ink2);font-variant-numeric:tabular-nums}
.track{height:14px}.bar{height:100%;min-width:2px;border-radius:0 4px 4px 0}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--grid);vertical-align:top}
th{color:var(--ink2);font-weight:500;font-size:13px}
td.num{text-align:right;font-variant-numeric:tabular-nums}
td.cmd{word-break:break-all;color:var(--ink2);font-size:12px}
.empty{color:var(--ink2)}
#tip{position:fixed;pointer-events:none;background:var(--ink);color:var(--surface);padding:6px 10px;border-radius:6px;font-size:13px;display:none}
@media (max-width:560px){.row{grid-template-columns:100px 1fr 70px}}
</style></head><body><main>
<header><h1>Processes on this machine</h1><span id="stamp">Scanning...</span></header>
<section class="tiles">
 <div class="tile"><div class="v" id="t-total">-</div><div class="l">Running processes</div></div>
 <div class="tile"><div class="v" id="t-mem">-</div><div class="l">Memory in use (GB)</div></div>
 <div class="tile"><div class="v" id="t-trk">-</div><div class="l">python / node processes</div></div>
</section>
<section class="card"><h2>Memory by program (top 12)</h2>
 <div class="legend"><span><i style="background:var(--s2)"></i>python / node</span><span><i style="background:var(--s1)"></i>everything else</span></div>
 <div id="bars"></div></section>
<section class="card"><h2>python / node processes</h2><div id="trk"></div></section>
</main><div id="tip"></div>
<script>
const $=id=>document.getElementById(id), tip=$('tip');
function el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e}
function hover(e,text){
 e.onmousemove=ev=>{tip.textContent=text;tip.style.display='block';tip.style.left=ev.clientX+12+'px';tip.style.top=ev.clientY+12+'px'};
 e.onmouseleave=()=>{tip.style.display='none'}}
function draw(d){
 $('t-total').textContent=d.total;$('t-mem').textContent=(d.mb/1024).toFixed(1);$('t-trk').textContent=d.tracked.length;
 const max=Math.max(1,...d.top.map(g=>g.mb)), bars=$('bars');bars.replaceChildren();
 for(const g of d.top){
  const row=el('div','row'),track=el('div','track'),bar=el('div','bar');
  bar.style.width=g.mb/max*100+'%';bar.style.background=g.tracked?'var(--s2)':'var(--s1)';track.append(bar);
  row.append(el('div','n',g.name),track,el('div','val',g.mb.toLocaleString()+' MB'));
  hover(row,g.name+': '+g.count+' process'+(g.count>1?'es':'')+', '+g.mb.toLocaleString()+' MB');bars.append(row)}
 const t=$('trk');t.replaceChildren();
 if(!d.tracked.length){t.append(el('div','empty','No python or node processes running.'));return}
 const tb=el('table'),hr=el('tr');
 for(const h of ['PID','Program','MB','Command'])hr.append(el('th','',h));tb.append(hr);
 for(const p of d.tracked){const r=el('tr');
  r.append(el('td','num',p.pid),el('td','',p.name),el('td','num',p.mb.toLocaleString()),el('td','cmd',p.cmd||'(not readable)'));tb.append(r)}
 t.append(tb)}
async function tick(){
 try{draw(await (await fetch('/api/procs')).json());$('stamp').textContent='Updated '+new Date().toLocaleTimeString();$('stamp').className=''}
 catch(e){$('stamp').textContent='Scan failed, retrying...';$('stamp').className='err'}}
tick();setInterval(tick,5000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/procs":
            try:
                body, code, kind = json.dumps(summarise(scan())).encode(), 200, "application/json"
            except Exception as e:  # report the scan failure to the page, keep serving
                body, code, kind = str(e).encode(), 500, "text/plain"
        elif self.path == "/":
            body, code, kind = PAGE.encode(), 200, "text/html; charset=utf-8"
        else:
            body, code, kind = b"not found", 404, "text/plain"
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"Process dashboard: http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
