"""온도 손님·인스타 방문자용 2027 신년운세 웹 리포트 (입력값은 계산에만 쓰고 저장하지 않음)"""
import html
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs

sys.path.insert(0, os.path.dirname(__file__))
import _nyr as R  # noqa: E402

STORE_CODES = {"온도", "ondo", "ondo2027", "온도2027"}
FIELDS = ("name", "gender", "date", "calendar", "leap", "time", "time_unknown", "job", "status", "interests", "code")


def err_page(msg):
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>입력 확인</title></head><body style="background:#0d1630;color:#ece7da;font-family:sans-serif;padding:40px 20px;text-align:center">'
            f'<p style="font-size:17px;line-height:1.8">{html.escape(msg)}</p><p><a href="/report" style="color:#d4b06a">← 다시 입력하기</a></p></body></html>')


class handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Robots-Tag", "noindex")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        self.send_response(302)
        self.send_header("Location", "/report")
        self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 5000:
            return self._send(413, err_page("입력이 너무 길어요."))
        q = parse_qs(self.rfile.read(n).decode("utf-8"), keep_blank_values=True)
        g = lambda k: (q.get(k) or [""])[0].strip()
        try:
            date = g("date")
            y = int(date[:4])
            if not (1930 <= y <= 2026) or len(date) != 10:
                return self._send(400, err_page("생년월일을 다시 확인해 주세요. (1930~2026년)"))
            t = g("time")
            if g("time_unknown") or not t:
                t = None
            elif len(t) != 5 or t[2] != ":":
                return self._send(400, err_page("태어난 시간을 다시 확인해 주세요."))
            data = {"name": g("name")[:12], "gender": g("gender"), "date": date,
                    "calendar": "lunar" if g("calendar") == "lunar" else "solar", "leap": bool(g("leap")),
                    "time": t, "job": g("job"), "status": g("status"), "interests": (q.get("interests") or [])[:2]}
            full = g("code").replace(" ", "").lower() in STORE_CODES
            hidden = "".join(f'<input type="hidden" name="{k}" value="{html.escape(v, quote=True)}">'
                             for k in FIELDS for v in (q.get(k) or []))
            p = R.calc_person(data)
            Y = R.calc_year()
            if g("format") == "print" and full:
                out = R.render(p, Y, mode="print", hidden="autoprint")
            else:
                out = R.render(p, Y, mode="web", full=full, hidden=hidden)
            return self._send(200, out)
        except Exception:
            return self._send(400, err_page("입력한 날짜로 계산할 수 없어요. 음력·윤달 여부와 날짜를 다시 확인해 주세요."))
