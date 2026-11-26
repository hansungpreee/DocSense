"""사용 방법 안내(투어): 메뉴를 하나씩 가리키며 그 부분만 밝게 두고 나머지는 어둡게 가린다.
화면 아무 곳이나 누르면 다음 단계, 「건너뛰기」는 항상 있다. 하루에 한 번(브라우저 저장소의 날짜로 판단)만 자동으로 나온다.
스트림릿은 화면 위에 덧씌우는 기능이 없어 숨은 iframe의 스크립트가 부모 문서에 겹침 화면을 붙인다 (같은 출처라 가능)."""
import json

import streamlit.components.v1 as components

from i18n import t

# 가리킬 대상: 사이드바 메뉴 5개(순서대로) + 도움말 버튼
STEPS = [
    ("nav:0", "대시보드: 대분류 맵입니다. 우리 부서 대분류가 가운데에서 주황색으로 빛나고, 원을 누르면 그 문서들이 나옵니다."),
    ("nav:1", "업로드: 문서를 올려 분류합니다. 끝나면 분류 근거가 바로 팝업으로 나옵니다."),
    ("nav:2", "이력: 내가 분류한 문서 기록을 찾아봅니다."),
    ("nav:3", "문서 양식: 회사 문서 양식을 내려받습니다."),
    ("nav:4", "설정: 글자 크기, 언어, 이 안내의 표시 여부를 바꿉니다."),
    ("css:.st-key-help_btn", "도움말: 언제든 여기서 프로그램 설명을 볼 수 있습니다."),
]

SCRIPT = """<script>
(function(){
const cfg=__CFG__, P=window.parent, D=P.document;
const today=new Date().toISOString().slice(0,10), key='docsense_tour_'+cfg.emp;
let seen=null; try{seen=P.localStorage.getItem(key);}catch(e){}
if(D.getElementById('ds-tour')) return;               // 이미 진행 중이면 다시 만들지 않는다
if(!cfg.force && seen===today) return;                // 오늘 이미 봤으면 건너뜀
function target(sel){
  if(sel.startsWith('nav:')) return D.querySelectorAll('[data-testid="stSidebarNav"] a,[data-testid="stSidebarNavLink"]')[+sel.slice(4)];
  return D.querySelector(sel.slice(4));
}
// 메뉴가 그려지기 전에 스크립트가 먼저 돌 수 있어 최대 6초 기다린다 (그동안은 오늘 본 것으로 치지 않는다)
let tries=0;
const wait=setInterval(function(){
  const ready=cfg.steps.filter(s=>target(s.sel));
  if(ready.length<cfg.steps.length && ++tries<20) return;
  clearInterval(wait);
  if(ready.length && !D.getElementById('ds-tour')) run(ready);
},300);
function run(steps){
try{P.localStorage.setItem(key,today);}catch(e){}
const root=D.createElement('div'); root.id='ds-tour';
root.style.cssText='position:fixed;inset:0;z-index:999999;cursor:pointer;font-family:sans-serif';
const hole=D.createElement('div');
hole.style.cssText='position:fixed;border-radius:12px;box-shadow:0 0 0 9999px rgba(0,0,0,.82);outline:3px solid #d9622b;transition:all .25s;pointer-events:none';
const tip=D.createElement('div');
tip.style.cssText='position:fixed;max-width:340px;background:#fff;color:#111;border-radius:12px;padding:14px 16px;font-size:15px;line-height:1.5;box-shadow:0 8px 30px rgba(0,0,0,.5);pointer-events:none';
const skip=D.createElement('button'); skip.textContent=cfg.skip;
skip.style.cssText='position:fixed;right:24px;top:20px;padding:8px 18px;border-radius:999px;border:0;background:#d9622b;color:#fff;font-size:15px;font-weight:700;cursor:pointer';
root.append(hole,tip,skip); D.body.appendChild(root);
let i=0;
function close(){root.remove();}
function draw(){
  const s=steps[i], r=target(s.sel).getBoundingClientRect(), pad=6;
  hole.style.left=(r.left-pad)+'px'; hole.style.top=(r.top-pad)+'px';
  hole.style.width=(r.width+2*pad)+'px'; hole.style.height=(r.height+2*pad)+'px';
  const hint=i===steps.length-1?cfg.last:cfg.next;
  tip.innerHTML='<div style="color:#d9622b;font-weight:700;margin-bottom:4px">'+(i+1)+' / '+steps.length+'</div>'
    +'<div></div><div style="margin-top:8px;color:#777;font-size:13px"></div>';
  tip.children[1].textContent=s.text; tip.children[2].textContent=hint;
  const w=Math.min(340,P.innerWidth-24);
  tip.style.left=Math.max(12,Math.min(r.right+20,P.innerWidth-w-12))+'px';
  tip.style.top=Math.max(12,Math.min(r.top,P.innerHeight-170))+'px';
}
root.addEventListener('click',()=>{ if(++i>=steps.length) close(); else draw(); });
skip.addEventListener('click',e=>{e.stopPropagation(); close();});
P.addEventListener('keydown',function h(e){ if(!D.getElementById('ds-tour')){P.removeEventListener('keydown',h);return;} if(e.key==='Escape') close(); });
draw();
}
})();
</script>"""


def show(emp_id: str, force: bool = False):
    """화면 어디서든 한 번 부르면 된다 (main.py). force=True면 오늘 봤어도 다시 보여 준다."""
    cfg = {"emp": emp_id, "force": force, "skip": t("건너뛰기"), "next": t("다음: 아무 곳이나 클릭"),
           "last": t("끝내기: 아무 곳이나 클릭"), "steps": [{"sel": sel, "text": t(text)} for sel, text in STEPS]}
    # </script>로 끊기지 않도록 < 를 이스케이프한다
    components.html(SCRIPT.replace("__CFG__", json.dumps(cfg, ensure_ascii=False).replace("<", "\\u003c")), height=0)
