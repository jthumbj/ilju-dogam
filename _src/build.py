import json, os, re, html, datetime, shutil, sys
sys.path.insert(0, os.path.dirname(__file__))
from data import NY, STEM_INFO, ILJU

BASE = os.environ.get("BASE", "https://ilju60.vercel.app")
SRC = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(SRC), "dist")
TODAY = datetime.date.today().isoformat()
VERIFY = {  # 검색 등록 인증 태그 (받으면 채움)
    "google-site-verification": os.environ.get("GOOGLE_VERIFY", "OfN-ka4E_XYYugQ94mzhFc6f5EbsiLmkKU65TrIBnAQ"),
    "naver-site-verification": os.environ.get("NAVER_VERIFY", ""),
}

STEMS = "甲乙丙丁戊己庚辛壬癸"; BR = "子丑寅卯辰巳午未申酉戌亥"
SK = "갑을병정무기경신임계"; BK = "자축인묘진사오미신유술해"
S_ROM = ["gap", "eul", "byeong", "jeong", "mu", "gi", "gyeong", "sin", "im", "gye"]
B_ROM = ["ja", "chuk", "in", "myo", "jin", "sa", "o", "mi", "sin", "yu", "sul", "hae"]
ANIMAL = ["쥐", "소", "호랑이", "토끼", "용", "뱀", "말", "양", "원숭이", "닭", "개", "돼지"]
B_EL = ["水", "土", "木", "木", "土", "火", "火", "土", "金", "金", "土", "水"]
EL_KO = {"木": "나무", "火": "불", "土": "흙", "金": "쇠", "水": "물"}
COLOR = ["푸른", "푸른", "붉은", "붉은", "누런", "누런", "흰", "흰", "검은", "검은"]
LIUHE = {0: 1, 1: 0, 2: 11, 11: 2, 3: 10, 10: 3, 4: 9, 9: 4, 5: 8, 8: 5, 6: 7, 7: 6}

def ko(i): return SK[i % 10] + BK[i % 12]
def hj(i): return STEMS[i % 10] + BR[i % 12]
def slug(i): return f"{S_ROM[i % 10]}-{B_ROM[i % 12]}"
def josa(word, a, b):  # 받침 여부
    c = word[-1]
    if "가" <= c <= "힣":
        return a if (ord(c) - 0xAC00) % 28 else b
    return a
def esc(s): return html.escape(s, quote=True)
def jdn(y, m, d): return datetime.date(y, m, d).toordinal() + 1721425
def day_idx(dt): return (jdn(dt.year, dt.month, dt.day) + 49) % 60

assert day_idx(datetime.date(2000, 1, 1)) == 54  # 戊午
assert day_idx(datetime.date(2026, 11, 20)) == 34  # 戊戌

css = open(os.path.join(SRC, "style.css"), encoding="utf-8").read()
core_js = open(os.path.join(SRC, "app.js"), encoding="utf-8").read()

def head(title, desc, path, extra=""):
    url = BASE + path
    v = "".join(f'<meta name="{k}" content="{esc(val)}">\n' for k, val in VERIFY.items() if val)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
{v}<meta property="og:type" content="website">
<meta property="og:site_name" content="60일주 도감">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE}/og.png">
<meta property="og:locale" content="ko_KR">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0b1226">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@500;700;900&family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/style.css">
{extra}</head>
"""

FOOT = """  <footer>
    일주는 태어난 날의 간지(干支)로, 음력 입력은 한국천문연구원 기준 음력 데이터로 양력으로 바꿔 계산해요.<br>
    모든 풀이는 재미와 참고를 위한 콘텐츠예요.<br>
    <a href="/">내 일주 찾기</a> · <a href="/ilju/">60일주 전체</a> · <a href="https://www.instagram.com/ilju_dogam/" rel="noopener">인스타그램 @ilju_dogam</a><br>© 60일주 도감
  </footer>"""

def all_links(cur=None):
    out = []
    for i in range(60):
        on = ' class="on"' if i == cur else ""
        out.append(f'<a href="/ilju/{slug(i)}"{on}>{hj(i)}<small>{ko(i)}</small></a>')
    return '<nav class="grid" aria-label="60일주 전체">' + "".join(out) + "</nav>"

# ---------- index ----------
def build_index():
    title = "내 일주 찾기 · 일주 계산기 | 60일주 도감"
    desc = "생년월일만 넣으면 60가지 일주 중 내 일주를 바로 알려드려요. 양력·음력·윤달 지원, 일주별 성격과 2027년 정미년 한 줄 풀이까지. 재미로 보는 사주."
    ld = {
        "@context": "https://schema.org", "@type": "WebApplication", "name": "내 일주 찾기 · 60일주 도감",
        "url": BASE + "/", "applicationCategory": "LifestyleApplication", "operatingSystem": "All",
        "inLanguage": "ko", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "KRW"},
        "description": desc,
    }
    extra = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>\n'
    slugs = json.dumps([slug(i) for i in range(60)])
    body = f"""<body>
