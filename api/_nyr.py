#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
60일주 도감 · 2027 정미년(丁未年) 내 일주 신년운세 리포트 생성기
----------------------------------------------------------------
입력(생년월일·양력/음력·성별·태어난 시간(선택))만 바꾸면
만세력 계산 → 2027 세운·월건 계산 → 규칙 판정 → HTML → A4 PDF 까지 자동으로 만듭니다.

필요: pip install --break-system-packages lunar-python playwright
      (Noto Serif/Sans CJK KR 폰트)

사용법
  python3 newyear_report.py                         # 내장 샘플(가상 인물 1994-03-21 여, 시간 모름)
  python3 newyear_report.py input.json              # JSON 입력
  python3 newyear_report.py input.json -o 결과.pdf

input.json 예시
  {"name": "서연", "gender": "여", "date": "1994-03-21", "calendar": "solar", "time": null}
  - calendar: "solar"(양력) 또는 "lunar"(음력). 음력 윤달이면 "leap": true
  - time: "HH:MM" 또는 null(모름) → 모르면 시주 없이 6글자 기준

계산 기준(리포트에도 표기)
  - lunar-python 만세력(절기 기준 년·월주, 입춘 기준 년 전환)
  - 태어난 시간이 있으면 동경 127.5° 보정(-30분), 1987·88 서머타임 기간 추가 -60분
  - 23시 이후 출생은 다음 날 일주(야자시 미적용)
  - 일주는 idx = (54 + (날짜 - 2000-01-01).days) % 60 공식으로 교차 검증
  - 2027 세운 丁未(입춘 기준) · 월건(12절 기준)을 코드로 계산하고 오호둔(五虎遁) 공식으로 교차 검증
  - 절입 시각은 lunar-python(베이징 시각, UTC+8)에 +1시간 해서 한국 표준시로 표기
  - 오행 분포는 원국 천간·지지 글자 기준(지장간 미포함)
