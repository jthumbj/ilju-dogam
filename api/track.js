// 테스트 기간 기록: 이름·인스타·입력한 사주 정보·시간·기기 (사장님 지인 테스트용, 이번 주 삭제 예정)
const { put } = require('@vercel/blob');

const clean = (s, n = 20) => String(s || '').replace(/[\/\\?#%*:|"<>\s]+/g, '').replace(/_/g, '＿').slice(0, n) || '-';

module.exports = async (req, res) => {
  if (req.method !== 'POST') { res.status(405).end(); return; }
  try {
    let b = req.body || {};
    if (typeof b === 'string') { try { b = JSON.parse(b); } catch (e) { b = {}; } }
    const ev = b.ev === 'report' ? 'report' : 'open';
    const t = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 19).replace(/:/g, '-');
    const ua = String(req.headers['user-agent'] || '');
    const dev = /iPhone|iPad/.test(ua) ? 'iOS' : /Android/.test(ua) ? 'Android' : 'PC';
    const insta = clean(String(b.insta || '').replace(/^@+/, ''), 30);
    const f = ['gender', 'date', 'cal', 'time', 'job', 'status', 'ints'].map((k) => clean(b[k], 24));
    const path = `visits/${t}_${ev}_${clean(b.from)}_${clean(b.name)}_${insta}_${f.join('_')}_${dev}.txt`;
    await put(path, '1', { access: process.env.BLOB_ACCESS || 'private', addRandomSuffix: true, contentType: 'text/plain' });
  } catch (e) { /* 기록 실패해도 손님 화면에는 영향 없음 */ }
  res.status(204).end();
};