<div class="wrap">
  <div class="brand">六十日柱 圖鑑</div>
  <h1>내 일주 찾기</h1>
  <p class="sub">생년월일만 넣으면 60가지 일주 중<br>나는 어떤 유형인지 알려드려요</p>

  <form class="card" id="f">
    <div class="seg" role="tablist">
      <button type="button" class="on" data-cal="solar">양력</button>
      <button type="button" data-cal="lunar">음력</button>
    </div>
    <div class="row">
      <div><label class="f" for="y">년</label><select id="y"></select></div>
      <div><label class="f" for="m">월</label><select id="m"></select></div>
      <div><label class="f" for="d">일</label><select id="d"></select></div>
    </div>
    <label class="chk" id="leapWrap" style="display:none"><input type="checkbox" id="leap"><span>윤달이에요</span></label>
    <label class="chk"><input type="checkbox" id="late"><span>밤 11시 30분 ~ 자정 사이에 태어났어요<small>모르면 체크하지 않아도 괜찮아요</small></span></label>
    <button class="go" type="submit">내 일주 보기</button>
    <div class="err" id="err"></div>
  </form>

  <div class="card" id="result" aria-live="polite">
    <div class="wm" id="wm"></div>
    <div class="lbl">나의 일주</div>
    <div class="name" id="rName"></div>
    <div class="hj" id="rHj"></div>
    <div class="img" id="rImg"></div>
    <div class="kw" id="rKw"></div>
    <p class="desc" id="rDesc"></p>
    <div class="meta" id="rMeta"></div>
    <div class="note" id="rNote" style="display:none"></div>
    <div class="ny" id="rNy">
      <div class="t">2027 丁未年 미리보기</div>
      <div class="h" id="rNyH"></div>
      <p id="rNyP"></p>
      <small>태어난 날 첫 글자와 2027년(정미년) 첫 글자 丁의 관계로 본 한 줄이에요. 2027년 운은 입춘(2월 4일)부터 봐요 · 재미로 보는 사주</small>
    </div>
    <div class="acts">
      <a class="btn" id="more" href="/ilju/">내 일주 자세히 보기 →</a>
      <button class="btn fill" id="copy" type="button">결과 복사해서 친구한테 보내기</button>
      <a class="btn" href="https://www.instagram.com/ilju_dogam/" target="_blank" rel="noopener">@ilju_dogam 팔로우하고 일주 도감 연재 보기 →</a>
      <span class="btn dim">월별 흐름·연애운 상세 리포트 · 오픈 준비 중</span>
    </div>
  </div>

  <section class="card text">
    <h2>일주가 뭐예요?</h2>
    <p>사주는 태어난 해·달·날·시를 네 개의 기둥(四柱)으로 봐요. 그중 <b>태어난 날의 기둥이 일주(日柱)</b>예요. 천간 10개와 지지 12개가 짝을 이뤄 모두 60가지가 있어서 '60일주'라고 불러요.</p>
    <p>일주의 첫 글자(일간)는 사주에서 '나 자신'을 뜻한다고 봐서, MBTI처럼 성격 유형을 볼 때 많이 써요. 같은 날 태어난 사람은 모두 같은 일주예요.</p>
    <p class="mini">태어난 시간이 밤 11시 30분~자정이면 보는 방식에 따라 다음 날 일주로 보기도 해요. 음력 생일은 양력으로 바꿔서 계산해요.</p>
  </section>

  <h2 class="sec">60일주 전체 보기</h2>
  {all_links()}
{FOOT}
</div>
<div class="toast" id="toast">복사됐어요</div>
<script src="/app.js"></script>
<script>window.SLUGS={slugs};</script>
<script src="/finder.js"></script>
</body>
</html>
"""
    return head(title, desc, "/", extra) + body

# ---------- each ilju ----------
def birthdays(i, y0=1990, y1=2005):
    d = datetime.date(y0, 1, 1)
    d += datetime.timedelta(days=(i - day_idx(d)) % 60)
    res = {}
    while d.year <= y1:
        res.setdefault(d.year, []).append(d)
        d += datetime.timedelta(days=60)
    return res

def build_ilju(i):
    s, b = i % 10, i % 12
    img, kw, desc = ILJU[i]
    name = ko(i) + "일주"
    title = f"{name} 성격·특징 ({hj(i)}日柱) | 60일주 도감"
    meta_desc = f"{name}({hj(i)})는 ‘{img}’에 비유하는 {kw} 타입이에요. {desc.split('.')[0]}. 내 생일이 {name}인지, 잘 맞는다고 보는 일주와 2027년 한 줄까지 확인해 보세요."
    yy = "양" if s % 2 == 0 else "음"
    s_el = STEM_INFO[s][1]
    partner_s = (s + 5) % 10
    he_b, chong_b = LIUHE[b], (b + 6) % 12
    he_list = [j for j in range(60) if j % 12 == he_b]
    chong_list = [j for j in range(60) if j % 12 == chong_b]
    partner_list = [j for j in range(60) if j % 10 == partner_s]
    same_stem = [j for j in range(60) if j % 10 == s and j != i]
    link = lambda j: f'<a href="/ilju/{slug(j)}">{ko(j)}</a>'
    bd = birthdays(i)
    bd_html = "".join(
        f'<div class="yr"><b>{y}년</b> ' + " · ".join(f"{d.month}/{d.day}" for d in ds) + "</div>" for y, ds in bd.items())
    ny = NY[s]
    animal = ANIMAL[b]
    color_name = f"{COLOR[s]} {animal}"
    prev_i, next_i = (i - 1) % 60, (i + 1) % 60
    ld = [{
        "@context": "https://schema.org", "@type": "Article", "headline": f"{name}({hj(i)}日柱) 성격과 특징",
        "inLanguage": "ko", "url": f"{BASE}/ilju/{slug(i)}", "dateModified": TODAY,
        "author": {"@type": "Organization", "name": "60일주 도감"},
        "publisher": {"@type": "Organization", "name": "60일주 도감"}, "description": meta_desc,
    }, {
        "@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "내 일주 찾기", "item": BASE + "/"},
            {"@type": "ListItem", "position": 2, "name": "60일주 전체", "item": BASE + "/ilju/"},
            {"@type": "ListItem", "position": 3, "name": name, "item": f"{BASE}/ilju/{slug(i)}"}]}]
    extra = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>\n' for x in ld)
    body = f"""<body>