"""
import datetime
import html
import json
import math
import sys
from pathlib import Path

from lunar_python import Lunar, Solar
from lunar_python.util import LunarUtil

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
GAN_KR = dict(zip(GAN, "갑을병정무기경신임계"))
ZHI_KR = dict(zip(ZHI, "자축인묘진사오미신유술해"))
GAN_EL = dict(zip(GAN, "木木火火土土金金水水"))
ZHI_EL = dict(zip(ZHI, "水土木木土火火土金金土水"))
ZHI_MAIN = dict(zip(ZHI, "癸己甲乙戊丙丁己庚辛戊壬"))  # 지지 본기
GAN_YY = {g: ("양" if i % 2 == 0 else "음") for i, g in enumerate(GAN)}
ZHI_YY = {z: ("양" if i % 2 == 0 else "음") for i, z in enumerate(ZHI)}
EL_KR = {"木": "목", "火": "화", "土": "토", "金": "금", "水": "수"}
EL_ORDER = ["木", "火", "土", "金", "水"]
EL_COLOR = {"木": "#6fae8a", "火": "#d9796a", "土": "#c9a76a", "金": "#c7ccd6", "水": "#6f97d1"}
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

TARGET_YEAR = 2027
TARGET_GZ = "丁未"
NAYIN_KR = {"天河水": "천하수"}

# ─────────────────────────── 이론 데이터 ───────────────────────────
STEM = {
    "甲": dict(img="곧게 뻗은 큰 나무", kw=["추진력", "곧은 마음", "리더십"],
              desc="목표가 생기면 곧게 뻗어 나가는 큰 나무 같은 기운이에요. 시작하는 힘이 좋고, 옳다고 믿는 방향을 쉽게 굽히지 않는 편이에요.",
              strength="시작하는 힘과 믿음직함", care="내 방식이 맞다고 느낄 때 주변의 속도를 놓치기 쉬워요."),
    "乙": dict(img="부드럽게 뻗는 풀과 덩굴", kw=["유연함", "친화력", "적응력"],
              desc="부드럽게 휘어지면서도 끝내 자리를 잡는 풀과 덩굴 같은 기운이에요. 분위기를 잘 읽고, 사람 사이에서 자연스럽게 길을 찾아요.",
              strength="유연한 적응력", care="맞춰 주다가 정작 내 마음은 말하지 못하고 쌓아 두기 쉬워요."),
    "丙": dict(img="세상을 비추는 태양", kw=["밝음", "솔직함", "표현력"],
              desc="세상을 환하게 비추는 태양 같은 기운이에요. 솔직하고 밝아서 어디서든 분위기를 띄우는 힘이 있어요.",
              strength="밝은 에너지와 표현력", care="감정이 빨리 달아오르는 만큼 말이 먼저 나가기도 해요."),
    "丁": dict(img="어둠을 밝히는 촛불", kw=["섬세함", "따뜻함", "집중력"],
              desc="어둠 속을 은은하게 밝히는 촛불 같은 기운이에요. 섬세하고 따뜻하며, 한 가지에 깊이 집중하는 힘이 있어요.",
              strength="세심함과 집중력", care="서운함을 겉으로 드러내지 않고 속으로 오래 품을 수 있어요."),
    "戊": dict(img="넓고 묵직한 큰 산", kw=["듬직함", "포용력", "신뢰"],
              desc="넓고 묵직한 큰 산 같은 기운이에요. 쉽게 흔들리지 않고, 주변 사람을 품어 주는 포용력이 있어요.",
              strength="흔들리지 않는 듬직함", care="한번 정한 생각을 바꾸는 데 시간이 걸리고, 표현이 담백해 무심해 보일 수 있어요."),
    "己": dict(img="씨앗을 품은 논밭", kw=["배려", "실속", "돌봄"],
              desc="씨앗을 품고 길러 내는 논밭 같은 기운이에요. 실속 있고 세심하며, 사람을 돌보는 데 능해요.",
              strength="세심한 배려와 실속", care="걱정이 많아질 때 생각이 꼬리를 물기 쉬워요."),
    "庚": dict(img="단단한 원석과 바위", kw=["결단력", "의리", "직진"],
              desc="단단한 원석이나 바위 같은 기운이에요. 결단이 빠르고 의리가 강하며, 맺고 끊음이 분명해요.",
              strength="결단력과 의리", care="직설적인 말이 의도보다 세게 전달될 수 있어요."),
    "辛": dict(img="정갈하게 다듬어진 보석", kw=["감각", "깔끔함", "자존감"],
              desc="다듬어진 보석처럼 섬세하고 정갈한 기운이에요. 미적 감각이 좋고, 자기만의 기준이 분명해요.",
              strength="세련된 감각", care="기준이 높은 만큼 작은 말에도 예민해질 수 있어요."),
    "壬": dict(img="넓게 흐르는 큰 강과 바다", kw=["넓은 시야", "자유로움", "지혜"],
              desc="넓게 흐르는 큰 강과 바다 같은 기운이에요. 생각의 스케일이 크고, 자유롭게 흐르며 많은 것을 받아들여요.",
              strength="넓은 시야와 포용력", care="생각이 많아 계획이 자주 바뀌거나, 속마음을 다 보여 주지 않을 때가 있어요."),
    "癸": dict(img="조용히 스며드는 비와 이슬", kw=["감수성", "직관", "공감력"],
              desc="조용히 스며드는 비와 이슬 같은 기운이에요. 감수성과 직관이 좋고, 드러나지 않게 주변을 적셔 주는 힘이 있어요.",
              strength="공감력과 직관", care="감정을 혼자 삭이다 보면 마음이 가라앉을 때가 있어요."),
}

BRANCH = {
    "子": dict(animal="쥐", img="한겨울 밤의 물", desc="영리하고 감수성이 풍부한 면이 가까운 관계에서 드러나요. 조용한 시간에 깊은 대화를 나누는 걸 좋아해요."),
    "丑": dict(animal="소", img="한겨울의 단단한 땅", desc="천천히, 하지만 깊게 마음을 쌓아 가는 타입이에요. 한번 믿으면 오래 가는 성실함이 있어요."),
    "寅": dict(animal="호랑이", img="이른 봄의 큰 나무", desc="새로운 걸 해 보고 싶어 하는 활동적인 면이 있어요. 주변에 활기를 불어넣어요."),
    "卯": dict(animal="토끼", img="봄날의 꽃과 풀", desc="다정하고 감각적인 면이 드러나요. 분위기 있는 순간과 소소한 표현을 좋아해요."),
    "辰": dict(animal="용", img="봄비를 머금은 땅", desc="포부가 크고 재주가 다양해요. 미래를 그리는 이야기를 즐기는 편이에요."),
    "巳": dict(animal="뱀", img="초여름의 불", desc="겉으로는 차분해 보여도 속에 열정을 품고 있어요. 상황을 꿰뚫어 보는 통찰이 있어요."),
    "午": dict(animal="말", img="한여름의 태양", desc="감정 표현이 시원하고 열정적이에요. 함께 있는 사람에게 에너지를 나눠 줘요."),
    "未": dict(animal="양", img="늦여름의 따뜻한 땅", desc="온화하고 배려심이 깊어요. 다만 마음속에 정한 고집이 은근히 있어요."),
    "申": dict(animal="원숭이", img="초가을의 쇠", desc="재치 있고 실행력이 좋아요. 문제를 해결할 때 든든해요."),
    "酉": dict(animal="닭", img="가을의 보석", desc="깔끔하고 완성도를 중요하게 여겨요. 약속과 디테일을 잘 지키는 편이에요."),
    "戌": dict(animal="개", img="늦가을의 마른 땅", desc="의리와 책임감이 강해요. 내 사람을 끝까지 챙기는 든든함이 있어요."),
    "亥": dict(animal="돼지", img="초겨울의 큰 물", desc="너그럽고 상상력이 풍부해요. 사람을 편하게 받아 주는 품이 있어요."),
}

DISHI = {
    "长生": ("장생", "새로 싹트는 기운 — 시작과 성장의 힘"), "沐浴": ("목욕", "호기심과 감수성이 살아 있는 기운"),
    "冠带": ("관대", "자신감을 갖추고 세상에 나서는 기운"), "临官": ("건록", "스스로 서는 자립의 기운"),
    "帝旺": ("제왕", "기운이 가장 차오른 주도적인 자리"), "衰": ("쇠", "힘을 고르며 노련해지는 기운"),
    "病": ("병", "공감과 상상력이 깊어지는 기운"), "死": ("사", "한 가지에 몰입하고 탐구하는 기운"),
    "墓": ("묘", "차곡차곡 쌓아 두는 신중한 기운"), "绝": ("절", "끊고 새로 시작하는 전환의 기운"),
    "胎": ("태", "가능성을 품은 기운"), "养": ("양", "보살핌 속에 자라는 기운"),
}

# 십신(일간 기준) — 이론적 의미에 맞춘 순한 풀이. 금전·건강 단정 없음.
TG = {
    "비견": dict(hz="比肩", sym="나란히 선 또 다른 나", kw="주체성",
               year="나와 똑같은 오행·음양의 기운이 한 해 동안 곁에 서는 흐름이에요. 내 생각과 방식대로 해 보고 싶은 마음이 커지고, 비슷한 결의 사람들과 어울릴 일이 많아지기 쉬운 해로 풀이해요.",
               month="내 페이스대로 밀고 가기 좋은 달. 혼자 다 하려 하기보다 동료와 나눠 보세요.",
               love="'나다움'을 지키고 싶은 마음이 커지는 흐름이에요. 상대와 나의 시간을 균형 있게 나누면 관계도 편안해져요.",
               work="스스로 기준을 세우고 주도하는 일이 잘 어울려요. 같은 목표를 가진 동료와 역할을 나누면 힘이 덜 들어요.",
               rel="비슷한 사람끼리 모이기 쉬운 해예요. 의견이 부딪힐 땐 누가 맞는지보다 서로의 방식을 인정하는 쪽이 오래 가요."),
    "겁재": dict(hz="劫財", sym="함께 겨루며 크는 동료", kw="자극과 협력",
               year="나와 같은 오행이지만 음양이 다른 기운이에요. 어깨를 나란히 하는 동료이자 선의의 경쟁자 같은 자리라, 자극을 받아 의욕이 오르고 사람들과 함께 움직일 일이 늘어나기 쉬운 해로 풀이해요.",
               month="주변에서 자극을 받기 쉬운 달. 비교보다 '함께 크기'에 초점을 두세요.",
               love="적극성이 살아나는 흐름이라 마음을 표현하기 좋아요. 지기 싫은 마음이 말다툼으로 번지지 않게, 이기는 대화보다 듣는 대화를 의식해 보세요.",
               work="팀 작업이나 협업에서 힘이 붙기 쉬운 흐름이에요. 역할과 공유 기준을 미리 정해 두면 서로 편해요.",
               rel="새로운 사람과 어울릴 기회가 많아질 수 있어요. 함께하는 일이 늘수록 약속과 경계를 분명히 해 두면 관계가 단단해져요."),
    "식신": dict(hz="食神", sym="즐겁게 만들어 내는 힘", kw="표현과 즐거움",
               year="내 기운이 자연스럽게 흘러나가는 자리예요. 하고 싶은 것을 즐겁게 표현하고, 꾸준히 무언가를 만들어 내고 싶어지는 해로 풀이해요.",
               month="좋아하는 것을 꾸준히 만들어 보기 좋은 달. 작은 루틴 하나를 시작해 보세요.",
               love="편안하고 따뜻한 표현이 잘 통하는 흐름이에요. 맛있는 것 함께 먹기, 취미 공유처럼 일상의 즐거움을 나눠 보세요.",
               work="전문성을 꾸준히 쌓고 결과물로 보여 주기 좋은 흐름이에요. 기록이나 포트폴리오로 정리해 두면 좋아요.",
               rel="여유 있고 너그러운 태도가 사람을 모으는 해예요. 챙겨 주는 만큼 나를 위한 시간도 남겨 두세요."),
    "상관": dict(hz="傷官", sym="재치와 새로운 시도", kw="새로운 시도",
               year="내 기운이 재치 있고 날카롭게 뻗어 나가는 자리예요. 기존 방식에 질문을 던지고 새로운 걸 시도해 보고 싶어지는 해로 풀이해요.",
               month="아이디어와 말솜씨가 살아나는 달. 좋은 말도 한 번 더 다듬어서 전해 보세요.",
               love="솔직하고 재치 있는 매력이 돋보이는 흐름이에요. 농담이나 직언이 상대에게 어떻게 들릴지 한 번만 생각하고 말하면 더 좋아요.",
               work="기획·창작·개선처럼 '새로 바꾸는 일'과 잘 어울려요. 규칙과 부딪힐 땐 근거를 차분히 정리해 제안해 보세요.",
               rel="표현력이 좋아지는 만큼 말의 온도가 중요해요. 칭찬은 크게, 아쉬운 점은 부드럽게 전해 보세요."),
    "편재": dict(hz="偏財", sym="넓게 움직이는 활동성", kw="활동 반경",
               year="내가 다루고 이끌어 가는 대상을 뜻하는 자리예요. 활동 범위가 넓어지고, 새로운 사람과 기회를 찾아 움직이고 싶어지는 해로 풀이해요.",
               month="새로운 사람·장소를 만나 보기 좋은 달. 일정은 넉넉하게 잡아 두세요.",
               love="새로운 만남이나 데이트 장소를 넓혀 보기 좋은 흐름이에요. 바쁜 일정 속에서도 연락의 리듬은 지켜 주세요.",
               work="여러 일을 함께 굴리거나 바깥 활동이 많은 일에 힘이 붙기 쉬워요. 우선순위 목록을 만들어 두면 흐름을 놓치지 않아요.",
               rel="인맥이 넓어지기 쉬운 해예요. 넓어진 만큼 가까운 사람에게 쓰는 시간도 따로 챙겨 보세요."),
    "정재": dict(hz="正財", sym="차곡차곡 쌓는 실속", kw="꼼꼼한 정리",
               year="내가 꼼꼼히 관리하고 지키는 대상을 뜻하는 자리예요. 계획을 세우고 하나씩 쌓아 가는 성실한 흐름의 해로 풀이해요.",
               month="계획표를 정리하고 생활 리듬을 다지기 좋은 달. 작은 목표를 하나씩 체크해 보세요.",
               love="안정감과 신뢰를 쌓기 좋은 흐름이에요. 거창한 이벤트보다 꾸준히 약속을 지키는 모습이 마음을 움직여요.",
               work="맡은 일을 차근차근 마무리하는 힘이 돋보이는 흐름이에요. 일정과 기록을 꼼꼼히 관리하면 강점이 잘 드러나요.",
               rel="믿을 수 있는 사람이라는 인상을 주기 좋은 해예요. 너무 계산적으로 보이지 않게 마음도 함께 표현해 주세요."),
    "편관": dict(hz="偏官", sym="나를 단련하는 도전", kw="도전과 단련",
               year="나를 단련시키는 자리예요. 도전 과제나 책임이 주어지고, 그 긴장감 속에서 단단해지는 해로 풀이해요.",
               month="해야 할 일이 몰리기 쉬운 달. 완벽보다 페이스 조절을 먼저 챙기세요.",
               love="분명한 태도와 강한 끌림이 눈에 띄는 흐름이에요. 상대의 속도를 존중하며 천천히 다가가 보세요.",
               work="부담스러운 과제도 해내면 실력이 되는 흐름이에요. 혼자 버티기보다 도움을 요청하는 것도 능력이에요.",
               rel="책임질 일이 늘 수 있어요. 할 수 있는 것과 어려운 것을 분명히 말해 두면 관계가 편해져요."),
    "정관": dict(hz="正官", sym="질서와 신뢰", kw="신뢰와 책임",
               year="나를 바르게 다듬어 주는 자리예요. 규칙과 약속, 책임 있는 역할을 통해 신뢰를 쌓아 가는 해로 풀이해요.",
               month="약속과 규칙을 지키는 모습이 빛나는 달. 맡은 역할을 차분히 해내 보세요.",
               love="진지하고 믿음직한 모습이 매력이 되는 흐름이에요. 서로의 기대를 대화로 맞춰 두면 관계가 더 안정돼요.",
               work="역할과 책임이 분명해지기 쉬운 흐름이에요. 기본과 절차를 지키는 태도가 강점이 돼요.",
               rel="예의와 배려가 돋보이는 해예요. 너무 틀에 맞추려 하지 말고 편한 모습도 보여 주세요."),
    "편인": dict(hz="偏印", sym="직관과 남다른 배움", kw="직관과 탐구",
               year="나에게 힘을 주는 자리 가운데 독특한 쪽이에요. 직관과 호기심이 커지고, 남다른 분야를 깊이 파고들고 싶어지는 해로 풀이해요.",
               month="관심 가는 분야를 깊게 파 보기 좋은 달. 혼자 생각할 시간을 확보하세요.",
               love="혼자만의 시간이 필요해질 수 있는 흐름이에요. 거리를 두고 싶을 땐 이유를 짧게라도 말해 주면 오해가 줄어요.",
               work="새로운 기술이나 자격 공부, 연구처럼 깊이 파는 일에 잘 어울려요. 떠오른 아이디어는 메모로 남겨 두세요.",
               rel="소수와 깊게 교류하고 싶어지는 해예요. 연락이 뜸해질 땐 가볍게 안부를 먼저 건네 보세요."),
    "정인": dict(hz="正印", sym="배움과 따뜻한 지지", kw="배움과 지지",
               year="나를 따뜻하게 받쳐 주는 자리예요. 배우고 정리하며, 주변의 도움과 조언을 받아들이기 좋은 해로 풀이해요.",
               month="배우고 정리하기 좋은 달. 조언을 구하면 생각이 정리돼요.",
               love="서로를 보살피고 받쳐 주는 따뜻함이 잘 드러나는 흐름이에요. 고마운 마음을 말로 표현해 보세요.",
               work="공부·자격·문서 정리처럼 기반을 다지는 일에 잘 어울려요. 선배나 멘토의 조언을 적극적으로 구해 보세요.",
               rel="받은 도움에 감사를 표현하면 관계가 깊어지는 해예요. 기대기만 하지 않도록 작은 보답도 챙겨 보세요."),
}
TG_CN = {"比肩": "비견", "劫财": "겁재", "食神": "식신", "伤官": "상관", "偏财": "편재",
         "正财": "정재", "七杀": "편관", "正官": "정관", "偏印": "편인", "正印": "정인"}

# 지지 관계표
LIUHE = {frozenset("子丑"): "土", frozenset("寅亥"): "木", frozenset("卯戌"): "火",
         frozenset("辰酉"): "金", frozenset("巳申"): "水", frozenset("午未"): "火"}
SANHE = {"申子辰": "水", "亥卯未": "木", "寅午戌": "火", "巳酉丑": "金"}  # 가운데 글자 = 왕지
CHONG = {frozenset(p) for p in ("子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥")}
XING = {frozenset(p) for p in ("寅巳", "巳申", "寅申", "丑戌", "戌未", "丑未", "子卯")}
ZIXING = set("辰午酉亥")
PO = {frozenset(p) for p in ("子酉", "丑辰", "寅亥", "卯午", "巳申", "未戌")}
HAI = {frozenset(p) for p in ("子未", "丑午", "寅巳", "卯辰", "申亥", "酉戌")}
GAN_HE = {frozenset("甲己"): "土", frozenset("乙庚"): "金", frozenset("丙辛"): "水", frozenset("丁壬"): "木", frozenset("戊癸"): "火"}
GAN_CHONG = {frozenset(p) for p in ("甲庚", "乙辛", "丙壬", "丁癸")}

REL_TXT = {  # 세운 지지 ↔ 일지
    "육합": dict(kw="연결", y="열두 지지 가운데 서로 짝을 이루는 육합이에요. 합은 서로 끌어당겨 묶이는 관계라, 가까운 관계와 생활 공간에 '연결'과 '협력'의 기운이 들어오는 해로 풀이해요.",
               m="일지와 합 — 사람·관계 쪽 연결이 자연스러운 달"),
    "반합": dict(kw="힘 모으기", y="삼합을 이루는 세 글자 가운데 두 글자가 만나는 반합이에요. 같은 방향으로 힘을 모으기 좋은 흐름으로 풀이해요.",
               m="일지와 반합 — 함께 힘을 모으기 좋은 달"),
    "충": dict(kw="변화와 움직임", y="정반대 자리에서 마주 보는 충이에요. 충은 '움직임'이라, 생활 리듬이나 환경에 변화를 주고 싶어지는 흐름으로 풀이해요. 미리 여유를 두고 움직이면 변화를 내 편으로 만들 수 있어요.",
              m="일지와 충 — 일정과 생활에 변화가 생기기 쉬우니 여유를 두세요"),
    "형": dict(kw="조율", y="형은 가까운 곳에서 조율할 일이 생기기 쉬운 관계로 봐요. 말과 약속을 한 번 더 점검하는 습관이 도움이 돼요.",
              m="일지와 형 — 말과 일정을 한 번 더 점검하는 달"),
    "자형": dict(kw="나를 돌보기", y="같은 글자가 겹치는 자형이에요. 스스로에게 엄격해지기 쉬운 관계로 봐요. 스스로를 몰아붙이지 않도록 쉬는 시간을 일정에 넣어 두세요.",
               m="같은 글자가 겹치는 자형 — 스스로를 몰아붙이지 않기"),
    "파": dict(kw="재정비", y="파는 기존의 틀을 한 번 깨고 다시 다듬는 관계로 봐요. 익숙한 방식을 점검하고 손보기 좋은 흐름이에요.",
              m="일지와 파 — 계획을 한 번 손보기 좋은 달"),
    "해": dict(kw="세심한 소통", y="해는 작은 오해가 생기기 쉬운 관계로 봐요. 중요한 이야기는 한 번 더 확인하는 대화가 도움이 돼요.",
              m="일지와 해 — 오해가 없도록 한 번 더 확인하는 대화를"),
}
EL_LIFE = {  # 오행의 전통 상징(색·활동) — 가볍게 참고
    "木": dict(color="초록", act="산책·식물 키우기·새로 배우기"),
    "火": dict(color="빨강·주황", act="햇볕 쬐기·공연 관람·표현 활동"),
    "土": dict(color="노랑·황토", act="정리 정돈·요리·손으로 만드는 취미"),
    "金": dict(color="흰색·은색", act="계획표 정리·미니멀 정리·규칙적인 운동 루틴"),
    "水": dict(color="검정·남색", act="물가 산책·독서·조용한 사색 시간"),
}


# 2026-11-24 리포트 v2 추가 데이터 — 전통 명리 개념에 맞춘 순한 풀이 (단정·불안 조장 없음)

STEM_NAME = {  # 천간 이름(읽는 법)
    "甲": "갑목", "乙": "을목", "丙": "병화", "丁": "정화", "戊": "무토",
    "己": "기토", "庚": "경금", "辛": "신금", "壬": "임수", "癸": "계수",
}
STEM_SHORT = {  # 입문 페이지용 한 줄
    "甲": "큰 나무 · 곧게 뻗는 추진력", "乙": "풀과 꽃 · 유연한 적응력", "丙": "태양 · 밝은 표현력",
    "丁": "촛불 · 섬세한 따뜻함", "戊": "큰 산 · 듬직한 포용력", "己": "논밭 · 세심한 실속",
    "庚": "바위·원석 · 시원한 결단력", "辛": "보석 · 정갈한 감각", "壬": "바다·강 · 넓은 시야", "癸": "비·이슬 · 조용한 공감력",
}
EL_SHORT = {"木": "나무 · 성장과 시작", "火": "불 · 열정과 표현", "土": "흙 · 안정과 중심",
            "金": "쇠 · 결단과 정리", "水": "물 · 지혜와 흐름"}

TG_GROUP = {"비견": "비겁", "겁재": "비겁", "식신": "식상", "상관": "식상", "편재": "재성", "정재": "재성",
            "편관": "관성", "정관": "관성", "편인": "인성", "정인": "인성"}
GROUP_INFO = {
    "비겁": dict(sym="나와 같은 기운", plain="나 · 친구 · 동료", work="독립적으로 내 일을 꾸리거나, 동료와 어깨를 나란히 하는 방식"),
    "식상": dict(sym="내가 표현하는 기운", plain="말 · 재능 · 결과물", work="말·글·기술로 무언가를 만들어 보여 주는 방식"),
    "재성": dict(sym="내가 다루는 기운", plain="돈 · 성과 · 현실 감각", work="숫자·성과·고객을 직접 다루며 결과를 내는 방식"),
    "관성": dict(sym="나를 다듬는 기운", plain="직장 · 규칙 · 책임", work="조직 안에서 역할과 책임을 맡아 신뢰를 쌓는 방식"),
    "인성": dict(sym="나를 돕는 기운", plain="배움 · 자격 · 도움", work="공부하고 자격을 갖춰 전문성으로 인정받는 방식"),
}

LOVE_STYLE = {
    "甲": "좋아하면 직진하는 타입이에요. 상대를 이끌고 지켜 주고 싶어 하지만, 내 방식이 맞다고 밀어붙이면 상대가 숨이 찰 수 있어요.",
    "乙": "상대에게 자연스럽게 맞춰 주는 다정한 타입이에요. 배려가 깊은 만큼 서운한 마음을 말 못 하고 쌓아 두지 않게 해 주세요.",
    "丙": "마음을 숨기지 못하고 밝게 표현하는 타입이에요. 설렘이 빨리 오는 만큼, 관계의 속도를 상대와 맞춰 가면 오래 가요.",
    "丁": "천천히 깊어지는 따뜻한 타입이에요. 작은 것까지 챙겨 주지만, 서운함을 속으로 오래 품지 않도록 그때그때 말해 보세요.",
    "戊": "듬직하게 곁을 지켜 주는 타입이에요. 표현이 담백해서 무심해 보일 수 있으니, 마음은 말로도 꼭 전해 주세요.",
    "己": "상대를 세심하게 돌보는 현실적인 타입이에요. 걱정이 많아질 땐 혼자 고민하지 말고 함께 이야기해 보세요.",
    "庚": "의리 있고 맺고 끊음이 분명한 타입이에요. 직설적인 말이 의도보다 세게 들릴 수 있으니 말의 온도만 살짝 낮춰 보세요.",
    "辛": "감각적이고 기준이 분명한 타입이에요. 작은 말에도 예민해질 수 있으니, 서운함은 기준이 아니라 마음으로 전해 보세요.",
    "壬": "자유롭고 너그러운 타입이에요. 생각이 넓은 만큼 속마음을 다 보여 주지 않을 때가 있으니, 가끔은 먼저 털어놓아 보세요.",
    "癸": "공감력이 깊고 섬세한 타입이에요. 상대의 감정까지 떠안기 쉬우니, 내 마음을 돌보는 시간도 꼭 챙겨 주세요.",
}
SPOUSE = {  # 일지 = 배우자 자리(가장 가까운 자리)
    "子": "조용히 깊은 대화를 나눌 수 있는 관계를 원해요. 감성을 알아주는 사람과 잘 맞아요.",
    "丑": "천천히 신뢰를 쌓는 관계를 원해요. 성실하고 한결같은 사람에게 마음이 가요.",
    "寅": "함께 새로운 걸 해 보는 활기찬 관계를 원해요. 같이 움직이는 사람과 잘 맞아요.",
    "卯": "다정한 표현과 분위기를 중요하게 여겨요. 소소한 애정 표현을 아끼지 않는 사람과 잘 맞아요.",
    "辰": "같은 꿈을 그리는 관계를 원해요. 미래 이야기를 함께 나눌 수 있는 사람과 잘 맞아요.",
    "巳": "겉은 차분해도 속은 뜨거운 관계를 원해요. 깊이 이해해 주는 사람에게 마음이 열려요.",
    "午": "감정 표현이 시원하고 열정적인 관계를 원해요. 함께 있을 때 에너지가 오르는 사람과 잘 맞아요.",
    "未": "따뜻하고 편안한 관계를 원해요. 은근한 고집도 웃으며 받아 주는 사람과 잘 맞아요.",
    "申": "재치 있고 같이 일을 해결하는 관계를 원해요. 대화가 잘 통하는 사람과 잘 맞아요.",
    "酉": "약속과 디테일을 지키는 깔끔한 관계를 원해요. 신뢰를 행동으로 보여 주는 사람과 잘 맞아요.",
    "戌": "의리와 책임감이 있는 관계를 원해요. 내 사람을 끝까지 챙기는 사람에게 마음이 가요.",
    "亥": "너그럽고 편안한 관계를 원해요. 있는 그대로를 받아 주는 사람과 잘 맞아요.",
}
MONEY_STYLE = {
    "甲": "목표를 정하면 크게 키우고 싶어 하는 편이에요. 시작은 시원하게, 관리는 규칙으로 정해 두면 좋아요.",
    "乙": "생활력이 좋고 알뜰하게 꾸려 가는 편이에요. 작은 지출이 모이지 않게 고정비만 한 번씩 점검해 보세요.",
    "丙": "쓸 때 시원하게 쓰는 편이에요. 기분 좋은 날 지출이 커지기 쉬우니 '즐기는 돈'을 미리 정해 두세요.",
    "丁": "필요한 곳에 꼼꼼히 쓰는 편이에요. 남을 챙기는 지출이 늘 수 있으니 나를 위한 저축도 함께 챙기세요.",
    "戊": "안정적으로 모아 두는 걸 좋아하는 편이에요. 너무 묶어 두기만 하기보다 목표별로 나눠 두면 좋아요.",
    "己": "실속을 챙기는 현실 감각이 좋아요. 걱정이 많아질 땐 숫자로 정리해 보면 마음이 편해져요.",
    "庚": "결정이 빠르고 과감한 편이에요. 큰 결정은 하루만 묵혀 두는 규칙을 만들어 보세요.",
    "辛": "가치 있는 것에 투자하는 감각이 있어요. 기준이 높은 만큼 '꼭 필요한가'를 한 번 더 물어보세요.",
    "壬": "흐름을 읽는 눈이 있고 여러 갈래로 움직이는 편이에요. 들어오고 나가는 흐름을 한곳에 기록해 두세요.",
    "癸": "조용히 차곡차곡 모으는 편이에요. 주변 부탁에 약해질 수 있으니 거절 기준을 정해 두세요.",
}
WORK_STYLE = {
    "甲": "앞장서서 방향을 정하고 일을 시작하는 데 강해요.",
    "乙": "사람 사이를 조율하고 상황에 맞춰 길을 찾는 데 강해요.",
    "丙": "분위기를 띄우고 사람들 앞에서 표현하는 데 강해요.",
    "丁": "한 가지를 깊게 파고들어 완성도를 높이는 데 강해요.",
    "戊": "큰 그림을 지키며 사람과 일을 묵직하게 받쳐 주는 데 강해요.",
    "己": "세심하게 관리하고 사람을 돌보며 키워 내는 데 강해요.",
    "庚": "빠르게 결단하고 문제를 정면으로 해결하는 데 강해요.",
    "辛": "디테일을 다듬고 기준에 맞게 완성하는 데 강해요.",
    "壬": "넓게 보고 흐름을 기획하며 여러 일을 연결하는 데 강해요.",
    "癸": "사람의 마음을 읽고 조용히 필요한 것을 채우는 데 강해요.",
}
WORK_FIELD = {  # 오행별 전통적 직업 상징 — 참고
    "木": "교육 · 출판 · 기획 · 디자인 · 식물·환경",
    "火": "미디어 · 마케팅 · 뷰티 · 공연 · 요식",
    "土": "부동산 · 상담 · 관리·운영 · 중개 · 농식품",
    "金": "금융 · 법·행정 · 기술·기계 · 의료·정밀",
    "水": "유통·무역 · 여행 · 연구 · 외국어 · 음료",
}
MONEY_YEAR = {  # 세운 십신 그룹별 돈 흐름
    "비겁": "나와 같은 기운이 들어오는 해라, 함께 쓰는 돈·경쟁·모임 지출이 늘기 쉬운 흐름으로 봐요. 돈을 빌려주거나 동업할 일은 조건을 문서로 남겨 두세요.",
    "식상": "재능과 결과물이 돈으로 이어지는 흐름으로 봐요(식상은 재성을 낳는 자리). 부업·포트폴리오처럼 '내가 만든 것'을 꾸준히 쌓아 보세요.",
    "재성": "돈과 성과를 직접 다루는 기운이 들어오는 해예요. 기회가 넓어지는 만큼 들어오고 나가는 흐름을 기록하면 실속이 남아요.",
    "관성": "역할과 책임이 커지면서 안정적인 수입 구조를 다지기 좋은 흐름으로 봐요. 큰 지출보다 고정 수입·계약 조건을 꼼꼼히 챙겨 보세요.",
    "인성": "배움·자격·준비에 쓰는 돈이 나중의 힘이 되는 흐름으로 봐요. 당장의 수익보다 나에게 투자하는 해로 생각해 보세요.",
}
WORK_YEAR = {
    "비겁": "동료·팀과 함께하거나 독립적으로 내 일을 꾸리기 좋은 흐름이에요.",
    "식상": "아이디어와 결과물을 보여 주기 좋은 흐름이에요. 새로 시도한 일이 이름을 알릴 기회가 될 수 있어요.",
    "재성": "성과와 숫자로 인정받기 좋은 흐름이에요. 일의 범위가 넓어질 수 있으니 우선순위를 정해 두세요.",
    "관성": "역할·직책·책임이 분명해지기 쉬운 흐름이에요. 조직 안에서 신뢰를 쌓기 좋은 해로 봐요.",
    "인성": "공부·자격·준비에 힘이 실리는 흐름이에요. 다음 단계를 위한 기반을 다지기 좋은 해로 봐요.",
}
PEOPLE_YEAR = {
    "비겁": "비슷한 목표를 가진 친구·동료", "식상": "취미를 나누는 사람·후배·함께 만드는 사람",
    "재성": "새로운 인맥·거래처·활동적인 사람", "관성": "믿을 수 있는 선배·윗사람·약속을 지키는 사람",
    "인성": "조언해 주는 멘토·스승·배움의 동료",
}
EL_LUCK = {  # 전통 상징 — 가볍게 참고
    "木": dict(num="3 · 8", dir="동쪽", taste="신맛", season="봄·아침"),
    "火": dict(num="2 · 7", dir="남쪽", taste="쓴맛", season="여름·한낮"),
    "土": dict(num="5 · 10", dir="중앙(집 가까이)", taste="단맛", season="환절기"),
    "金": dict(num="4 · 9", dir="서쪽", taste="매운맛", season="가을·저녁"),
    "水": dict(num="1 · 6", dir="북쪽", taste="짠맛", season="겨울·밤"),
}
EL_OVER = {  # 많을 때 줄이면 좋은 습관
    "木": "일을 한꺼번에 벌이기, 계획 없이 시작부터 하기",
    "火": "서두르기, 감정이 달아오른 채 결정하기, 늦은 밤까지 무리하기",
    "土": "고민만 하고 미루기, 한번 정한 생각에 고집 부리기",
    "金": "날 선 말, 완벽하지 않으면 시작하지 않기",
    "水": "생각만 많고 행동은 미루기, 혼자 걱정 끌어안기",
}
REL_MONTH_CARE = {"충": "생활·일정에 변화가 생기기 쉬운 달", "형": "말과 약속을 한 번 더 점검할 달",
                  "파": "계획을 손볼 일이 생기기 쉬운 달", "해": "작은 오해가 생기지 않게 확인이 필요한 달",
                  "자형": "스스로를 몰아붙이지 않도록 쉼표가 필요한 달"}
TG_NEAR = {  # 그해 십신별 가까이하면 좋은 것
    "비견": "같은 목표를 가진 동료, 함께하는 운동 모임", "겁재": "같이 성장하는 스터디·팀 프로젝트",
    "식신": "꾸준한 취미, 정성 들인 한 끼", "상관": "새로운 시도, 글·영상 같은 창작",
    "편재": "새로운 장소와 사람, 가벼운 여행", "정재": "가계부와 일정표, 작은 생활 루틴",
    "편관": "규칙적인 운동과 체력 관리", "정관": "약속과 계획표, 믿을 수 있는 윗사람",
    "편인": "혼자 몰입하는 공부 시간, 메모 습관", "정인": "독서와 자격 공부, 조언해 주는 멘토",
}
TG_AVOID = {  # 그해 십신별 줄이면 좋은 것 (순한 표현)
    "비견": "혼자 다 하려는 고집", "겁재": "남과 비교하기, 큰돈 빌려주기·보증",
    "식신": "늘어지는 생활 리듬, 야식과 과식", "상관": "날 선 직언, 감정적으로 규칙과 부딪히기",
    "편재": "무리한 확장, 즉흥적인 큰 지출", "정재": "지나친 계산, 걱정 때문에 기회 미루기",
    "편관": "과로와 혼자 버티기", "정관": "체면 때문에 거절 못 하기, 틀에 나를 끼워 맞추기",
    "편인": "생각만 하고 미루기, 연락 끊고 혼자 숨기", "정인": "준비만 하다 시작 못 하기, 지나친 의존",
}


def gz_kr(gz):
    return GAN_KR[gz[0]] + ZHI_KR[gz[1]]


def jo(word, cons, vow):
    w = str(word)
    ch = " "
    for c in reversed(w):
        if c in GAN_KR or c in ZHI_KR or 0xAC00 <= ord(c) < 0xAC00 + 11172 or c.isalnum():
            ch = GAN_KR.get(c) or ZHI_KR.get(c) or c
            break
    code = ord(ch[-1]) - 0xAC00
    return w + (cons if 0 <= code < 11172 and code % 28 else vow)


# ─────────────────────────── 만세력 계산 ───────────────────────────
def korea_dst(dt):
    spans = [(datetime.datetime(1987, 5, 10, 2), datetime.datetime(1987, 10, 11, 3)),
             (datetime.datetime(1988, 5, 8, 2), datetime.datetime(1988, 10, 9, 3))]
    return any(s <= dt < e for s, e in spans)


def day_formula(date):
    idx = (54 + (date - datetime.date(2000, 1, 1)).days) % 60
    return GAN[idx % 10] + ZHI[idx % 12]


def norm_job(j):
    j = str(j or "")
    if any(k in j for k in ("자영", "사업", "사장", "프리", "창업", "가게")):
        return "자영업"
    if any(k in j for k in ("학생", "취준", "취업", "준비", "수험")):
        return "학생·취준"
    if any(k in j for k in ("직장", "회사", "공무", "근무", "직원", "알바")):
        return "직장인"
    return None


def norm_status(s):
    s = str(s or "")
    if "기혼" in s or "결혼" in s or "배우자" in s:
        return "기혼"
    if "연애" in s or "커플" in s or "만나" in s:
        return "연애중"
    if "미혼" in s or "솔로" in s or "싱글" in s:
        return "미혼"
    return None


def calc_person(p):
    y, m, d = map(int, p["date"].split("-"))
    has_time = bool(p.get("time"))
    hh, mm = (map(int, p["time"].split(":")) if has_time else (12, 0))
    if p.get("calendar", "solar") == "lunar":
        lm = -m if p.get("leap") else m
        solar_in = Lunar.fromYmdHms(y, lm, d, hh, mm, 0).getSolar()
    else:
        solar_in = Solar.fromYmdHms(y, m, d, hh, mm, 0)
    dt = datetime.datetime(solar_in.getYear(), solar_in.getMonth(), solar_in.getDay(), hh, mm)
    notes = []
    if has_time:
        adj = 30
        if korea_dst(dt):
            adj += 60
            notes.append("서머타임 -60분")
        dt -= datetime.timedelta(minutes=adj)
        notes.insert(0, "동경 127.5° 보정 -30분")
    s = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, 0)
    lunar = s.getLunar()
    ec = lunar.getEightChar()
    ec.setSect(1)
    pillars = {"year": ec.getYear(), "month": ec.getMonth(), "day": ec.getDay(),
               "time": ec.getTime() if has_time else None}
    # 검증 ① 일주 공식
    base = dt.date() + (datetime.timedelta(days=1) if (has_time and dt.hour >= 23) else datetime.timedelta(0))
    f = day_formula(base)
    assert f == pillars["day"], f"일주 불일치: lunar={pillars['day']} formula={f}"
    # 검증 ② Solar ↔ Lunar 왕복
    back = Lunar.fromYmdHms(lunar.getYear(), lunar.getMonth(), lunar.getDay(), dt.hour, dt.minute, 0)
    assert back.getSolar().toYmd() == s.toYmd(), "양력↔음력 왕복 불일치"
    bec = back.getEightChar(); bec.setSect(1)
    assert (bec.getYear(), bec.getMonth(), bec.getDay()) == (pillars["year"], pillars["month"], pillars["day"])
    chars = []
    for k in ("year", "month", "day", "time"):
        if pillars[k]:
            chars += [GAN_EL[pillars[k][0]], ZHI_EL[pillars[k][1]]]
    counts = {e: chars.count(e) for e in EL_ORDER}
    lun_str = f"음력 {lunar.getYear()}.{abs(lunar.getMonth())}.{lunar.getDay()}" + (" (윤달)" if lunar.getMonth() < 0 else "")
    sol_str = f"양력 {solar_in.getYear()}.{solar_in.getMonth()}.{solar_in.getDay()}"
    name = p.get("name") or ""
    return dict(dt=dt, ec=ec, job=norm_job(p.get("job")), status=norm_status(p.get("status")),
                interests=p.get("interests") or [], name=name, nick=f"{name}님" if name else "당신", gender=p.get("gender", ""),
                has_time=has_time, time=p.get("time"), pillars=pillars, day=pillars["day"],
                stem=pillars["day"][0], branch=pillars["day"][1], counts=counts, total=len(chars),
                solar=sol_str, lunar=lun_str, dishi=ec.getDayDiShi(), adj_notes=notes,
                check=f"일주 공식 교차검증 {f} ✓ · 양력↔음력 왕복 ✓")


def to_kst(js):
    """lunar-python 절기 시각(베이징, UTC+8) → 한국 표준시(UTC+9)"""
    s = js.getSolar()
    return datetime.datetime(s.getYear(), s.getMonth(), s.getDay(), s.getHour(), s.getMinute(), s.getSecond()) + datetime.timedelta(hours=1)


JIE_KR = {"立春": "입춘", "惊蛰": "경칩", "清明": "청명", "立夏": "입하", "芒种": "망종", "小暑": "소서",
          "立秋": "입추", "白露": "백로", "寒露": "한로", "立冬": "입동", "大雪": "대설", "小寒": "소한"}


def calc_year(year=TARGET_YEAR):
    """세운 + 12개월 월건(절기 기준) 계산 및 검증"""
    # 입춘 찾기
    lc = Solar.fromYmd(year, 1, 25).getLunar().getNextJie()
    assert lc.getName() == "立春"
    lichun = to_kst(lc)
    # 입춘 전날/당일(입춘 이후)의 년주 확인
    before = Solar.fromYmdHms(year, 2, lc.getSolar().getDay() - 1, 12, 0, 0).getLunar().getEightChar().getYear()
    after_s = lc.getSolar()
    after = Solar.fromYmdHms(after_s.getYear(), after_s.getMonth(), after_s.getDay() + 1, 12, 0, 0).getLunar().getEightChar().getYear()
    assert after == TARGET_GZ, f"{year} 세운이 {TARGET_GZ}가 아님: {after}"
    # 60갑자 공식 교차: (year-4) % 60
    i60 = (year - 4) % 60
    assert GAN[i60 % 10] + ZHI[i60 % 12] == after
    nayin = LunarUtil.NAYIN[after]
    # 월건: 입춘부터 12개 절
    months = []
    cur = lc
    yg = GAN.index(after[0])
    first_stem = {0: 2, 5: 2, 1: 4, 6: 4, 2: 6, 7: 6, 3: 8, 8: 8, 4: 0, 9: 0}[yg]  # 오호둔: 甲己→丙寅, 乙庚→戊寅, 丙辛→庚寅, 丁壬→壬寅, 戊癸→甲寅
    for k in range(12):
        s = cur.getSolar()
        probe = Solar.fromYmdHms(s.getYear(), s.getMonth(), s.getDay(), s.getHour(), s.getMinute(), s.getSecond()).next(1)  # 절입 다음 날 정오
        probe = Solar.fromYmdHms(probe.getYear(), probe.getMonth(), probe.getDay(), 12, 0, 0)
        mgz = probe.getLunar().getEightChar().getMonth()
        expect = GAN[(first_stem + k) % 10] + ZHI[(2 + k) % 12]
        assert mgz == expect, f"월건 불일치 {mgz} vs {expect}"
        start = to_kst(cur)
        nxt = Solar.fromYmdHms(s.getYear(), s.getMonth(), s.getDay(), 12, 0, 0).next(3).getLunar().getNextJie()
        months.append(dict(gz=mgz, jie=JIE_KR[cur.getName()] if cur.getName() in JIE_KR else cur.getName(),
                           start=start, end=to_kst(nxt) - datetime.timedelta(days=1)))
        cur = nxt
    assert months[-1]["gz"][1] == "丑" and to_kst(cur).year == year + 1  # 마지막은 다음 해 입춘 전
    next_lichun = to_kst(cur)
    return dict(gz=after, prev=before, lichun=lichun, next_lichun=next_lichun, nayin=nayin, months=months,
                hide=LunarUtil.ZHI_HIDE_GAN[after[1]], order=i60 + 1)


# ─────────────────────────── 관계 판정 ───────────────────────────
def element_rel(ea, eb):
    if ea == eb:
        return "same"
    if SHENG[ea] == eb:
        return "a_sheng_b"
    if SHENG[eb] == ea:
        return "b_sheng_a"
    if KE[ea] == eb:
        return "a_ke_b"
    return "b_ke_a"


def ten_god(me, other):
    em, eo = GAN_EL[me], GAN_EL[other]
    same = GAN_YY[me] == GAN_YY[other]
    r = element_rel(em, eo)
    tg = {"same": "비견" if same else "겁재", "a_sheng_b": "식신" if same else "상관",
          "b_sheng_a": "편인" if same else "정인", "a_ke_b": "편재" if same else "정재",
          "b_ke_a": "편관" if same else "정관"}[r]
    lib = TG_CN.get(LunarUtil.SHI_SHEN.get(me + other))
    assert lib is None or lib == tg, f"십신 교차검증 실패 {me}{other}: {tg} vs {lib}"
    return tg


def branch_rels(a, b):
    """a, b 두 지지 사이에 실제로 해당하는 관계만 반환: [(종류, 설명)]"""
    out = []
    pair = frozenset((a, b))
    if a == b:
        if a in ZIXING:
            out.append(("자형", f"{a}{a} 자형"))
        return out
    if pair in LIUHE:
        out.append(("육합", f"{a}{b} 육합 → {LIUHE[pair]}"))
    for trio, el in SANHE.items():
        if a in trio and b in trio and trio[1] in (a, b):  # 왕지 포함 반합만
            out.append(("반합", f"{trio} 삼합 중 반합 → {el}"))
    if pair in CHONG:
        out.append(("충", f"{a}{b} 충"))
    if pair in XING:
        out.append(("형", f"{a}{b} 형"))
    if pair in PO:
        out.append(("파", f"{a}{b} 파"))
    if pair in HAI:
        out.append(("해", f"{a}{b} 해"))
    return out


def stem_rels(a, b):
    pair = frozenset((a, b))
    out = []
    if pair in GAN_HE:
        out.append(("천간합", f"{a}{b} 합 → {GAN_HE[pair]}"))
    if pair in GAN_CHONG:
        out.append(("천간충", f"{a}{b} 충"))
    return out


# ─────────────────────────── HTML ───────────────────────────
CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; margin: 0; padding: 0; }
:root { --navy:#0d1630; --gold:#d4b06a; --gold2:#f0d9a6; --ink:#ece7da; --mute:#a3abbf; --line:rgba(212,176,106,.35); }
body { font-family: 'Noto Sans CJK KR', sans-serif; color: var(--ink); background: var(--navy); -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.page { width: 210mm; height: 297mm; position: relative; overflow: hidden; page-break-after: always;
        background: radial-gradient(120% 80% at 50% 0%, #1b2a55 0%, var(--navy) 60%, #0a1126 100%); padding: 22mm 20mm 20mm; }
.page:last-child { page-break-after: auto; }
.wm { position: absolute; right: -8mm; bottom: -14mm; font-family: 'Noto Serif CJK KR', serif; font-weight: 900; font-size: 150mm; line-height: 1; color: var(--gold); opacity: .055; }
.hdr { position: absolute; top: 10mm; left: 20mm; right: 20mm; display: flex; justify-content: space-between; font-size: 8.5pt; color: var(--mute); letter-spacing: .08em; }
.ftr { position: absolute; bottom: 10mm; left: 20mm; right: 20mm; display: flex; justify-content: space-between; font-size: 8pt; color: var(--mute); }
.serif { font-family: 'Noto Serif CJK KR', serif; }
.eyebrow { color: var(--gold); font-size: 9.5pt; letter-spacing: .25em; margin-bottom: 4mm; }
h1 { font-family: 'Noto Serif CJK KR', serif; font-weight: 700; font-size: 23pt; color: var(--gold2); margin-bottom: 3mm; line-height: 1.3; }
h2 { font-family: 'Noto Serif CJK KR', serif; font-size: 13pt; color: var(--gold); margin: 6mm 0 3mm; }
p, li { font-size: 10.8pt; line-height: 1.85; }
.lead { color: var(--mute); font-size: 10pt; margin-bottom: 6mm; }
.rule { height: 1px; background: linear-gradient(90deg, var(--gold), transparent); margin: 4mm 0 5mm; }
.card { background: rgba(255,255,255,.035); border: 1px solid var(--line); border-radius: 3mm; padding: 5.5mm 7mm; margin-bottom: 4.5mm; }
.chip { display: inline-block; border: 1px solid var(--line); color: var(--gold2); border-radius: 10mm; padding: .6mm 3.2mm; font-size: 9pt; margin: 0 1.5mm 1.5mm 0; }
.small { font-size: 8.8pt; color: var(--mute); line-height: 1.7; }
.k { color: var(--gold); font-size: 9.5pt; letter-spacing: .1em; margin-bottom: 2mm; display: block; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 5mm; }
.three { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4mm; }
/* cover */
.cover { display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; }
.cover .brand { position: absolute; top: 22mm; letter-spacing: .4em; color: var(--gold); font-size: 10pt; }
.cover .year { font-family: 'Noto Serif CJK KR', serif; font-size: 13pt; letter-spacing: .5em; color: var(--gold); }
.cover .big { font-family: 'Noto Serif CJK KR', serif; font-size: 92pt; font-weight: 700; color: var(--gold2); line-height: 1.1; letter-spacing: .08em; margin: 2mm 0; }
.cover .title { font-family: 'Noto Serif CJK KR', serif; font-size: 25pt; color: var(--gold2); font-weight: 700; margin: 4mm 0 3mm; }
.cover .sub { color: var(--mute); font-size: 10.5pt; letter-spacing: .1em; }
.cover .me { margin-top: 16mm; border: 1px solid var(--line); border-radius: 30mm; padding: 3mm 9mm; color: var(--ink); font-size: 11pt; }
.cover .me b { font-family: 'Noto Serif CJK KR', serif; color: var(--gold2); font-size: 14pt; margin: 0 1.5mm; }
.ring { width: 130mm; height: 130mm; border: 1px solid var(--line); border-radius: 50%; position: absolute; top: 50%; left: 50%; transform: translate(-50%,-56%); }
.ring.r2 { width: 112mm; height: 112mm; opacity: .45; }
.cover-foot { position: absolute; bottom: 22mm; left: 0; right: 0; text-align: center; font-size: 9pt; color: var(--mute); line-height: 1.9; }
/* pillar table */
table.pl { width: 100%; border-collapse: separate; border-spacing: 2mm 0; margin-bottom: 2mm; }
table.pl th { font-size: 9pt; color: var(--mute); font-weight: 400; padding-bottom: 2mm; }
table.pl td { text-align: center; background: rgba(255,255,255,.035); border: 1px solid var(--line); padding: 3mm 0 2.4mm; }
table.pl tr.g td { border-radius: 2mm 2mm 0 0; border-bottom: none; }
table.pl tr.z td { border-radius: 0 0 2mm 2mm; border-top: 1px dashed rgba(212,176,106,.2); }
table.pl td.day { background: rgba(212,176,106,.12); border-color: var(--gold); }
.hz1 { font-family: 'Noto Serif CJK KR', serif; font-size: 28pt; font-weight: 700; line-height: 1.15; }
.kr1 { font-size: 8.5pt; color: var(--mute); }
.dot { display: inline-block; width: 2.2mm; height: 2.2mm; border-radius: 50%; margin-right: 1mm; vertical-align: middle; }
.person-head { display: flex; justify-content: space-between; align-items: baseline; margin: 2mm 0 4mm; }
.person-head b { font-family: 'Noto Serif CJK KR', serif; font-size: 13pt; color: var(--gold2); }
.person-head span { font-size: 9pt; color: var(--mute); }
.big-ilju { display: flex; align-items: center; gap: 8mm; margin: 4mm 0 6mm; }
.big-ilju .hz { font-family: 'Noto Serif CJK KR', serif; font-size: 58pt; font-weight: 700; color: var(--gold2); line-height: 1; }
.big-ilju .meta { font-size: 10pt; color: var(--mute); line-height: 1.8; }
.chk { display: grid; grid-template-columns: repeat(3, 1fr); gap: 3mm; margin: 3mm 0 6mm; }
.chk.c2 { grid-template-columns: 1fr 1fr; }
.chk div { border: 1px solid rgba(255,255,255,.12); border-radius: 2mm; padding: 3mm 4mm; font-size: 10pt; color: var(--mute); display: flex; justify-content: space-between; }
.chk div.on { border-color: var(--gold); color: var(--gold2); background: rgba(212,176,106,.1); }
.vs { display: flex; justify-content: center; align-items: center; gap: 12mm; margin: 5mm 0 4mm; }
.vs .c { text-align: center; }
.vs .c .hz { font-family: 'Noto Serif CJK KR', serif; font-size: 46pt; color: var(--gold2); font-weight: 700; line-height: 1.1; }
.vs .c .s { font-size: 9pt; color: var(--mute); }
.vs .arrow { font-size: 11pt; color: var(--gold); text-align: center; line-height: 1.6; }
.pt { display: flex; gap: 5mm; margin-bottom: 5mm; }
.pt .n { font-family: 'Noto Serif CJK KR', serif; font-size: 20pt; color: var(--gold); width: 9mm; flex: none; line-height: 1.2; }
.pt b { display: block; font-family: 'Noto Serif CJK KR', serif; font-size: 13pt; color: var(--gold2); margin-bottom: 1mm; }
.pt p { font-size: 10.6pt; line-height: 1.8; }
.tg { display: grid; grid-template-columns: repeat(5, 1fr); gap: 2mm; margin-top: 2mm; }
.tg div { border: 1px solid rgba(255,255,255,.1); border-radius: 2mm; text-align: center; padding: 2mm 0; font-size: 9pt; color: var(--mute); }
.tg div b { display: block; font-family: 'Noto Serif CJK KR', serif; font-size: 14pt; color: var(--ink); }
.tg div.on { border-color: var(--gold); background: rgba(212,176,106,.14); color: var(--gold2); }
.tg div.on b { color: var(--gold2); }
dl.gl { display: grid; grid-template-columns: 34mm 1fr; row-gap: 2.2mm; font-size: 9.6pt; line-height: 1.6; }
dl.gl dt { color: var(--gold2); font-family: 'Noto Serif CJK KR', serif; }
dl.gl dd { color: var(--ink); }
table.x { width: 100%; border-collapse: collapse; font-size: 9.5pt; }
table.x td, table.x th { padding: 2mm 2mm; border-bottom: 1px solid rgba(255,255,255,.08); text-align: left; }
table.x th { color: var(--mute); font-weight: 400; font-size: 8.8pt; }
.notice { border: 1px solid var(--gold); border-radius: 3mm; padding: 6mm 7mm; background: rgba(212,176,106,.06); }
.strip { display: grid; grid-template-columns: repeat(6, 1fr); gap: 2mm; }
.strip div { text-align: center; border: 1px solid rgba(255,255,255,.1); border-radius: 2mm; padding: 2mm 0 1.5mm; }
.strip b { display: block; font-family: 'Noto Serif CJK KR', serif; font-size: 15pt; color: var(--gold2); }
.strip span { font-size: 8pt; color: var(--mute); }
.mon { display: grid; grid-template-columns: 30mm 1fr; gap: 5mm; border: 1px solid var(--line); border-radius: 3mm; padding: 4mm 5mm; margin-bottom: 3.6mm; background: rgba(255,255,255,.03); }
.mon .l { text-align: center; border-right: 1px solid rgba(212,176,106,.2); padding-right: 4mm; }
.mon .l .m { font-size: 9.5pt; color: var(--gold); letter-spacing: .1em; }
.mon .l .g { font-family: 'Noto Serif CJK KR', serif; font-size: 25pt; color: var(--gold2); font-weight: 700; line-height: 1.2; }
.mon .l .d { font-size: 7.8pt; color: var(--mute); }
.mon .r .tags { margin-bottom: 1.2mm; }
.mon .r .tags .chip { font-size: 8.3pt; margin-bottom: 1mm; }
.mon .r .chip.rel { border-color: var(--gold); background: rgba(212,176,106,.12); }
.mon .r p { font-size: 9.8pt; line-height: 1.65; }
.mon .r b.kw { font-family: 'Noto Serif CJK KR', serif; color: var(--gold2); font-size: 11.5pt; margin-right: 2mm; }
/* v2 */
.g10 { display: grid; grid-template-columns: repeat(5, 1fr); gap: 2mm; }
.g10.z { grid-template-columns: repeat(6, 1fr); }
.g10 div { border: 1px solid rgba(255,255,255,.1); border-radius: 2mm; text-align: center; padding: 1.8mm 1mm 1.4mm; }
.g10 b { display: block; font-family: 'Noto Serif CJK KR', serif; font-size: 16pt; line-height: 1.2; }
.g10 .r { display: block; font-size: 8.8pt; color: var(--gold2); }
.g10 .s { display: block; font-size: 7.4pt; color: var(--mute); line-height: 1.4; }
.g10 div.on { border-color: var(--gold); background: rgba(212,176,106,.16); }
.cyc { display: flex; align-items: center; justify-content: space-between; margin: 1mm 0 2mm; }
.cyc .e { text-align: center; width: 26mm; }
.cyc .e b { display: block; font-family: 'Noto Serif CJK KR', serif; font-size: 17pt; line-height: 1.2; }
.cyc .e span { font-size: 7.6pt; color: var(--mute); }
.cyc .a { color: var(--gold); font-size: 10pt; }
.mchips .chip { font-size: 9pt; }
.card.plus { border-color: var(--gold); background: rgba(212,176,106,.07); }
.card.minus { border-color: rgba(255,255,255,.16); }
.luck { display: grid; grid-template-columns: repeat(3, 1fr); gap: 2.5mm; margin-top: 1mm; }
.luck div { border: 1px solid rgba(255,255,255,.1); border-radius: 2mm; padding: 2mm 3mm; }
.luck span { display: block; font-size: 7.8pt; color: var(--mute); }
.luck b { font-size: 10pt; color: var(--gold2); font-weight: 500; }
.mate { display: grid; grid-template-columns: 1fr 1fr; gap: 4mm; }
.mate .big { font-family: 'Noto Serif CJK KR', serif; font-size: 16pt; color: var(--gold2); font-weight: 700; line-height: 1.3; }
p.tip { font-size: 10.2pt; line-height: 1.75; }
/* v3 */
.rate { display: grid; grid-template-columns: 30mm 1fr 17mm; align-items: center; gap: 3mm; margin-bottom: 2.4mm; }
.rate .n { font-size: 9.6pt; color: var(--ink); }
.rate .bar { display: grid; grid-template-columns: repeat(5, 1fr); gap: 1mm; }
.rate .bar i { height: 3.2mm; border-radius: 1mm; background: rgba(255,255,255,.08); }
.rate .bar i.on { background: var(--gold); }
.rate .bar i.on.lo { background: #b9776c; }
.rate .t { font-size: 9pt; color: var(--gold2); text-align: right; }
.rate .w { grid-column: 2 / 4; font-size: 8.2pt; color: var(--mute); margin-top: -1.6mm; }
.cal { display: grid; grid-template-columns: repeat(3, 1fr); gap: 2.6mm; }
.cal > div { border: 1px solid rgba(255,255,255,.12); border-radius: 2.4mm; padding: 2.6mm 3mm 2.2mm; min-height: 37mm; }
.cal > div.good { border-color: var(--gold); background: rgba(212,176,106,.08); }
.cal > div.care { border-color: rgba(185,119,108,.7); background: rgba(185,119,108,.06); }
.cal .hd { display: flex; justify-content: space-between; align-items: baseline; }
.cal .hd b { font-size: 10.5pt; color: var(--gold2); }
.cal .hd span { font-family: 'Noto Serif CJK KR', serif; font-size: 12pt; color: var(--ink); }
.cal .lv { font-size: 8.4pt; margin: 1mm 0 1.2mm; color: var(--mute); }
.cal .lv em { font-style: normal; color: var(--gold2); }
.cal .lv em.c { color: #d39a90; }
.cal p { font-size: 8.4pt; line-height: 1.5; color: var(--ink); }
.tl { display: grid; grid-template-columns: 1fr 1.25fr 1fr; gap: 3mm; margin: 2mm 0 4mm; }
.tl > div { border: 1px solid rgba(255,255,255,.12); border-radius: 2.4mm; padding: 3mm 3.5mm; text-align: center; }
.tl > div.now { border-color: var(--gold); background: rgba(212,176,106,.1); }
.tl .y { font-size: 8.4pt; color: var(--mute); }
.tl .g { font-family: 'Noto Serif CJK KR', serif; font-size: 22pt; color: var(--gold2); line-height: 1.25; }
.tl .p { font-size: 9.6pt; color: var(--gold); }
.tl .d { font-size: 8.4pt; color: var(--ink); line-height: 1.5; margin-top: 1mm; }
.gauge { height: 3.4mm; border-radius: 2mm; background: rgba(255,255,255,.08); position: relative; margin: 2mm 0 1.5mm; }
.gauge i { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 2mm; background: linear-gradient(90deg, #8a7448, var(--gold)); }
.gauge b { position: absolute; top: -1mm; width: .6mm; height: 5.4mm; background: var(--ink); opacity: .5; }
.sum { display: grid; grid-template-columns: 26mm 1fr; row-gap: 2.6mm; column-gap: 3mm; }
.sum dt { color: var(--gold); font-size: 9.6pt; }
.sum dd { font-size: 10.2pt; line-height: 1.6; }
"""


