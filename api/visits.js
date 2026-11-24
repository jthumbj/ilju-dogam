// 사장님 전용 방문 기록 보기: /api/visits?key=비밀키
const { list } = require('@vercel/blob');
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

module.exports = async (req, res) => {
  const key = (req.query && req.query.key) || '';
  if (!process.env.VISITS_KEY || key !== process.env.VISITS_KEY) { res.status(404).send('Not found'); return; }
  let blobs = [], cursor;
  do {
    const r = await list({ prefix: 'visits/', cursor, limit: 1000 });
    blobs = blobs.concat(r.blobs);
    cursor = r.hasMore ? r.cursor : undefined;
  } while (cursor);
  const rows = blobs.map((b) => {
    const parts = b.pathname.replace(/^visits\//, '').replace(/\.txt$/, '').split('_').map((x) => x.replace(/＿/g, '_'));
    const [t, ev, from, name] = parts;
    const insta = parts.length >= 6 ? parts[4] : '-';
    const devx = parts[parts.length - 1];
    return { t: (t || '').replace('T', ' ').replace(/-(\d\d)-(\d\d)$/, ':$1:$2'), ev, from, name, insta, dev: (devx || '').split('-')[0] };
  }).sort((a, b) => (a.t < b.t ? 1 : -1));
  const people = {};
  rows.forEach((r) => {
    if (r.ev !== 'report') return;
    const who = `${r.name}\u0000${r.insta}`;
    people[who] = people[who] || { open: 0, report: 0, last: r.t };
    people[who][r.ev === 'report' ? 'report' : 'open'] += 1;
  });
  const opens = rows.filter((r) => r.ev === 'open').length;
  const reports = rows.filter((r) => r.ev === 'report').length;
  const ppl = Object.entries(people).sort((a, b) => (a[1].last < b[1].last ? 1 : -1))
    .map(([n, v]) => { const [nm, ig] = n.split('\u0000'); return `<tr><td>${esc(nm)}</td><td>${ig !== '-' ? `<a href="https://instagram.com/${encodeURIComponent(ig)}" style="color:#d4b06a">@${esc(ig)}</a>` : '-'}</td><td>${v.report}</td><td>${esc(v.last)}</td></tr>`; }).join('');
  const log = rows.slice(0, 300).map((r) => `<tr><td>${esc(r.t)}</td><td>${r.ev === 'report' ? '리포트 봄' : '페이지 열기'}</td><td>${esc(r.name)}</td><td>${r.insta && r.insta !== '-' ? '@' + esc(r.insta) : '-'}</td><td>${esc(r.dev)}</td></tr>`).join('');
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('X-Robots-Tag', 'noindex');
  res.send(`<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>방문 기록</title>
<style>body{font-family:sans-serif;background:#0d1630;color:#ece7da;padding:18px;max-width:760px;margin:auto}h1{color:#f0d9a6;font-size:20px}h2{color:#d4b06a;font-size:15px;margin-top:22px}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:7px 6px;border-bottom:1px solid rgba(255,255,255,.1);text-align:left}th{color:#a3abbf;font-weight:400}.n{font-size:28px;color:#f0d9a6}</style></head><body>
<h1>2027 신년운세 리포트 · 방문 기록</h1>
<p>페이지 열기 <span class="n">${opens}</span>회 · 리포트 생성 <span class="n">${reports}</span>회</p>
<h2>누가 봤나 (사주에 쓴 이름 · 인스타 아이디, 최근 순)</h2><table><tr><th>이름</th><th>인스타</th><th>리포트</th><th>마지막</th></tr>${ppl || '<tr><td colspan=4>아직 없어요</td></tr>'}</table>
<h2>전체 기록 (최근 300개 · 한국 시간)</h2><table><tr><th>시간</th><th>행동</th><th>이름</th><th>인스타</th><th>기기</th></tr>${log}</table>
</body></html>`);
};
