#!/usr/bin/env bash
# Temporary source probe for PR #9 recon (removed before merge).
echo "# PROBE PR9"
python3 - <<'PY'
import re
def load(p): return open(p,encoding="utf-8-sig").read().replace("\r","")
src=load("server.py"); L=src.split("\n")
def fn(name):
    m=re.search(r"^def "+name+r"\(.*?(?=^\S)", src, re.S|re.M)
    print("#### def",name); print("```py")
    if m:
        a=src[:m.start()].count("\n")+1
        for i,l in enumerate(m.group(0).split("\n")): print(f"{a+i}|{l}")
    print("```")
def show(a,b,t):
    print("####",t); print("```py")
    for i in range(max(0,a-1),min(b,len(L))): print(f"{i+1}|{L[i]}")
    print("```")
print("#### server index"); print("```")
for i,l in enumerate(L):
    if re.match(r"^(def |class |@app\.|async def )",l): print(f"{i+1}|{l[:150]}")
print("```")
for n in ["_apply_fx_chain","_tv_grade_parts","_tv_grade_filter"]: fn(n)
hits=[i for i,l in enumerate(L) if ("_tv_grade_parts(" in l or "vstack" in l or "text_z" in l or "canvas" in l.lower() and "text" in l.lower()) and not l.lstrip().startswith("def ")]
print("#### hits"); print("```")
for i in hits: print(f"{i+1}|{L[i][:200]}")
print("```")
done=set()
for i in hits:
    if i in done: continue
    a=max(0,i-12); b=min(len(L),i+12)
    for k in range(a,b): done.add(k)
    show(a+1,b,f"ctx {i+1}")
PY
echo "#### editor.js index"; echo '```'; grep -n "^    function \|^function \|^    async function " web/editor.js | cut -c1-120; echo '```'
for w in faceAnchor CoreTimeMap audioClock masterClock "requestAnimationFrame" "cropBox" "hooks\." "lensAmp\|kind === \"lens\"\|fxKind === \"lens\""; do
  echo "#### grep editor $w"; echo '```'; grep -n "$w" web/editor.js | cut -c1-200 | head -40; echo '```'
done
echo "#### grep web for exporter/glPasses/timeMap"; echo '```'; grep -rn "glPasses\|exporter.js\|timeMap\|CoreTimeMap\|lens.js" web --include=*.html --include=*.js | grep -v "^web/core/selftest" | cut -c1-200 | head -40; echo '```'
echo "#### index.html scripts"; echo '```'; grep -n "<script" web/index.html | cut -c1-200; echo '```'