def esc(s):
    return html.escape(str(s))


def page(inner, num=None, wm="", cls=""):
    hdr = f'<div class="hdr"><span>60일주 도감 · {TARGET_YEAR} 정미년 신년운세 리포트</span><span>@ilju_dogam</span></div>' if num else ""
    ftr = f'<div class="ftr"><span>재미와 참고를 위한 콘텐츠</span><span>{num:02d}</span></div>' if num else ""
    w = f'<div class="wm">{esc(wm)}</div>' if wm else ""
    return f'<section class="page {cls}">{w}{hdr}{inner}{ftr}</section>'


def pillar_table(p):
    cols = [("시주", "time"), ("일주", "day"), ("월주", "month"), ("년주", "year")]
    th = "".join(f"<th>{c}</th>" for c, _ in cols)
    g = z = ""
    for _, k in cols:
        gz = p["pillars"][k]
        cl = ' class="day"' if k == "day" else ""
        if gz:
            g += (f'<td{cl}><div class="hz1" style="color:{EL_COLOR[GAN_EL[gz[0]]]}">{gz[0]}</div>'
                  f'<div class="kr1">{GAN_KR[gz[0]]} · {GAN_YY[gz[0]]}{GAN_EL[gz[0]]}</div></td>')
            z += (f'<td{cl}><div class="hz1" style="color:{EL_COLOR[ZHI_EL[gz[1]]]}">{gz[1]}</div>'
                  f'<div class="kr1">{ZHI_KR[gz[1]]} · {BRANCH[gz[1]]["animal"]} · {ZHI_EL[gz[1]]}</div></td>')
        else:
            g += f'<td{cl}><div class="hz1" style="color:#4a5577">–</div><div class="kr1">시간 미상</div></td>'
            z += f'<td{cl}><div class="hz1" style="color:#4a5577">–</div><div class="kr1">&nbsp;</div></td>'
    return f'<table class="pl"><tr>{th}</tr><tr class="g">{g}</tr><tr class="z">{z}</tr></table>'


