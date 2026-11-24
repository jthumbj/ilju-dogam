// 방문 확인용 기록: 링크 이름(from)·입력한 이름·인스타 아이디·시간·기기 (생년월일은 저장하지 않음)
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
    const path = `visits/${t}_${ev}_${clean(b.from)}_${clean(b.name)}_${insta}_${dev}.txt`;
    await put(path, '1', { access: process.env.BLOB_ACCESS || 'private', addRandomSuffix: true, contentType: 'text/plain' });
  } catch (e) { /* 기록 실패해도 손님 화면에는 영향 없음 */ }
  res.status(204).end();
};