<div class="wrap">
  <div class="brand"><a href="/">六十日柱 圖鑑</a></div>
  <p class="crumb"><a href="/">내 일주 찾기</a> › <a href="/ilju/">60일주</a> › {name}</p>
  <article>
  <div class="card hero">
    <div class="wm">{hj(i)}</div>
    <div class="lbl">60일주 중 {i + 1}번째</div>
    <h1>{name} <span class="hjs">{hj(i)}日柱</span></h1>
    <div class="img">“{esc(img)}”</div>
    <div class="kw">{esc(kw)}</div>
    <p class="desc">{esc(desc)}</p>
  </div>

  <section class="card text">
    <h2>{name}{josa(name, '은', '는')} 이렇게 만들어져요</h2>
    <p><b>천간 {STEMS[s]}({SK[s]})</b> — {yy}의 {EL_KO[s_el]}({s_el}) 기운으로, ‘{STEM_INFO[s][0]}’에 비유해요. 일주의 첫 글자라 ‘나 자신’을 뜻한다고 봐요.</p>
    <p><b>지지 {BR[b]}({BK[b]})</b> — 띠로는 {animal}{josa(animal, '을', '를')} 뜻하고, {EL_KO[B_EL[b]]}({B_EL[b]}) 기운이에요.</p>
    <p>그래서 {name}를 <b>‘{color_name}’</b>의 날이라고 부르기도 해요.</p>
  </section>

  <section class="card text">
    <h2>잘 맞는다고 보는 일주</h2>
    <p><b>천간합</b> — {STEMS[s]}{josa(SK[s], '은', '는')} {STEMS[partner_s]}({SK[partner_s]}){josa(SK[partner_s], '과', '와')} 합을 이룬다고 봐요({STEMS[min(s, partner_s)]}{STEMS[max(s, partner_s)]}合). 일주 첫 글자가 {SK[partner_s]}인 사람에게 끌린다고 보기도 해요: {' · '.join(link(j) for j in partner_list)}</p>
    <p><b>지지 육합</b> — {BR[b]}{josa(BK[b], '은', '는')} {BR[he_b]}({BK[he_b]}){josa(BK[he_b], '과', '와')} 짝을 이뤄 편안한 사이로 봐요: {' · '.join(link(j) for j in he_list)}</p>
    <p><b>지지 충</b> — {BR[b]}{josa(BK[b], '과', '와')} {BR[chong_b]}({BK[chong_b]}){josa(BK[chong_b], '은', '는')} 부딪히는 관계로 봐요. 나쁘다기보다 서로 자극을 주는 사이예요: {' · '.join(link(j) for j in chong_list)}</p>
    <p class="mini">궁합은 일주 하나만이 아니라 사주 전체를 함께 봐요. 재미로만 참고해 주세요.</p>
  </section>

  <section class="card text ny">
    <div class="t">2027 丁未年 미리보기</div>
    <h2>2027년은 {name}에게 ‘{ny[0]}’</h2>
    <p>{esc(ny[1])}</p>
    <p class="mini">일간 {STEMS[s]}과 2027년 천간 丁의 관계로 본 한 줄이에요. 2027년 운은 입춘(2월 4일)부터 봐요.</p>
  </section>

  <section class="card text">
    <h2>내 생일이 {name}일까?</h2>
    <p>일주는 60일마다 돌아와요. 아래는 1990~2005년 중 {name}에 해당하는 양력 날짜예요.</p>
    <div class="dates">{bd_html}</div>
    <a class="btn fill" href="/">다른 생일도 바로 찾아보기 →</a>
  </section>

  <section class="card text">
    <h2>일간이 같은 일주 ({STEMS[s]} {SK[s]})</h2>
    <p>{' · '.join(link(j) for j in same_stem)}</p>
    <p class="pn"><a href="/ilju/{slug(prev_i)}">← {ko(prev_i)}일주</a><a href="/ilju/{slug(next_i)}">{ko(next_i)}일주 →</a></p>
  </section>
  </article>

  <div class="acts">
    <a class="btn" href="https://www.instagram.com/ilju_dogam/" target="_blank" rel="noopener">@ilju_dogam에서 {name} 카드뉴스 보기 →</a>
  </div>

  <h2 class="sec">60일주 전체 보기</h2>
  {all_links(i)}
{FOOT}
</div>
</body>
</html>
"""
    return head(title, meta_desc, f"/ilju/{slug(i)}", extra) + body

def build_list():
    title = "60일주 전체 목록 · 일주별 성격 | 60일주 도감"
    desc = "갑자일주부터 계해일주까지 60가지 일주의 성격과 특징을 한눈에. 일주별 비유, 키워드, 잘 맞는다고 보는 일주까지 재미로 보는 사주 도감이에요."
    rows = "".join(
        f'<a class="li" href="/ilju/{slug(i)}"><span class="h">{hj(i)}</span><span><b>{ko(i)}일주</b><small>{esc(ILJU[i][1])} · “{esc(ILJU[i][0])}”</small></span></a>'
        for i in range(60))
    body = f"""<body>