def bar_chart(base, plus):
    """원국 오행(금색) + 세운이 더하는 오행(밝은 테두리) 막대"""
    W, H, pad_l, pad_b, top = 480, 210, 30, 42, 22
    tot = {e: base[e] + plus.get(e, 0) for e in EL_ORDER}
    mx = max(4, max(tot.values()))
    gw = (W - pad_l) / 5
    bw = 40
    o = [f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg" font-family="Noto Sans CJK KR">']
    for i in range(mx + 1):
        y = H - pad_b - (H - pad_b - top) * i / mx
        o.append(f'<line x1="{pad_l}" x2="{W}" y1="{y:.1f}" y2="{y:.1f}" stroke="rgba(255,255,255,.08)"/>')
        o.append(f'<text x="{pad_l-8}" y="{y+3:.1f}" fill="#a3abbf" font-size="9" text-anchor="end">{i}</text>')
    unit = (H - pad_b - top) / mx
    for j, e in enumerate(EL_ORDER):
        cx = pad_l + gw * j + gw / 2
        x = cx - bw / 2
        y0 = H - pad_b
        hb = unit * base[e]
        if base[e]:
            o.append(f'<rect x="{x:.1f}" y="{y0-hb:.1f}" width="{bw}" height="{hb:.1f}" rx="3" fill="{EL_COLOR[e]}"/>')
        if plus.get(e):
            hp = unit * plus[e]
            o.append(f'<rect x="{x+1:.1f}" y="{y0-hb-hp+1:.1f}" width="{bw-2}" height="{hp-2:.1f}" rx="3" fill="rgba(240,217,166,.12)" stroke="#f0d9a6" stroke-width="1.6" stroke-dasharray="4 3"/>')
        o.append(f'<text x="{cx:.1f}" y="{y0-unit*tot[e]-6:.1f}" fill="#f0d9a6" font-size="12" font-weight="700" text-anchor="middle">{base[e]}{"+" + str(plus[e]) if plus.get(e) else ""}</text>')
        o.append(f'<text x="{cx:.1f}" y="{H-pad_b+19}" fill="{EL_COLOR[e]}" font-size="15" font-family="Noto Serif CJK KR" font-weight="700" text-anchor="middle">{e}</text>')
        o.append(f'<text x="{cx:.1f}" y="{H-pad_b+33}" fill="#a3abbf" font-size="9" text-anchor="middle">{EL_KR[e]}</text>')
    o.append(f'<rect x="{W-200}" y="0" width="10" height="10" rx="2" fill="#c9a76a"/><text x="{W-186}" y="9" fill="#ece7da" font-size="10">내 원국</text>')
    o.append(f'<rect x="{W-120}" y="0" width="10" height="10" rx="2" fill="none" stroke="#f0d9a6" stroke-dasharray="3 2"/><text x="{W-106}" y="9" fill="#ece7da" font-size="10">{TARGET_GZ}년이 더하는 기운</text>')
    o.append("</svg>")
    return "".join(o)


def inner_rel(stem, branch):
    es, eb = GAN_EL[stem], ZHI_EL[branch]
    S, B = f"{es}({EL_KR[es]})", f"{eb}({EL_KR[eb]})"
    return {
        "same": f"천간과 지지가 같은 {S} 기운이에요. 자기 색이 뚜렷하고 본래 모습을 그대로 드러내는 구조예요.",
        "a_sheng_b": f"천간 {jo(S,'이','가')} 지지 {jo(B,'을','를')} 생(生)해 주는 구조예요. 위의 기운이 아래로 흘러 내려가 힘을 실어 줘요.",
        "b_sheng_a": f"지지 {jo(B,'이','가')} 천간 {jo(S,'을','를')} 생(生)해 주는 구조예요. 아래의 기운이 위를 든든하게 받쳐 줘요.",
        "a_ke_b": f"천간 {jo(S,'이','가')} 지지 {jo(B,'을','를')} 극(克)하는 구조예요. 위의 기운이 아래를 다듬으며 이끌어 가요.",
        "b_ke_a": f"지지 {jo(B,'이','가')} 천간 {jo(S,'을','를')} 극(克)하는 구조예요. 아래에서 오는 자극으로 단단해지는 결이에요.",
    }[element_rel(es, eb)]


def keywords(p, Y):
    """오행 균형·십신·지지관계로 한 해 키워드 3개"""
    tg = ten_god(p["stem"], Y["gz"][0])
    rels = branch_rels(p["branch"], Y["gz"][1])
    plus = {GAN_EL[Y["gz"][0]]: 0, ZHI_EL[Y["gz"][1]]: 0}
    plus[GAN_EL[Y["gz"][0]]] += 1
    plus[ZHI_EL[Y["gz"][1]]] += 1
    k1 = (TG[tg]["kw"], f"세운 천간 {jo(Y['gz'][0],'은','는')} 내 일간 {p['stem']}에게 {tg}({TG[tg]['hz']}) — {TG[tg]['sym']}. {TG[tg]['month'].split('. ')[-1]}")
    if rels:
        main = rels[0][0]
        k2 = (REL_TXT[main]["kw"], f"세운 지지 {jo(Y['gz'][1],'과','와')} 내 일지 {jo(p['branch'],'은','는')} {', '.join(r[1] for r in rels)}. {REL_TXT[main]['y'].split('. ')[0]}.")
    else:
        k2 = ("내 리듬", f"세운 지지 {jo(Y['gz'][1],'과','와')} 내 일지 {p['branch']} 사이에 합·충·형·파·해가 없어요. 정해진 끌림이나 부딪힘 없이 내 리듬대로 한 해를 꾸려 가기 좋은 흐름이에요.")
    c = p["counts"]
    top_n = max(c.values())
    tops = [e for e in EL_ORDER if c[e] == top_n]
    adds = [e for e in plus if plus[e]]
    lacking = [e for e in EL_ORDER if c[e] + plus.get(e, 0) == 0]
    fill = [e for e in adds if c[e] == 0]
    over = [e for e in adds if e in tops and top_n >= 3]
    lack_txt = (f" 한 해 동안에도 {'·'.join(e + EL_KR[e] for e in lacking)} 기운은 비어 있으니, "
                f"{' / '.join(EL_LIFE[e]['act'] for e in lacking)} 같은 활동으로 가볍게 채워 보세요.") if lacking else ""
    if fill:
        k3 = ("채움", f"원국에 없던 {'·'.join(e + EL_KR[e] for e in fill)} 기운이 {Y['gz']}년에 들어와요. 평소 낯설던 영역에 관심이 생기기 쉬운 해예요." + lack_txt)
    elif over:
        k3 = ("완급 조절", f"원국에 이미 많은 {'·'.join(e + EL_KR[e] for e in over)} 기운이 {Y['gz']}년에 더해져요. 장점이 더 선명해지는 만큼 속도를 고르는 쉼표가 필요해요." + lack_txt)
    else:
        k3 = ("균형", f"{Y['gz']}년이 더하는 {'·'.join(e + EL_KR[e] for e in adds)} 기운이 원국과 무난하게 어우러져요." + lack_txt)
    return [k1, k2, k3], plus, lacking


# ─────────────────────────── v3 분석: 대운 · 힘의 균형 · 분야별 상대평가 ───────────────────────────
PHASE = {"비겁": ("자립기", "내 힘으로 서고 내 방식을 세우는 10년"),
         "식상": ("표현기", "재능과 말·결과물을 펼쳐 보이는 10년"),
         "재성": ("확장기", "성과와 돈, 현실을 직접 다루는 10년"),
         "관성": ("책임기", "자리와 역할, 책임이 커지는 10년"),
         "인성": ("충전기", "배우고 자격을 갖추며 기반을 다지는 10년")}
JOB_FOCUS = {
    "직장인": {"비겁": "동료와 역할을 나누고, 내 몫의 성과를 분명히 드러내기", "식상": "개선 아이디어·제안으로 존재감 키우기",
             "재성": "숫자로 보이는 성과, 평가·성과급 챙기기", "관성": "승진·인사이동·책임 있는 자리에 대비하기",
             "인성": "자격증·교육·문서 업무로 기반 다지기"},
    "자영업": {"비겁": "비슷한 가게와의 협업과 차별화, 동업 조건은 문서로", "식상": "신메뉴·콘텐츠·홍보로 손님 끌기",
             "재성": "매출 확대 기회 잡기, 고정비·현금흐름 매달 점검", "관성": "계약·세무·인허가 같은 규칙 정비로 신뢰 쌓기",
             "인성": "브랜드·운영 방식 정비, 배우며 다음 단계 준비"},
    "학생·취준": {"비겁": "스터디 동료와 함께 페이스 유지", "식상": "포트폴리오·발표·면접 표현력 키우기",
               "재성": "현실적인 목표 설정, 아르바이트·실무 경험 쌓기", "관성": "시험·합격·조직에 들어가는 흐름 잡기",
               "인성": "자격증·공부에 몰입하기"},
}
LOVE_STATUS = {
    "미혼": {"합": "가까운 곳에서 자연스럽게 인연이 이어지기 쉬운 흐름이에요. 소개나 모임 제안에 열려 있어 보세요.",
           "충": "익숙한 연애 패턴을 바꿔 보고 싶어지는 흐름이에요. 새로운 환경에서의 만남이 의외로 잘 맞을 수 있어요.",
           "평": "조급할 필요 없는 흐름이에요. 내 생활 반경 안에서 꾸준히 사람을 만나 보세요."},
    "연애중": {"합": "관계가 한 단계 가까워지기 쉬운 흐름이에요. 미래 계획을 함께 이야기해 보기 좋아요.",
            "충": "생활 패턴·거리감에 변화가 생기기 쉬워요. 서운함은 쌓아 두지 말고 그때그때 대화로 풀어 보세요.",
            "평": "큰 변화 없이 안정적인 흐름이에요. 둘만의 작은 루틴을 만들어 보세요."},
    "기혼": {"합": "배우자와 한 방향을 보기 좋은 흐름이에요. 함께 정한 목표가 힘이 돼요.",
           "충": "집안 일정·환경에 변화가 생기기 쉬워요. 역할 분담과 돈 이야기를 미리 맞춰 두세요.",
           "평": "평온한 흐름이에요. 일상 속 고마움을 표현하는 게 가장 좋은 관리예요."},
}
LIFE_CARE = {  # 그해 십신별 생활관리 (질병 예측 아님)
    "비견": "혼자 다 떠안기 쉬운 해예요. 운동도 일도 '같이 하는 사람'을 두면 오래 가요.",
    "겁재": "경쟁심에 무리하기 쉬운 해예요. 이기려는 일정보다 회복하는 일정을 먼저 잡으세요.",
    "식신": "먹고 쉬는 즐거움이 커지는 해예요. 식사 리듬과 수면 시간을 일정하게 지키면 컨디션이 오래 가요.",
    "상관": "생각과 말이 많아져 머리가 쉴 틈이 없기 쉬워요. 하루 한 번은 화면을 끄는 시간을 만드세요.",
    "편재": "바깥 활동이 늘어 체력이 분산되기 쉬워요. 일정 사이에 빈칸을 남겨 두세요.",
    "정재": "꼼꼼함이 걱정으로 번지기 쉬워요. 할 일을 적어 두고 머릿속에서는 내려놓는 연습을 해 보세요.",
    "편관": "책임과 압박이 커지기 쉬운 해예요. 과로 신호가 오면 바로 쉬고, 검진은 미루지 마세요.",
    "정관": "규칙적인 생활이 가장 잘 맞는 해예요. 잠·운동 시간을 고정해 두면 흔들림이 줄어요.",
    "편인": "생각이 깊어지는 만큼 혼자 가라앉기 쉬워요. 햇볕 쬐며 걷기와 사람 만나기를 일부러 챙기세요.",
    "정인": "도움을 주고받기 좋은 해예요. 몸이 보내는 신호를 무시하지 말고 쉬는 것도 계획에 넣으세요.",
}
REL_TIP = {"충": "생활에 변화가 생기기 쉬우니 일정에 여유를 두세요.", "형": "말과 약속을 한 번 더 점검하세요.",
           "자형": "스스로를 몰아붙이지 말고 쉼표를 넣으세요.", "파": "계획을 한 번 손보기 좋은 달이에요.",
           "해": "중요한 말은 한 번 더 확인하세요."}
LEVEL5 = {5: "매우 좋음", 4: "좋음", 3: "보통", 2: "신중", 1: "매우 신중"}
LEVEL3 = {1: "좋음", 0: "보통", -1: "신중"}


def calc_daeyun(p):
    """대운 — lunar-python 결과를 절입일까지 일수÷3 직접 계산과 교차검증"""
    g = str(p["gender"])
    if not (g.startswith("남") or g.startswith("여")):
        return None
    male = g.startswith("남")
    yun = p["ec"].getYun(1 if male else 0, 1)
    yg = p["pillars"]["year"][0]
    fwd = (GAN_YY[yg] == "양") == male
    assert yun.isForward() == fwd, "대운 순역 불일치"
    lunar = Solar.fromYmdHms(p["dt"].year, p["dt"].month, p["dt"].day, p["dt"].hour, p["dt"].minute, 0).getLunar()
    jq = lunar.getNextJie() if fwd else lunar.getPrevJie()
    js = jq.getSolar()
    jdt = datetime.datetime(js.getYear(), js.getMonth(), js.getDay(), js.getHour(), js.getMinute())
    days = abs((jdt - p["dt"]).total_seconds()) / 86400
    own_start = p["dt"] + datetime.timedelta(days=days * 120)  # 3일 = 1년
    ls = yun.getStartSolar()
    lib_start = datetime.datetime(ls.getYear(), ls.getMonth(), ls.getDay())
    assert abs((own_start - lib_start).days) <= 125, f"대운 시작 불일치 {own_start} vs {lib_start}"  # 라이브러리는 일·시 단위 근사
    mi = (GAN.index(p["pillars"]["month"][0]), ZHI.index(p["pillars"]["month"][1]))
    out = []
    for k, d in enumerate(yun.getDaYun()[1:10], 1):
        step = k if fwd else -k
        expect = GAN[(mi[0] + step) % 10] + ZHI[(mi[1] + step) % 12]
        assert d.getGanZhi() == expect, f"대운 간지 불일치 {d.getGanZhi()} vs {expect}"
        sy = own_start.year + 10 * (k - 1)
        out.append(dict(gz=d.getGanZhi(), start=sy, end=sy + 9))
    return dict(forward=fwd, start=own_start, days=days, su=max(1, round(days / 3)), list=out)


def strength(p):
    """억부 기준 힘의 균형: 월지 3 · 일지 2 · 나머지 1 (일간 제외), 나를 돕는 기운(비겁·인성) 비율"""
    me = GAN_EL[p["stem"]]
    help_el = {me, next(e for e in EL_ORDER if SHENG[e] == me)}
    items = []
    for k in ("year", "month", "day", "time"):
        gz = p["pillars"][k]
        if not gz:
            continue
        if k != "day":
            items.append((GAN_EL[gz[0]], 1))
        items.append((ZHI_EL[gz[1]], {"month": 3, "day": 2}.get(k, 1)))
    tot = sum(w for _, w in items)
    sup = sum(w for e, w in items if e in help_el)
    r = sup / tot
    kind = "강" if r >= 0.6 else "약" if r < 0.4 else "중"
    return dict(sup=sup, tot=tot, ratio=r, kind=kind, deukryeong=ZHI_EL[p["pillars"]["month"][1]] in help_el)


FAV = {"강": {"비겁": -1, "인성": -1, "식상": 1, "재성": 1, "관성": 1},
       "약": {"비겁": 1, "인성": 1, "식상": -0.5, "재성": -1, "관성": -1},
       "중": {"비겁": 0, "인성": 0, "식상": 0.5, "재성": 0, "관성": 0}}
REL_SCORE = {"육합": 0.5, "반합": 0.5, "충": -1, "형": -0.5, "자형": -0.5, "파": -0.25, "해": -0.25}


def clamp5(x):
    return max(1, min(5, int(math.floor(x + 0.5))))


def ratings(p, Y, S):
    """2027 분야별 상대평가(1~5) + 한 줄 근거. 모든 규칙은 십신·합충·힘의 균형에서만 나옴"""
    yg, yz = Y["gz"][0], Y["gz"][1]
    t1, t2 = ten_god(p["stem"], yg), ten_god(p["stem"], ZHI_MAIN[yz])
    g1, g2 = TG_GROUP[t1], TG_GROUP[t2]
    F = FAV[S["kind"]]
    kinds = {r[0] for r in branch_rels(p["branch"], yz)}
    rel = sum(REL_SCORE[k] for k in kinds)
    male = str(p["gender"]).startswith("남")
    star = "재성" if male else "관성"
    good_spouse = "정재" if male else "정관"
    R = {}
    x = 3 + F[g1] + 0.5 * F[g2] + rel
    R["종합운"] = (x, f"{t1}·{t2}의 기운이 {'나에게 힘이 되는' if F[g1] + 0.5 * F[g2] > 0 else '부담과 숙제를 함께 주는' if F[g1] + 0.5 * F[g2] < 0 else '무난한'} 쪽으로 계산돼요.")
    x = 3 + (1 if g1 == "재성" else 0) + (0.5 if g2 == "재성" else 0) + (0.5 if g1 == "식상" else 0) \
        - (1 if t1 == "겁재" else 0.5 if t1 == "비견" else 0) - (0.5 if S["kind"] == "약" and "재성" in (g1, g2) else 0)
    R["재물운"] = (x, "돈의 별(재성)이 들어오는 해예요." if "재성" in (g1, g2) else "나눠 쓰는 지출이 늘기 쉬운 해예요." if g1 == "비겁" else "재능이 돈으로 이어지는 통로가 열리는 해예요." if g1 == "식상" else "돈보다 다른 분야에 무게가 실리는 해예요.")
    x = 3 + (1 if g1 == star else 0) + (0.5 if g2 == star else 0) + (1 if kinds & {"육합", "반합"} else 0) - (0.5 if kinds & {"충", "형"} else 0)
    R["연애운"] = (x, "인연의 별이 들어오는 해예요." if star in (g1, g2) else "배우자 자리와 합이 드는 해예요." if kinds & {"육합", "반합"} else "관계에 변화의 바람이 부는 해예요." if kinds & {"충", "형"} else "잔잔하게 흘러가는 해예요.")
    x = 3 + (0.5 if good_spouse in (t1, t2) else 0) + (1 if kinds & {"육합", "반합"} else 0) - (1 if "충" in kinds else 0.5 if kinds & {"형", "파", "해", "자형"} else 0)
    R["결혼·관계 안정"] = (x, "배우자 자리(일지)가 묶이는 합이 있어요." if kinds & {"육합", "반합"} else "배우자 자리가 흔들리는 충이 있어 대화가 중요해요." if "충" in kinds else "배우자 자리에 큰 움직임은 없어요.")
    w = (1 if F.get(g1, 0) > 0 else 0.5) if g1 in ("관성", "식상") else (0.5 if g1 == "인성" else 0)
    x = 3 + w + (0.5 if g2 in ("관성", "식상") else 0) - (0.5 if F[g1] < 0 and g1 == "관성" else 0)
    R["일·직장운"] = (x, {"관성": "자리와 역할이 분명해지는 흐름이에요.", "식상": "새로운 시도와 결과물이 돋보이는 흐름이에요.", "인성": "공부·자격으로 기반을 다지는 흐름이에요.",
                     "재성": "성과를 숫자로 보여 주는 흐름이에요.", "비겁": "동료·경쟁 속에서 내 자리를 다지는 흐름이에요."}[g1])
    x = 3 + (1 if kinds & {"육합", "반합"} else 0) + (0.5 if g1 == "비겁" else 0) - (0.5 if t1 == "편관" else 0) - (0.5 if "충" in kinds else 0)
    R["인간관계운"] = (x, "가까운 사람과의 연결이 강해지는 해예요." if kinds & {"육합", "반합"} else "사람이 모이고 어울릴 일이 많은 해예요." if g1 == "비겁" else "관계에서 선을 분명히 하면 편한 해예요.")
    x = 3 + (1 if g1 == "인성" else 0) + (0.5 if t1 == "정관" else 0) - (0.5 if t1 == "겁재" else 0) - (0.5 if kinds & {"형"} else 0)
    R["문서·계약운"] = (x, "공부·자격·문서에 힘이 실리는 해예요." if g1 == "인성" else "약속과 계약을 지키는 힘이 커지는 해예요." if t1 == "정관" else "계약은 조건을 한 번 더 확인하면 좋은 해예요." if t1 == "겁재" or "형" in kinds else "평소처럼 꼼꼼히 챙기면 되는 해예요.")
    x = 3 - (1 if t1 == "편관" else 0) - (0.5 if "충" in kinds else 0) + (0.5 if t1 in ("식신", "정인") else 0) - (0.5 if S["kind"] == "약" and F[g1] < 0 else 0)
    R["생활관리운"] = (x, LIFE_CARE[t1].split(". ")[0] + ".")
    return {k: (clamp5(v), why) for k, (v, why) in R.items()}


def month_levels(p, S):
    F = FAV[S["kind"]]
    male = str(p["gender"]).startswith("남")
    star = "재성" if male else "관성"

    def f(m):
        g, z = m["gz"][0], m["gz"][1]
        t1, t2 = ten_god(p["stem"], g), ten_god(p["stem"], ZHI_MAIN[z])
        g1, g2 = TG_GROUP[t1], TG_GROUP[t2]
        kinds = {r[0] for r in branch_rels(p["branch"], z)}
        rel = sum(REL_SCORE[k] for k in kinds)
        tot = F[g1] + 0.5 * F[g2] + rel
        lv = lambda x: 1 if x >= 0.75 else -1 if x <= -0.75 else 0
        money = (1 if g1 == "재성" else 0) + (0.5 if g2 == "재성" else 0) + (0.5 if g1 == "식상" else 0) - (1 if t1 == "겁재" else 0.5 if t1 == "비견" else 0)
        love = (1 if g1 == star else 0) + (0.5 if g2 == star else 0) + (1 if kinds & {"육합", "반합"} else 0) - (1 if kinds & {"충", "형"} else 0)
        work = (1 if g1 in ("관성", "식상") else 0) + (0.5 if g2 in ("관성", "식상") else 0) + (0.5 if g1 == "인성" else 0) - (0.5 if "충" in kinds else 0)
        return dict(m=m, t1=t1, kinds=kinds, score=tot, lv=lv(tot), money=lv(money), love=lv(love), work=lv(work),
                    tip=TG[t1]["month"].split(". ")[-1] if not kinds - {"육합", "반합"} else REL_TIP[sorted(kinds - {"육합", "반합"})[0]])
    return f


def months_until_lichun(Y, today=None):
    """작성일부터 2027 입춘 전까지 남은 달(2026 병오년)"""
    today = today or datetime.date.today()
    out = []
    s = Solar.fromYmd(today.year, today.month, today.day)
    cur = s.getLunar().getPrevJie()
    while True:
        js = cur.getSolar()
        start = to_kst(cur)
        if start >= Y["lichun"]:
            break
        probe = Solar.fromYmdHms(js.getYear(), js.getMonth(), js.getDay(), 12, 0, 0).next(1)
        gz = probe.getLunar().getEightChar().getMonth()
        nxt = Solar.fromYmdHms(js.getYear(), js.getMonth(), js.getDay(), 12, 0, 0).next(3).getLunar().getNextJie()
        out.append(dict(gz=gz, start=start, end=to_kst(nxt) - datetime.timedelta(days=1)))
        cur = nxt
        if len(out) > 4:
            break
    return out


# ─────────────────────────── 웹(반응형) 출력 ───────────────────────────
FONT_LINK = '<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&family=Noto+Serif+KR:wght@500;700;900&display=swap" rel="stylesheet">'
WEB_CSS = """
body { font-family: 'Noto Sans CJK KR','Noto Sans KR','Apple SD Gothic Neo',sans-serif; background: #070d20; }
.serif, h1, h2, .hz1, .big-ilju .hz, .vs .c .hz, .cover .big, .cover .title, .cover .year, .g10 b, .cyc .e b, .tl .g, .mate .big, .wm, .cal .hd span, .pt .n, .pt b, .tg div b, dl.gl dt, .strip b { font-family: 'Noto Serif CJK KR','Noto Serif KR',serif !important; }
.page { width: auto; max-width: 210mm; height: auto; margin: 0 auto 4mm; padding: 34px 26px 34px; page-break-after: auto; }
.hdr, .ftr { display: none; }
.cover { min-height: 88vh; padding-top: 90px; padding-bottom: 150px; }
.wm { font-size: min(150mm, 92vw); }
.page > div[style*="position:absolute"] { position: static !important; margin-top: 10mm; }
.bar-top { position: sticky; top: 0; z-index: 9; display: flex; gap: 8px; justify-content: center; align-items: center; padding: 10px 12px;
  background: rgba(7,13,32,.92); backdrop-filter: blur(6px); border-bottom: 1px solid rgba(212,176,106,.3); }
.bar-top a, .bar-top button { font: 500 14px 'Noto Sans KR', sans-serif; color: #0d1630; background: #d4b06a; border: 0; border-radius: 20px; padding: 8px 16px; text-decoration: none; cursor: pointer; }
.bar-top a.ghost { background: transparent; color: #f0d9a6; border: 1px solid rgba(212,176,106,.5); }
.cta { max-width: 210mm; margin: 0 auto 8mm; padding: 26px 22px; text-align: center; border: 1px solid #d4b06a; border-radius: 4mm; background: rgba(212,176,106,.08); color: #ece7da; }
.cta b { display: block; font: 700 18px 'Noto Serif KR', serif; color: #f0d9a6; margin-bottom: 8px; }
.cta p { font-size: 14px; line-height: 1.8; }
@media (max-width: 640px) {
  .page { padding: 28px 16px 30px; margin-bottom: 3mm; }
  h1 { font-size: 19pt; } h2 { font-size: 12pt; }
  p, li { font-size: 10.5pt; } .lead { font-size: 9.8pt; }
  .two, .mate, .tl { grid-template-columns: 1fr; } .three { gap: 2mm; } .three .card { padding: 3.5mm 2mm !important; }
  .luck, .cal, .chk { grid-template-columns: 1fr 1fr; }
  .cal > div { min-height: 0; }
  .g10 { gap: 1.2mm; } .g10 .s { display: none; } .g10.z { grid-template-columns: repeat(4, 1fr); }
  .cyc { flex-wrap: wrap; justify-content: center; gap: 3mm 0; } .cyc .a { display: none; } .cyc .e { width: 33%; }
  .tg div .small { display: none; }
  .rate { grid-template-columns: 25mm 1fr 15mm; gap: 2mm; }
  .cover .big { font-size: 66pt; } .cover .title { font-size: 20pt; } .ring { width: 92vw; height: 92vw; } .ring.r2 { width: 80vw; height: 80vw; }
  .hz1 { font-size: 22pt; } table.pl { border-spacing: 1mm 0; }
  .big-ilju { gap: 5mm; } .big-ilju .hz { font-size: 42pt; }
  .person-head { flex-direction: column; gap: 1mm; }
  .sum { grid-template-columns: 1fr; row-gap: .6mm; } .sum dd { margin-bottom: 2.4mm; }
  .card { padding: 4.5mm 5mm; }
}
@media print { .bar-top, .cta { display: none; } }
"""


def wrap_html(pages, mode="print", full=True, hidden=""):
    if mode == "print":
        auto = "<script>window.addEventListener('load',()=>setTimeout(()=>window.print(),700))</script>" if hidden == "autoprint" else ""
        return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{FONT_LINK if auto else ""}<title>2027 신년운세 리포트</title><style>{CSS}{".serif,h1,h2{font-family:\'Noto Serif CJK KR\',\'Noto Serif KR\',serif} body{font-family:\'Noto Sans CJK KR\',\'Noto Sans KR\',sans-serif}" if auto else ""}</style>{auto}</head><body>{"".join(pages)}</body></html>'
    sel = pages if full else [pages[i] for i in (0, 1, 2, 3, 5) if i < len(pages)]
    cta = "" if full else ('<div class="cta"><b>여기까지가 무료 요약판이에요</b><p>연애·결혼 · 금전 · 직업 · 대운 · 열두 달 캘린더 · 궁합까지 담긴 <b style="display:inline;font-size:inherit">14쪽 전체 리포트</b>는<br>'
                           '혼술바 온도 매장 코드를 넣으면 무료로 볼 수 있어요.</p><p style="margin-top:10px"><a href="/report" style="color:#f0d9a6">← 매장 코드 넣고 다시 보기</a></p></div>')
    bar = (f'<div class="bar-top"><a class="ghost" href="/report">다시 입력</a>'
           f'<form method="post" action="/api/report" target="_blank" style="margin:0">{hidden}<input type="hidden" name="format" value="print"><button type="submit">PDF로 저장</button></form></div>') if full else \
        '<div class="bar-top"><a class="ghost" href="/report">다시 입력</a></div>'
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="robots" content="noindex"><title>내 2027 신년운세 리포트 · 60일주 도감</title>{FONT_LINK}<style>{CSS}{WEB_CSS}</style></head>'
            f'<body>{bar}{"".join(sel)}{cta}</body></html>')


def month_label(m):
    return f"{m['start'].month}월" if m["start"].year == TARGET_YEAR else f"{m['start'].month}월({str(m['start'].year)[2:]}년)"


def pick_months(p, Y, score_fn, top=3):
    """월건별 점수 → 점수 높은 달 (점수 0 제외), 시간순 정렬"""
    sc = []
    for i, m in enumerate(Y["months"]):
        g, z = m["gz"][0], m["gz"][1]
        s = score_fn(TG_GROUP[ten_god(p["stem"], g)], TG_GROUP[ten_god(p["stem"], ZHI_MAIN[z])],
                     {r[0] for r in branch_rels(p["branch"], z)}, ten_god(p["stem"], g))
        if s > 0:
            sc.append((s, i, m))
    best = sorted(sc, key=lambda t: (-t[0], t[1]))[:top]
    return [m for _, _, m in sorted(best, key=lambda t: t[1])]


def mchips(ms, empty="특별히 두드러지는 달은 없어요 — 꾸준한 리듬이 가장 큰 무기예요."):
    if not ms:
        return f'<p class="small">{empty}</p>'
    return '<div class="mchips">' + "".join(f'<span class="chip">{month_label(m)} · {m["gz"]}</span>' for m in ms) + "</div>"


def els_txt(els):
    return "·".join(f"{e}({EL_KR[e]})" for e in els)