<div class="wrap">
  <div class="brand"><a href="/">六十日柱 圖鑑</a></div>
  <h1>60일주 전체</h1>
  <p class="sub">갑자일주부터 계해일주까지<br>일주별 성격을 한눈에 보세요</p>
  <a class="btn fill" href="/">내 일주 먼저 찾기 →</a>
  <div class="list">{rows}</div>
{FOOT}
</div>
</body>
</html>
"""
    return head(title, desc, "/ilju/") + body

FINDER_JS = r"""
const NY=%NY%, STEM_INFO=%SI%, ILJU=%IJ%;
(function(){
  let cal='solar';
  const $=id=>document.getElementById(id);
  const ySel=$('y'),mSel=$('m'),dSel=$('d');
  const minY=LUNAR_START, maxY=LUNAR_START+LUNAR.length-1;
  for(let y=maxY;y>=minY;y--) ySel.add(new Option(y+'년',y));
  ySel.value=1995;
  for(let m=1;m<=12;m++) mSel.add(new Option(m+'월',m));
  function fillDays(){
    const keep=+dSel.value||1, y=+ySel.value, m=+mSel.value;
    let n=30; if(cal==='solar'){n=new Date(y,m,0).getDate();}
    dSel.innerHTML=''; for(let d=1;d<=n;d++) dSel.add(new Option(d+'일',d));
    dSel.value=Math.min(keep,n);
  }
  fillDays(); ySel.onchange=mSel.onchange=fillDays;
  document.querySelectorAll('.seg button').forEach(b=>b.onclick=()=>{
    cal=b.dataset.cal; document.querySelectorAll('.seg button').forEach(x=>x.classList.toggle('on',x===b));
    $('leapWrap').style.display=cal==='lunar'?'flex':'none'; fillDays();
  });
  function show(idx,ctx){
    const p=pillarName(idx), [img,kw,desc]=ILJU[idx], s=STEM_INFO[idx%10];
    $('wm').textContent=p.hanja; $('rName').textContent=p.ko+'일주'; $('rHj').textContent=p.hanja+'日柱';
    $('rImg').textContent='“'+img+'”'; $('rKw').textContent=kw; $('rDesc').textContent=desc;
    $('rMeta').innerHTML=`<span>나의 기운 · ${p.hanja[0]} ${s[0]} (${s[1]})</span><span>60일주 중 ${idx+1}번째</span>`;
    const note=$('rNote'); let html='';
    if(ctx&&ctx.solarText) html+=`양력 <b>${ctx.solarText}</b> 기준으로 계산했어요.`;
    if(ctx&&ctx.late){const n=pillarName((idx+1)%60);html+=(html?'<br>':'')+`밤 11시 30분 이후 출생은 보는 방식에 따라 다음 날인 <b>${n.ko}일주(${n.hanja})</b>로 보기도 해요.`;}
    note.innerHTML=html; note.style.display=html?'block':'none';
    const ny=NY[idx%10];
    $('rNyH').textContent=`2027년은 나에게 ‘${ny[0]}’`;
    $('rNyP').textContent=ny[1];
    $('more').href='/ilju/'+window.SLUGS[idx]; $('more').textContent=p.ko+'일주 자세히 보기 →';
    window.__last=`나는 ${p.ko}일주(${p.hanja}) — ${kw}\n“${img}”\n2027년은 나에게 ‘${ny[0]}’\n너는 몇 일주야? ${location.origin}\n@ilju_dogam #60일주도감 #내일주찾기`;
    const r=$('result'); r.classList.remove('show'); void r.offsetWidth; r.classList.add('show');
    r.scrollIntoView({behavior:'smooth',block:'start'});
  }
  $('f').onsubmit=e=>{
    e.preventDefault(); $('err').textContent='';
    let y=+ySel.value,m=+mSel.value,d=+dSel.value, ctx={late:$('late').checked};
    if(cal==='lunar'){
      const r=lunarToSolar(y,m,d,$('leap').checked);
      if(r.error){$('err').textContent=r.error;return;}
      ctx.solarText=`${r.y}년 ${r.m}월 ${r.d}일`; y=r.y;m=r.m;d=r.d;
    } else if(!validSolar(y,m,d)){$('err').textContent='날짜를 확인해 주세요.';return;}
    show(dayPillarIndex(y,m,d),ctx);
  };
  $('copy').onclick=async()=>{
    const t=$('toast');
    try{await navigator.clipboard.writeText(window.__last);t.textContent='복사됐어요! 댓글이나 스토리에 붙여넣어 보세요';}
    catch(_){t.textContent='복사가 안 되는 환경이에요. 화면을 캡처해 주세요';}
    t.classList.add('on'); setTimeout(()=>t.classList.remove('on'),2200);
  };
})();
"""

def main():
    if os.path.exists(OUT): shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "ilju"))
    w = lambda p, c: open(os.path.join(OUT, p), "w", encoding="utf-8").write(c)
    w("index.html", build_index())
    w("ilju/index.html", build_list())
    for i in range(60):
        w(f"ilju/{slug(i)}.html", build_ilju(i))
    shutil.copy(os.path.join(SRC, "og.png"), os.path.join(OUT, "og.png"))
    w("style.css", css)
    w("app.js", core_js)
    w("finder.js", FINDER_JS.replace("%NY%", json.dumps(NY, ensure_ascii=False))
      .replace("%SI%", json.dumps(STEM_INFO, ensure_ascii=False)).replace("%IJ%", json.dumps(ILJU, ensure_ascii=False)))
    w("favicon.svg", '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#0b1226"/><text x="32" y="44" font-size="30" text-anchor="middle" fill="#d4af5f" font-family="serif" font-weight="700">60</text></svg>')
    urls = [("/", "1.0"), ("/ilju/", "0.8")] + [(f"/ilju/{slug(i)}", "0.7") for i in range(60)]
    w("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
      "".join(f"  <url><loc>{BASE}{u}</loc><lastmod>{TODAY}</lastmod><priority>{p}</priority></url>\n" for u, p in urls) + "</urlset>\n")
    w("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n")
    w("vercel.json", json.dumps({"cleanUrls": True}, indent=2))
    w("README.md", "# 60일주 도감 · 내 일주 찾기\n\n생년월일로 60일주 중 내 일주를 찾는 정적 사이트. `src/build.py`로 생성.\n")
    print("built", len(os.listdir(os.path.join(OUT, 'ilju'))), "ilju pages")

if __name__ == "__main__":
    main()