def render(p, Y, mode="print", full=True, hidden=""):
    N = p["nick"]
    yg, yz = Y["gz"][0], Y["gz"][1]
    tg_y = ten_god(p["stem"], yg)
    tg_yz = ten_god(p["stem"], ZHI_MAIN[yz])
    grp_y, grp_yz = TG_GROUP[tg_y], TG_GROUP[tg_yz]
    me_el = GAN_EL[p["stem"]]
    male = str(p["gender"]).startswith("남")
    pages = []
    ebn = [0]

    def E(title):
        ebn[0] += 1
        return f'<div class="eyebrow">{ebn[0]:02d} · {title}</div>'

    def add(inner, wm="", cls="", cover=False):
        pages.append(page(inner, None if cover else len(pages) + 1, wm=wm, cls=cls))

    t_txt = f" · {esc(p['time'])}" if p["has_time"] else " · 태어난 시간 미상"
    rels = branch_rels(p["branch"], yz)
    kinds = {r[0] for r in rels}
    kws, plus, lacking = keywords(p, Y)
    st, bz = STEM[p["stem"]], BRANCH[p["branch"]]

    S = strength(p)
    D = calc_daeyun(p)
    RT = ratings(p, Y, S)
    FM = month_levels(p, S)
    ML = [FM(m) for m in Y["months"]]
    ORDER = ["종합운", "재물운", "연애운", "결혼·관계 안정", "일·직장운", "인간관계운", "문서·계약운", "생활관리운"]
    INT_MAP = {"금전": "재물운", "재물": "재물운", "돈": "재물운", "투자": "재물운", "부동산": "재물운", "연애": "연애운",
               "결혼": "결혼·관계 안정", "사업": "일·직장운", "직장": "일·직장운", "승진": "일·직장운", "이직": "일·직장운",
               "건강": "생활관리운", "인간관계": "인간관계운", "가족": "인간관계운", "계약": "문서·계약운"}
    picked = []
    for it in p["interests"]:
        for k, v in INT_MAP.items():
            if k in str(it) and v not in picked:
                picked.append(v)
    best = max(ORDER[1:], key=lambda k: (RT[k][0], -ORDER.index(k)))
    worst = min(ORDER[1:], key=lambda k: (RT[k][0], ORDER.index(k)))
    cols = []
    for k in picked:
        c = {"재물운": ("money", "재물"), "연애운": ("love", "연애"), "결혼·관계 안정": ("love", "연애"), "일·직장운": ("work", "일")}.get(k)
        if c and c not in cols:
            cols.append(c)
    for c in ([("money", "재물"), ("work", "일")] if p["job"] and not p["status"] else [("money", "재물"), ("love", "연애")]):
        if len(cols) < 2 and c not in cols:
            cols.append(c)
    cols = cols[:2]
    # ── 표지
    add(f"""
      <div class="ring"></div><div class="ring r2"></div>
      <div class="brand">60 ILJU DOGAM</div>
      <div class="year">{TARGET_YEAR}</div>
      <div class="big">{Y['gz']}</div>
      <div class="title">정미년 내 일주 신년운세</div>
      <div class="sub">내 일주로 미리 보는 {TARGET_YEAR}년의 흐름 · 연애 · 돈 · 일</div>
      <div class="me">{esc(N)} <b>{p['day']}</b> {gz_kr(p['day'])}일주</div>
      <div class="cover-foot">{esc(N)} ({esc(p['gender'])}) — {p['solar']}{t_txt}<br>
      <span style="color:var(--gold)">작성일 {datetime.date.today():%Y.%m.%d} · 만세력 코드 자동 계산 · 재미와 참고를 위한 콘텐츠</span></div>
    """, wm="未", cls="cover", cover=True)

    # ── 사주 처음이라면
    g10 = "".join(f'<div class="{"on" if g == p["stem"] else ""}"><b style="color:{EL_COLOR[GAN_EL[g]]}">{g}</b>'
                  f'<span class="r">{STEM_NAME[g]}</span><span class="s">{STEM_SHORT[g]}</span></div>' for g in GAN)
    z12 = "".join(f'<div class="{"on" if z == p["branch"] else ""}"><b style="color:{EL_COLOR[ZHI_EL[z]]}">{z}</b>'
                  f'<span class="r">{ZHI_KR[z]} · {BRANCH[z]["animal"]}</span><span class="s">{EL_KR[ZHI_EL[z]]}</span></div>' for z in ZHI)
    cyc = '<span class="a">→</span>'.join(f'<div class="e"><b style="color:{EL_COLOR[e]}">{e}</b><span>{EL_SHORT[e]}</span></div>' for e in EL_ORDER)
    add(f"""
      {E('사주 처음이라면')}<h1>3분 만에 읽는 사주 기초</h1>
      <p class="lead">사주(四柱)는 태어난 <b style="color:var(--gold2)">해 · 달 · 날 · 시</b> 네 기둥이에요. 기둥마다 위 글자(천간)와 아래 글자(지지)가 하나씩 있어 모두 여덟 글자, 그래서 '팔자'라고 불러요.</p>
      <div class="card plus"><span class="k">이 리포트의 주인공 = 일주</span>
        <p class="tip">태어난 '날'의 기둥이 <b style="color:var(--gold2)">일주</b>예요. 그 위 글자(일간)가 바로 '나'예요.
        {esc(N)}의 일주는 <b style="color:var(--gold2)">{p['day']}({gz_kr(p['day'])})</b> — 일간 {p['stem']}{jo('('+STEM_NAME[p['stem']]+')','은','는')} {esc(st['img'])}, 일지 {p['branch']}{jo('('+ZHI_KR[p['branch']]+')','은','는')} {BRANCH[p['branch']]['animal']}의 글자예요.</p></div>
      <h2>천간 열 글자 — '나'를 나타내는 자연</h2>
      <div class="g10">{g10}</div>
      <p class="small" style="margin-top:1.5mm">'정화(丁火)'는 정 + 화(불), '을목(乙木)'은 을 + 목(나무)처럼 글자 이름에 오행을 붙여 읽어요. 금색 칸이 내 일간이에요.</p>
      <h2>지지 열두 글자 — 우리가 아는 '띠'</h2>
      <div class="g10 z">{z12}</div>
      <h2>오행 — 다섯 가지 기운</h2>
      <div class="cyc">{cyc}</div>
      <p class="small">→ 방향으로 서로 키워 줘요(상생: 나무가 불을 키우고, 불이 흙을 만들고…). 한 칸 건너뛰면 서로 다듬어요(상극: 나무가 흙을, 물이 불을). 좋고 나쁨이 아니라 '관계'를 보는 거예요.</p>
    """, wm="八")

    # ── 원국 + 힘의 균형
    adj = f" · {', '.join(p['adj_notes'])}" if p["adj_notes"] else ""
    el_chips = " ".join(f'<span class="chip"><span class="dot" style="background:{EL_COLOR[e]}"></span>{e}{EL_KR[e]} {p["counts"][e]}</span>' for e in EL_ORDER)
    help_els = [me_el, next(e for e in EL_ORDER if SHENG[e] == me_el)]
    s_label = {"강": "힘이 강한 편 — 밀고 나가는 사주", "중": "균형형 — 치우침이 적은 사주", "약": "섬세한 편 — 도움을 받아 크는 사주"}[S["kind"]]
    s_txt = {"강": "나를 돕는 기운이 충분해서 추진력이 좋아요. 그 힘을 밖으로 써 줄 표현·성과·책임의 기운(식상·재성·관성)이 들어올 때 빛나는 구조로 봐요.",
             "중": "나를 돕는 기운과 내가 쓰는 기운이 비슷해요. 어느 쪽으로 크게 치우치지 않아 해마다 흐름을 고르게 타는 편이에요.",
             "약": "나를 돕는 기운보다 내가 감당하는 기운이 더 많아요. 배움·사람·쉼(인성·비겁)이 들어올 때 힘이 붙고, 일이 몰릴 땐 나눠 드는 게 이득인 구조로 봐요."}[S["kind"]]
    add(f"""
      {E('사주 원국')}<h1>{esc(N)}의 원국</h1>
      <p class="lead">태어난 해·달·날·시를 천간(위)과 지지(아래) 글자로 나타낸 표예요. 가운데 금색 칸이 이 리포트의 중심인 '일주'예요.</p>
      <div class="person-head"><b>{esc(N)} <span>({esc(p['gender'])})</span></b><span>{p['solar']} · {p['lunar']}{t_txt}{adj}</span></div>
      {pillar_table(p)}
      <h2>원국의 오행</h2><div>{el_chips}</div>
      <div class="card plus" style="margin-top:4mm"><span class="k">타고난 힘의 균형 — {s_label}</span>
        <div class="gauge"><i style="width:{S['ratio']*100:.0f}%"></i><b style="left:40%"></b><b style="left:60%"></b></div>
        <p class="small">나를 돕는 기운({els_txt(help_els)}) {S['sup']} / 전체 {S['tot']} · 태어난 달 {jo('('+p['pillars']['month'][1]+')','이','가')} {'나를 돕는 기운이에요(득령)' if S['deukryeong'] else '나를 돕는 기운은 아니에요(실령)'}</p>
        <p class="tip" style="margin-top:1.5mm">{s_txt}</p>
        <p class="small" style="margin-top:1mm">오행 개수와 실제 힘은 달라요. 계절을 정하는 태어난 달(가중치 3)과 일지(2)를 더 무겁게 쳐서 계산했어요.</p></div>
      <div class="card"><span class="k">계산 기준과 검증</span>
        <p class="small">만세력 라이브러리(lunar-python)로 절기 기준 년·월주를 계산했어요. 태어난 시간이 있으면 동경 127.5° 기준 30분 보정(1987·88년 서머타임 기간은 추가 보정)을 하고, 23시 이후 출생은 다음 날 일주로 봐요. 시간을 모르면 시주를 비워 두고 나머지 글자로 풀이해요.<br>
        검증: {p['check']}{' · 대운 순역·간지·시작 시점 직접 계산 대조 ✓' if D else ''} · {TARGET_YEAR} 세운 {Y['gz']} 입춘 기준 확인 ✓ · 월건 12개 오호둔 공식 대조 ✓</p></div>
    """, wm="命")

    # ── 일주 한눈에
    dname, dtxt = DISHI.get(p["dishi"], (p["dishi"], ""))
    kw = "".join(f'<span class="chip">{esc(k)}</span>' for k in st["kw"])
    add(f"""
      {E('내 일주 한눈에')}<h1>{gz_kr(p['day'])}일주는 이런 사람</h1>
      <div class="big-ilju"><div class="hz">{p['day']}</div>
        <div class="meta">일간 <b style="color:var(--gold2)">{p['stem']}</b> {STEM_NAME[p['stem']]} · {GAN_YY[p['stem']]}{GAN_EL[p['stem']]} — {esc(st['img'])}<br>
        일지 <b style="color:var(--gold2)">{p['branch']}</b> {bz['animal']} · {ZHI_EL[p['branch']]} — {esc(bz['img'])}<br>
        12운성 <b style="color:var(--gold2)">{dname}</b> — {esc(dtxt)}</div></div>
      <div>{kw}</div><div class="rule"></div>
      <div class="card"><span class="k">일간 — 타고난 기질</span><p>{esc(st['desc'])}</p></div>
      <div class="card"><span class="k">일지 — 가까운 자리에서의 모습</span><p>{esc(bz['desc'])}</p></div>
      <div class="card"><span class="k">두 글자의 관계 — {GAN_EL[p['stem']]} · {ZHI_EL[p['branch']]}</span><p>{inner_rel(p['stem'], p['branch'])}</p></div>
      <div class="two">
        <div class="card"><span class="k">강점</span><p>{esc(st['strength'])}</p></div>
        <div class="card"><span class="k">알아 두면 좋은 점</span><p>{esc(st['care'])}</p></div>
      </div>
    """, wm=p["stem"])

    # ── 지금, 인생의 어느 지점
    def dy_box(d, cls=""):
        g1 = TG_GROUP[ten_god(p["stem"], d["gz"][0])]
        g2 = TG_GROUP[ten_god(p["stem"], ZHI_MAIN[d["gz"][1]])]
        fv = FAV[S["kind"]][g1] + FAV[S["kind"]][g2]
        tone = "힘이 붙는 흐름" if fv > 0 else "단련되며 크는 흐름" if fv < 0 else "고르게 가는 흐름"
        return (f'<div class="{cls}"><div class="y">{d["start"]}~{d["end"]}년</div><div class="g">{d["gz"]}</div>'
                f'<div class="p">{PHASE[g1][0]} · {tone}</div><div class="d">{PHASE[g1][1]}</div></div>'), g1, fv
    flow_html = ""
    if D:
        lst = D["list"]
        ci = next((i for i, d in enumerate(lst) if d["start"] <= TARGET_YEAR <= d["end"]), None)
        if ci is None:  # 첫 대운 전(어린이)
            cur_txt = f"첫 대운은 {lst[0]['start']}년경 시작해요."
            flow_html = f'<div class="card"><p class="tip">{cur_txt}</p></div>'
            phase_now = None
        else:
            prev = lst[ci - 1] if ci > 0 else None
            nxt = lst[ci + 1] if ci + 1 < len(lst) else None
            boxes = []
            if prev:
                boxes.append(dy_box(prev)[0])
            else:
                boxes.append(f'<div><div class="y">~{lst[0]["start"] - 1}년</div><div class="g">–</div><div class="p">대운 시작 전</div><div class="d">타고난 원국의 흐름대로 자라는 시기</div></div>')
            nowb, g_now, fv_now = dy_box(lst[ci], "now")
            boxes.append(nowb)
            boxes.append(dy_box(nxt)[0] if nxt else "<div></div>")
            phase_now = (PHASE[g_now][0], lst[ci]["end"] + 1)
            task = {"비겁": "내 기준과 방식을 세우되, 혼자 다 하려 하지 않는 것", "식상": "재능을 꾸준한 결과물로 쌓아 보여 주는 것",
                    "재성": "기회를 고르고, 벌어들인 것을 지키는 구조를 만드는 것", "관성": "맡은 자리에서 신뢰를 쌓되, 책임에 눌리지 않게 페이스를 지키는 것",
                    "인성": "배움과 자격으로 다음 10년의 기반을 다지는 것"}[g_now]
            flow_html = (f'<div class="tl">{"".join(boxes)}</div>'
                         f'<div class="card plus"><span class="k">지금 가장 중요한 과제</span><p class="tip">{lst[ci]["start"]}년부터 이어지는 <b style="color:var(--gold2)">{PHASE[g_now][0]}</b>예요. {task}이 이 시기의 숙제로 봐요. 다음 큰 흐름은 <b style="color:var(--gold2)">{lst[ci]["end"] + 1}년경</b>에 바뀌어요.</p></div>')
    else:
        phase_now = None
        flow_html = '<div class="card"><p class="tip">성별 정보가 없어 대운(10년 흐름)은 계산하지 않았어요.</p></div>'
    rem = [FM(m) for m in months_until_lichun(Y)]
    rem_html = "".join(f'<span class="chip">{x["m"]["start"].month}월 {x["m"]["gz"]} · {LEVEL3[x["lv"]]}</span>' for x in rem)
    tg26 = ten_god(p["stem"], "丙")
    shift = f"2026년 병오(丙午)년은 {esc(N)}에게 {tg26}({TG_GROUP[tg26]} — {GROUP_INFO[TG_GROUP[tg26]]['plain']})의 해였고, {TARGET_YEAR}년은 {tg_y}({grp_y} — {GROUP_INFO[grp_y]['plain']})의 해예요."
    shift += " 같은 무리 안에서 결이 조금 바뀌는 정도라 흐름이 자연스럽게 이어져요." if TG_GROUP[tg26] == grp_y else f" 관심의 무게가 '{GROUP_INFO[TG_GROUP[tg26]]['plain'].split(' · ')[0]}' 쪽에서 '{GROUP_INFO[grp_y]['plain'].split(' · ')[0]}' 쪽으로 옮겨 가요."
    add(f"""
      {E('인생의 큰 흐름')}<h1>지금, 인생의 어느 지점에 있을까</h1>
      <p class="lead">사주에서는 약 10년마다 바뀌는 큰 흐름을 '대운'이라고 해요. 태어난 달에서 출발해 {'순서대로' if D and D['forward'] else '거꾸로'} 흘러가고, {f"{esc(N)}은 약 {D['su']}세 무렵({D['start'].year}년경)부터 시작했어요" if D else '성별에 따라 방향이 정해져요'}.</p>
      {flow_html}
      <h2>2027년 입춘 전까지 남은 시간</h2>
      <div class="mchips">{rem_html or '<span class="small">이미 2027년 흐름에 들어섰어요.</span>'}</div>
      <p class="small" style="margin-top:1mm">사주의 새해는 {Y['lichun']:%Y년 %-m월 %-d일} 입춘부터예요. 그 전까지는 2026년 병오년의 끝자락이에요.</p>
      <div class="card" style="margin-top:4mm"><span class="k">2027년으로 넘어가며</span><p class="tip">{shift}</p></div>
      <p class="small">대운 시작 시점은 태어난 시각부터 가까운 절기까지의 날짜로 계산해요(3일 = 1년). {'' if p['has_time'] else '태어난 시간을 몰라 정오 기준으로 계산했기 때문에 몇 달 정도 차이가 날 수 있어요.'}</p>
    """, wm="運")

    # ── 2027, 나에게 어떤 해
    def rate_row(k):
        v, why = RT[k]
        bar = "".join(f'<i class="{"on" + (" lo" if v <= 2 else "") if j < v else ""}"></i>' for j in range(5))
        star_mark = " ★" if k in picked else ""
        return f'<div class="rate"><span class="n">{k}{star_mark}</span><div class="bar">{bar}</div><span class="t">{LEVEL5[v]}</span><span class="w">{esc(why)}</span></div>'
    add(f"""
      {E(f'{TARGET_YEAR}년 종합')}<h1>{TARGET_YEAR}년, 나에게 어떤 해일까</h1>
      <p class="lead">{Y['gz']}년의 기운이 {esc(N)}의 원국(힘의 균형·일지)과 만나는 방식을 분야별로 계산했어요.{' ★는 관심 분야예요.' if picked else ''}</p>
      <div class="card">{''.join(rate_row(k) for k in ORDER)}</div>
      <div class="three">{''.join(f'<div class="card" style="text-align:center;padding:4mm 3mm"><span class="k">키워드 {i}</span><b class="serif" style="color:var(--gold2);font-size:13pt">{esc(t)}</b></div>' for i, (t, _) in enumerate(kws, 1))}</div>
      <div class="two">
        <div class="card plus"><span class="k">가장 큰 기회 — {best}</span><p class="tip">{esc(RT[best][1])} {esc(TG[tg_y]['month'].split('. ')[-1])}</p></div>
        <div class="card minus"><span class="k">신경 쓸 부분 — {worst}</span><p class="tip">{esc(RT[worst][1])} {esc(TG_AVOID[tg_y])}만 조심하면 충분해요.</p></div>
      </div>
      <p class="small">등급은 명리 이론에 따른 상대평가(5 매우 좋음 ~ 1 매우 신중)예요. 실제로 일이 일어날 확률을 뜻하지 않아요.</p>
    """, wm="年")

    # ── 계산 근거
    s_rel = stem_rels(p["stem"], yg)
    rel_lines = "<br>".join(f"<b style='color:var(--gold2)'>{k} · {esc(d)}</b> — {esc(REL_TXT[k]['y'].split('. ')[0])}." for k, d in rels) or \
        f"일지 {jo(p['branch'],'과','와')} {yz} 사이에 합·충·형·파·해가 없어요. 내 리듬대로 꾸려 가기 좋은 담백한 흐름이에요."
    he_line = "".join(f" 또 {d}{' — 한 해의 기운과 손을 잡는 흐름' if kd == '천간합' else ' — 익숙한 방식에 변화를 주고 싶어지는 흐름'}이에요." for kd, d in s_rel)
    k_html = "".join(f'<div class="pt"><div class="n">{i}</div><div><b>{esc(t)}</b><p>{esc(d)}</p></div></div>' for i, (t, d) in enumerate(kws, 1))
    add(f"""
      {E('왜 이렇게 봤을까')}<h1>{Y['gz']}년과 나의 관계</h1>
      <p class="lead">{TARGET_YEAR}년 {gz_kr(Y['gz'])}년은 {Y['lichun']:%-m월 %-d일 %H:%M} 입춘부터 시작해요. 천간 {yg}({STEM_NAME[yg]} · {esc(STEM[yg]['img'])})와 지지 {yz}({BRANCH[yz]['animal']} · {esc(BRANCH[yz]['img'])})가 내 일주와 어떻게 만나는지가 풀이의 근거예요.</p>
      <div class="card">{bar_chart(p['counts'], plus)}</div>
      {k_html}
      <p class="small">참고 — 지지 {yz} 속(지장간) 가장 큰 기운은 {ZHI_MAIN[yz]}로, 나에게 {tg_yz}({esc(TG[tg_yz]['sym'])})예요.{esc(he_line)}</p>
    """, wm="干")

    # ── 연애 · 결혼
    star_el = KE[me_el] if male else next(e for e in EL_ORDER if KE[e] == me_el)
    star_grp = "재성" if male else "관성"
    y_els = [GAN_EL[yg]] + [GAN_EL[h] for h in Y["hide"]]
    star_in_stem = GAN_EL[yg] == star_el
    star_in_hide = star_el in [GAN_EL[h] for h in Y["hide"]]
    if star_in_stem:
        star_y = f"{TARGET_YEAR}년 천간 {jo(yg,'이','가')} 바로 이 {star_grp}이에요. 전통적으로 인연의 별이 겉으로 드러나는 해라, 새로운 만남이나 관계를 진지하게 생각할 계기가 생기기 쉬운 흐름으로 봐요."
    elif star_in_hide:
        star_y = f"{TARGET_YEAR}년의 지지 {yz} 속(지장간)에 이 기운이 들어 있어요. 겉으로 요란하기보다 가까운 곳에서 은근하게 인연이 이어지는 흐름으로 봐요."
    else:
        star_y = f"{TARGET_YEAR}년에는 이 기운이 따로 들어오지 않아요. 새 인연을 '찾는' 해보다 지금의 나와 관계를 단단히 가꾸는 해로 보는 게 좋아요."
    n_star = p["counts"][star_el]
    natal_star = {0: f"원국에는 {star_el}({EL_KR[star_el]}) 글자가 없어요. 이럴 땐 인연을 기다리기보다 내가 좋아하는 활동 속에서 자연스럽게 만나는 쪽이 잘 맞는다고 봐요.",
                  1: f"원국에 {star_el}({EL_KR[star_el]}) 글자가 하나 있어요. 마음 가는 사람이 분명한, 한 사람에게 집중하는 결로 봐요.",
                  2: f"원국에 {star_el}({EL_KR[star_el]}) 글자가 둘 있어요. 인연의 기운이 적당히 있어 관계에 관심이 꾸준한 결로 봐요."}.get(
        n_star, f"원국에 {star_el}({EL_KR[star_el]}) 글자가 {n_star}개로 많은 편이에요. 인기가 있고 관계가 다채로울 수 있으니, 나에게 맞는 사람을 고르는 기준을 세워 두면 좋아요.")
    if kinds & {"육합", "반합"}:
        spouse_y = f"일지(배우자 자리)와 {yz}가 {'·'.join(sorted(kinds & {'육합','반합'}))} 관계예요. 가까운 사이가 더 가까워지기 쉬워, 함께 사는 이야기나 결혼 이야기가 오가기 좋은 흐름으로 보기도 해요."
    elif kinds & {"충", "형", "파", "해", "자형"}:
        spouse_y = f"일지(배우자 자리)와 {yz}가 {'·'.join(sorted(kinds - {'육합','반합'}))} 관계예요. 생활 패턴이나 거리감에 변화가 생기기 쉬우니, 큰 결정은 대화를 충분히 나눈 뒤에 해 보세요."
    else:
        spouse_y = f"일지(배우자 자리)와 {yz} 사이에 특별한 합·충이 없어요. 관계의 속도를 두 사람이 정하기 좋은, 담백한 흐름이에요."
    love_good = pick_months(p, Y, lambda gs, gz, rk, tg: (2 if gs == star_grp else 0) + (1 if gz == star_grp else 0) + (2 if rk & {"육합", "반합"} else 0))
    love_care = pick_months(p, Y, lambda gs, gz, rk, tg: 1 if rk & {"충", "형"} else 0, top=2)
    status_card = (f' — 지금 상황({p["status"]}) 기준</span><p class="tip">{esc(spouse_y)}</p><p class="tip" style="margin-top:1.5mm"><b style="color:var(--gold2)">지금 상황에서는</b> — {esc(LOVE_STATUS[p["status"]]["합" if kinds & {"육합", "반합"} else "충" if kinds & {"충", "형", "파", "해", "자형"} else "평"])}') if p['status'] else f'</span><p class="tip">{esc(spouse_y)}'
    add(f"""
      {E('연애 · 결혼')}<h1>{esc(N)}의 연애와 결혼</h1>
      <p class="lead">연애는 일간의 기질, 일지(배우자 자리), 그리고 전통적인 인연의 별({'남성은 재성' if male else '여성은 관성'})로 봐요. 요즘 관계에 그대로 대입하기보다 '관계의 결'을 보는 참고로 읽어 주세요.</p>
      <div class="card"><span class="k">♡ 나의 연애 스타일 — {STEM_NAME[p['stem']]} 일간</span><p>{esc(LOVE_STYLE[p['stem']])}</p></div>
      <div class="card"><span class="k">◎ 내가 원하는 관계 — 일지 {p['branch']}({BRANCH[p['branch']]['animal']})</span><p>{esc(SPOUSE[p['branch']])}</p></div>
      <div class="card plus"><span class="k">☆ {TARGET_YEAR}년 연애 흐름</span>
        <p class="tip">{esc(TG[tg_y]['love'])}</p>
        <p class="tip" style="margin-top:2mm"><b style="color:var(--gold2)">인연의 별</b> — {esc(N)}에게는 {star_el}({EL_KR[star_el]}) 기운이에요. {esc(natal_star)} {esc(star_y)}</p></div>
      <div class="card"><span class="k">◇ 결혼 · 오래 가는 관계{status_card}</p></div>
      <div class="two">
        <div class="card"><span class="k">마음을 표현하기 좋은 달</span>{mchips(love_good)}</div>
        <div class="card"><span class="k">대화에 여유를 둘 달</span>{mchips(love_care, '일지와 부딪히는 달이 없어요. 편안한 흐름이에요.')}</div>
      </div>
    """, wm="緣")

    # ── 금전
    money_el = KE[me_el]
    n_money = p["counts"][money_el]
    sik_el = SHENG[me_el]
    natal_money = {0: f"원국에 재성({money_el}{EL_KR[money_el]}) 글자가 없어요. 돈 자체를 좇기보다 일과 재능을 키우면 돈이 따라오는 구조로 보기도 해요. 목표 금액을 숫자로 정해 두면 흐름이 잡혀요.",
                   1: f"원국에 재성({money_el}{EL_KR[money_el]})이 하나 있어요. 필요한 만큼 챙기는 현실 감각이 있는 편이에요.",
                   2: f"원국에 재성({money_el}{EL_KR[money_el]})이 둘 있어요. 돈과 성과에 대한 감각이 살아 있는 편이에요."}.get(
        n_money, f"원국에 재성({money_el}{EL_KR[money_el]})이 {n_money}개로 많은 편이에요. 기회를 보는 눈이 밝은 만큼, 여러 곳에 벌이기보다 선택과 집중이 실속을 남겨요.")
    sik_txt = f" 재성을 낳는 식상({sik_el}{EL_KR[sik_el]})도 원국에 {p['counts'][sik_el]}개 있어요 — {'재능이 돈으로 이어지는 통로가 열려 있는 편이에요.' if p['counts'][sik_el] else '부업·기술처럼 내 재능을 돈으로 바꾸는 연습이 도움이 돼요.'}"
    money_good = pick_months(p, Y, lambda gs, gz, rk, tg: (2 if gs == "재성" else 0) + (1 if gz == "재성" else 0) + (1 if gs == "식상" else 0))
    money_care = pick_months(p, Y, lambda gs, gz, rk, tg: (2 if tg == "겁재" else 1 if tg == "비견" else 0) + (1 if gz == "비겁" else 0), top=2)
    money_habit = {'자영업': '매출보다 순이익·고정비·현금흐름을 매달 한 줄로 기록해 보세요. 숫자가 보이면 결정이 쉬워져요.',
                   '직장인': '급여일에 저축·투자 금액이 먼저 빠져나가게 자동이체를 걸어 두세요. 남는 돈으로 쓰는 구조가 가장 단단해요.',
                   '학생·취준': '용돈·아르바이트비를 주 단위 예산으로 나눠 보세요. 작은 기록 습관이 나중의 큰 차이가 돼요.'}.get(p['job']) or (
        '들어오고 나가는 돈을 한 달에 한 번 기록해 보세요. 흐름이 보이면 불안이 줄어요.' if grp_y in ('재성', '비겁') else '나에게 투자하는 돈(배움·도구·건강)과 그냥 새는 돈을 나눠 적어 보세요.')
    add(f"""
      {E('금전운')}<h1>{TARGET_YEAR}년 돈의 흐름</h1>
      <p class="lead">명리에서 돈은 '재성(내가 다루는 기운)'으로 봐요. {esc(N)}의 재성은 {money_el}({EL_KR[money_el]})이에요. 구체적인 투자 조언이 아니라 성향과 흐름을 보는 참고예요.</p>
      <div class="card"><span class="k">◆ 나의 돈 스타일 — {STEM_NAME[p['stem']]} 일간</span><p>{esc(MONEY_STYLE[p['stem']])}</p></div>
      <div class="card"><span class="k">◇ 원국의 재물 구조</span><p class="tip">{esc(natal_money)}{esc(sik_txt)}</p></div>
      <div class="card plus"><span class="k">☆ {TARGET_YEAR}년 돈의 흐름 — {tg_y}({grp_y})의 해</span>
        <p class="tip">{esc(MONEY_YEAR[grp_y])}</p>
        <p class="tip" style="margin-top:2mm">지지 {yz} 속 기운은 {tg_yz}({grp_yz}) — {esc(MONEY_YEAR[grp_yz].split('. ')[0])}.</p></div>
      <div class="two">
        <div class="card"><span class="k">돈 흐름을 점검·기회로 삼을 달</span>{mchips(money_good)}</div>
        <div class="card"><span class="k">지출·약속을 한 번 더 볼 달</span>{mchips(money_care)}</div>
      </div>
      <div class="card"><span class="k">올해의 돈 습관 한 가지{' — ' + p['job'] + ' 기준' if p['job'] else ''}</span><p class="tip">{esc(money_habit)}</p></div>
      <p class="small">재물운은 오락·참고용 풀이예요. 투자·대출 등 실제 금전 결정은 전문가와 상의해 주세요.</p>
    """, wm="財")

    # ── 직업 · 일
    grp_cnt = {g: 0 for g in GROUP_INFO}
    for k in ("year", "month", "day", "time"):
        gz = p["pillars"][k]
        if not gz:
            continue
        if k != "day":
            grp_cnt[TG_GROUP[ten_god(p["stem"], gz[0])]] += 1
        grp_cnt[TG_GROUP[ten_god(p["stem"], ZHI_MAIN[gz[1]])]] += 1
    top_n = max(grp_cnt.values())
    top_grps = [g for g in GROUP_INFO if grp_cnt[g] == top_n][:2]
    grp_el = {"비겁": me_el, "식상": SHENG[me_el], "재성": KE[me_el],
              "관성": next(e for e in EL_ORDER if KE[e] == me_el), "인성": next(e for e in EL_ORDER if SHENG[e] == me_el)}
    field_els = list(dict.fromkeys([me_el] + [grp_el[g] for g in top_grps]))
    gmap = "".join(f'<div class="{"on" if g in top_grps else ""}"><b>{grp_cnt[g]}</b>{g}<br><span class="small">{GROUP_INFO[g]["plain"]}</span></div>' for g in GROUP_INFO)
    work_good = pick_months(p, Y, lambda gs, gz, rk, tg: (2 if gs in ("관성", "식상") else 0) + (1 if gz in ("관성", "식상") else 0))
    work_prep = pick_months(p, Y, lambda gs, gz, rk, tg: (2 if gs == "인성" else 0) + (1 if gz == "인성" else 0), top=2)
    add(f"""
      {E('직업 · 일')}<h1>일하는 방식과 {TARGET_YEAR}년의 일</h1>
      <p class="lead">원국 글자들이 '나'에게 어떤 십신인지 세어 보면, 내가 힘을 잘 쓰는 방식이 보여요. (일간 제외 · 지지는 본기 기준)</p>
      <div class="tg">{gmap}</div>
      <div class="card" style="margin-top:4mm"><span class="k">◆ 나의 일하는 스타일</span>
        <p class="tip">{esc(WORK_STYLE[p['stem']])} 원국에서는 {'·'.join(top_grps)}이 가장 많아요 — {esc(' / '.join(GROUP_INFO[g]['work'] for g in top_grps))}이 잘 맞는 편이에요.</p></div>
      <div class="card"><span class="k">◇ 전통적으로 연결해 보는 분야 (참고)</span>
        <p class="tip">{'<br>'.join(f'{e}({EL_KR[e]}) — {WORK_FIELD[e]}' for e in field_els)}</p></div>
      <div class="card plus"><span class="k">☆ {TARGET_YEAR}년 일의 흐름 — {tg_y}({grp_y})의 해</span>
        <p class="tip">{esc(WORK_YEAR[grp_y])} {esc(TG[tg_y]['work'].split('. ', 1)[-1])}</p></div>
      {('<div class="card plus"><span class="k">' + p['job'] + ' 기준 올해의 포인트</span><p class="tip">' + esc(JOB_FOCUS[p['job']][grp_y]) + ' / ' + esc(JOB_FOCUS[p['job']][grp_yz]) + '</p></div>') if p['job'] else ''}
      <div class="two">
        <div class="card"><span class="k">도전·제안하기 좋은 달</span>{mchips(work_good)}</div>
        <div class="card"><span class="k">공부·준비에 좋은 달</span>{mchips(work_prep)}</div>
      </div>
      <p class="small">이직·창업 같은 큰 결정은 사주보다 현실 조건이 먼저예요. 흐름을 참고하는 용도로만 써 주세요.</p>
    """, wm="業")

    # ── 열두 달 캘린더
    def cal_cell(x):
        m = x["m"]
        cls = {1: "good", -1: "care", 0: ""}[x["lv"]]
        lv = lambda v: f'<em class="{"c" if v < 0 else ""}">{LEVEL3[v]}</em>'
        extra = " · ".join(f"{nm} {lv(x[key])}" for key, nm in cols)
        rel = f" ({'·'.join(sorted(x['kinds']))})" if x["kinds"] else ""
        return (f'<div class="{cls}"><div class="hd"><b>{month_label(m)}</b><span>{m["gz"]}</span></div>'
                f'<div class="lv">종합 {lv(x["lv"])} · {extra}</div>'
                f'<p>{esc(TG[x["t1"]]["kw"])}{esc(rel)} — {esc(x["tip"])}</p></div>')
    top_m = max(ML, key=lambda x: x["score"])
    low_m = min(ML, key=lambda x: x["score"])
    focus = []
    for key, nm in cols:
        goods = [month_label(x["m"]) for x in ML if x[key] == 1][:3]
        focus.append(f"{nm}: {', '.join(goods) if goods else '두드러진 달 없음 — 꾸준함이 무기'}")
    add(f"""
      {E('열두 달')}<h1>{TARGET_YEAR}년 열두 달의 흐름</h1>
      <p class="lead">각 달의 간지(월건)가 내 일간·일지와 만나는 방식으로 '종합'과 관심 분야를 3단계로 표시했어요. 달은 양력 1일이 아니라 절기(입춘·경칩…)가 들어오는 날 바뀌어요.</p>
      <div class="cal">{''.join(cal_cell(x) for x in ML)}</div>
      <div class="card plus" style="margin-top:3.5mm"><dl class="sum">
        <dt>적극 활용할 달</dt><dd>{month_label(top_m['m'])}({top_m['m']['gz']}) — {esc(TG[top_m['t1']]['month'].split('. ')[0])}.</dd>
        <dt>신중할 달</dt><dd>{month_label(low_m['m'])}({low_m['m']['gz']}) — {esc(low_m['tip'])}</dd>
        <dt>분야별 좋은 달</dt><dd>{' / '.join(focus)}</dd></dl></div>
    """, wm="月")

    # ── 가까이할 것 · 줄일 것
    tot = {e: p["counts"][e] + plus.get(e, 0) for e in EL_ORDER}
    mn = min(tot.values())
    weak = sorted([e for e in EL_ORDER if tot[e] == mn], key=lambda e: p["counts"][e])[:2]
    mx = max(tot.values())
    over = [e for e in EL_ORDER if tot[e] >= 4] or ([e for e in EL_ORDER if tot[e] == mx] if mx >= 3 and list(tot.values()).count(mx) == 1 else [])
    luck_html = ""
    for e in weak:
        L = EL_LUCK[e]
        luck_html += (f'<p class="tip" style="margin-top:2mm"><b style="color:{EL_COLOR[e]}">{e}({EL_KR[e]}) 채우기</b> — {EL_SHORT[e]}</p>'
                      f'<div class="luck"><div><span>색</span><b>{EL_LIFE[e]["color"]}</b></div><div><span>숫자</span><b>{L["num"]}</b></div>'
                      f'<div><span>방향</span><b>{L["dir"]}</b></div><div><span>맛</span><b>{L["taste"]}</b></div>'
                      f'<div><span>시간·계절</span><b>{L["season"]}</b></div><div><span>활동</span><b>{EL_LIFE[e]["act"].split("·")[0]}</b></div></div>')
    care_ms = [(m, [r[0] for r in branch_rels(p["branch"], m["gz"][1]) if r[0] in REL_MONTH_CARE]) for m in Y["months"]]
    care_ms = [(m, ks) for m, ks in care_ms if ks][:3]
    care_html = "".join(f'<span class="chip">{month_label(m)} · {REL_MONTH_CARE[ks[0]]}</span>' for m, ks in care_ms) or '<span class="small">일지와 부딪히는 달이 없어요.</span>'
    over_txt = (f"원국과 {Y['gz']}년을 합치면 {els_txt(over)} 기운이 가장 많아요. 넘치는 기운은 이런 습관으로 드러나기 쉬워요 — "
                + " / ".join(EL_OVER[e] for e in over) + ".") if over else "오행이 한쪽으로 크게 넘치지는 않아요. 지금의 균형을 지키는 게 가장 좋은 관리예요."
    add(f"""
      {E('올해의 처방')}<h1>{TARGET_YEAR}년, 가까이할 것 · 줄일 것</h1>
      <p class="lead">원국과 {Y['gz']}년 기운을 합쳐서 <b style="color:var(--gold2)">비어 있는 기운은 채우고, 넘치는 기운은 덜어 내는</b> 방향으로 골랐어요. 오행의 전통 상징을 가볍게 활용한 생활 팁이에요.</p>
      <div class="card plus"><span class="k">＋ 가까이하면 좋은 것</span>
        <p class="tip">올해 가장 약한 기운은 {els_txt(weak)}이에요. 일상에서 이 기운을 조금씩 더해 보세요.</p>
        {luck_html}
        <p class="tip" style="margin-top:3mm"><b style="color:var(--gold2)">{tg_y}의 해에 어울리는 것</b> — {esc(TG_NEAR[tg_y])}</p></div>
      <div class="card minus"><span class="k">－ 줄이면 좋은 것</span>
        <p class="tip">{esc(over_txt)}</p>
        <p class="tip" style="margin-top:2mm"><b style="color:var(--gold2)">{tg_y}의 해에 조심할 습관</b> — {esc(TG_AVOID[tg_y])}</p>
        <p class="tip" style="margin-top:2mm"><b style="color:var(--gold2)">{gz_kr(p['day'])}일주가 기억할 점</b> — {esc(st['care'])}</p></div>
      <div class="card"><span class="k">몸과 마음 관리 — 생활관리운 {LEVEL5[RT['생활관리운'][0]]}</span><p class="tip">{esc(LIFE_CARE[tg_y])}</p>
        <p class="small" style="margin-top:1mm">특정 질환을 예측하지 않아요. 건강은 실제 검진과 의료진 판단이 우선이에요.</p></div>
    """, wm="福")

    # ── 잘 어울리는 사람
    he_partner = next(next(iter(pr - {p["stem"]})) for pr in GAN_HE if p["stem"] in pr)
    liuhe_b = next(next(iter(pr - {p["branch"]})) for pr in LIUHE if p["branch"] in pr)
    trio = next(t for t in SANHE if p["branch"] in t)
    sanhe_b = [z for z in trio if z != p["branch"]]
    chong_b = next(next(iter(pr - {p["branch"]})) for pr in CHONG if p["branch"] in pr)
    yb = p["pillars"]["year"][1]
    y_liuhe = next(next(iter(pr - {yb})) for pr in LIUHE if yb in pr)
    y_trio = [z for z in next(t for t in SANHE if yb in t) if z != yb]
    y_chong = next(next(iter(pr - {yb})) for pr in CHONG if yb in pr)
    nat_mn = min(p["counts"].values())
    need = [e for e in EL_ORDER if p["counts"][e] == nat_mn][:2]
    need_stems = [g for g in GAN if GAN_EL[g] in need]
    ani = lambda z: f"{BRANCH[z]['animal']}({z})"
    add(f"""
      {E('잘 어울리는 사람')}<h1>{esc(N)}과 잘 맞는 사람</h1>
      <p class="lead">상대의 일주나 띠를 알면 아래에서 찾아보세요. 궁합은 '맞다·안 맞다'가 아니라 서로 어떤 기운을 주고받는지 보는 거예요.</p>
      <div class="mate">
        <div class="card plus"><span class="k">끌림의 짝 — 천간합</span><div class="big">{he_partner} {STEM_NAME[he_partner]}</div>
          <p class="small">내 일간 {jo(p['stem'],'과','와')} 합을 이루는 일간이에요. 상대 일주의 첫 글자가 {jo(he_partner,'이면','면')} 자연스럽게 끌리는 사이로 봐요.</p></div>
        <div class="card plus"><span class="k">편안한 짝 — 육합 · 삼합</span><div class="big">{ani(liuhe_b)} · {' · '.join(ani(z) for z in sanhe_b)}</div>
          <p class="small">내 일지 {p['branch']}와 합을 이루는 글자예요. 상대의 일지(일주 둘째 글자)나 띠가 이 글자면 생활의 합이 잘 맞는 편으로 봐요.</p></div>
        <div class="card"><span class="k">부족함을 채워 주는 사람</span><div class="big">{' · '.join(STEM_NAME[g] for g in need_stems)}</div>
          <p class="small">내 원국에 적은 {els_txt(need)} 기운을 일간으로 가진 사람이에요. 내가 갖지 못한 면을 보여 줘서 배울 점이 많은 사이예요.</p></div>
        <div class="card"><span class="k">자극을 주는 사이 — 충</span><div class="big">{ani(chong_b)}</div>
          <p class="small">내 일지와 마주 보는 글자예요. 성향이 달라 부딪힐 수 있지만, 서로를 움직이게 하는 '자극제'가 되기도 해요.</p></div>
      </div>
      <div class="card"><span class="k">내 띠({BRANCH[yb]['animal']}띠) 기준으로 보면</span>
        <p class="tip">잘 맞는 띠: {ani(y_liuhe)} · {' · '.join(ani(z) for z in y_trio)} &nbsp;/&nbsp; 서로 자극이 되는 띠: {ani(y_chong)}</p>
        <p class="small">띠(년지)는 사회·바깥 관계, 일지는 가까운 관계를 볼 때 더 참고해요.</p></div>
      <div class="card plus"><span class="k">☆ {TARGET_YEAR}년에 가까이하면 좋은 사람</span>
        <p class="tip">{esc(PEOPLE_YEAR[grp_y])}. {esc(TG[tg_y]['rel'])}</p></div>
    """, wm="合")

    # ── 마무리
    s1 = f"{esc(N)}의 가장 큰 무기는 {esc(jo(st['strength'], '이에요', '예요'))}."
    s2 = {"약": "다만 원국의 힘이 섬세한 편이라, 올해는 혼자 버티기보다 도움을 받아들이는 쪽이 결과가 좋아요.",
          "강": "타고난 힘이 넘치는 편이라, 올해는 그 힘을 여러 곳에 흩기보다 한곳에 모아 쓰는 게 관건이에요.",
          "중": "균형이 잘 잡힌 사주라, 무리하게 바꾸기보다 지금의 리듬을 지키는 쪽이 이득이에요."}[S["kind"]]
    s3 = f"{TARGET_YEAR}년은 {tg_y}의 해예요. {TG[tg_y]['month'].split('. ')[-1]}"
    s4 = f" 지금은 {phase_now[0]}의 한가운데라, 올해 쌓는 것이 {phase_now[1]}년부터 이어질 다음 흐름의 바탕이 돼요." if phase_now else ""
    s5 = f" 운은 방향을 알려 줄 뿐, 걸어가는 건 {esc(N)}이에요. 올해도 충분히 잘 해낼 거예요."
    add(f"""
      {E('총평')}<h1>다가올 시간을 준비하며</h1>
      <p class="serif" style="font-size:12.5pt;color:var(--gold2);line-height:1.9;margin:2mm 0 6mm">{esc(jo(st['img'],'이','가'))} 만나는 {esc(STEM[yg]['img'])}과 {esc(BRANCH[yz]['img'])}의 해.</p>
      <div class="card"><dl class="sum">
        <dt>가장 큰 기회</dt><dd>{best} — {esc(RT[best][1])}</dd>
        <dt>신경 쓸 부분</dt><dd>{worst} — {esc(RT[worst][1])}</dd>
        <dt>꼭 해 볼 것</dt><dd>{esc(TG_NEAR[tg_y])}</dd>
        <dt>줄일 것</dt><dd>{esc(TG_AVOID[tg_y])}</dd>
        <dt>올해의 목표</dt><dd>'{esc(kws[0][0])}' — {esc(TG[tg_y]['work'].split('. ')[0])}.</dd></dl></div>
      <div class="card plus"><span class="k">마지막 한마디</span>
        <p class="serif" style="font-size:11pt;line-height:1.95">{s1} {esc(s2)} {esc(s3)}{esc(s4)}{s5}</p></div>
      <div class="notice" style="margin-top:4mm">
        <span class="k">안내</span>
        <p class="small">· 이 리포트는 명리학의 일주·십신·합충·오행·대운 이론을 바탕으로 <b style="color:var(--gold2)">재미와 참고를 위해</b> 만든 콘텐츠예요. 미래를 예언하거나 특정 사건·날짜를 단정하지 않아요.<br>
        · 건강·투자·법률·사업 등 중요한 결정은 실제 자료와 해당 분야 전문가의 판단을 우선해 주세요.<br>
        · 사주 계산은 만세력 코드로 자동 산출했으며, 태어난 시간·지역에 따라 시주와 대운 시점이 달라질 수 있어요.<br>
        · 리포트에 담긴 개인정보(생년월일 등)는 리포트 제작에만 사용해요.</p>
      </div>
      <div style="position:absolute;bottom:22mm;left:0;right:0;text-align:center">
        <div class="serif" style="color:var(--gold);letter-spacing:.4em;font-size:10pt">60 ILJU DOGAM</div>
        <div class="small" style="margin-top:2mm">내 일주가 궁금하다면 · 인스타그램 @ilju_dogam</div></div>
    """, wm="春")
    return wrap_html(pages, mode, full, hidden)


SAMPLE = {"name": "서연", "gender": "여", "date": "1994-03-21", "calendar": "solar", "time": None}


def main():
    args = sys.argv[1:]
    out = Path("newyear_report.pdf")
    if "-o" in args:
        i = args.index("-o")
        out = Path(args[i + 1])
        del args[i:i + 2]
    data = json.loads(Path(args[0]).read_text(encoding="utf-8")) if args else SAMPLE
    p = calc_person(data)
    Y = calc_year()
    pp = p["pillars"]
    print(f"[{p['nick']}] {p['solar']} / {p['lunar']} → {pp['year']}年 {pp['month']}月 {pp['day']}日 {pp['time'] or '--'}時 | 오행 {p['counts']} | {p['check']}")
    print(f"[{TARGET_YEAR}] 세운 {Y['gz']} (입춘 {Y['lichun']:%Y-%m-%d %H:%M} KST, 전년 {Y['prev']}) 납음 {Y['nayin']}")
    for m in Y["months"]:
        print(f"   {m['gz']} {m['jie']} {m['start']:%Y-%m-%d %H:%M} ~ {m['end']:%Y-%m-%d} | 천간 {ten_god(p['stem'], m['gz'][0])} | 일지관계 {[r[1] for r in branch_rels(p['branch'], m['gz'][1])]}")
    print(f"   일간↔세운천간: {ten_god(p['stem'], Y['gz'][0])} {stem_rels(p['stem'], Y['gz'][0])} | 일지↔세운지지: {branch_rels(p['branch'], Y['gz'][1])}")
    doc = render(p, Y)
    html_path = out.with_suffix(".html")
    html_path.write_text(doc, encoding="utf-8")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        pg = br.new_page()
        pg.goto(html_path.resolve().as_uri())
        pg.wait_for_timeout(500)
        pg.pdf(path=str(out), format="A4", print_background=True, prefer_css_page_size=True)
        br.close()
    print("PDF:", out.resolve())


if __name__ == "__main__":
    main()
