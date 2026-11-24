# 60일주 도감 · 내 일주 찾기

생년월일로 60일주 중 내 일주를 찾는 정적 사이트. `src/build.py`로 생성.

## 수정 방법
- 원본은 `_src/` (배포 제외). `cd _src && python3 build.py` → `../dist`가 생기면 그 내용을 저장소 루트에 복사해 커밋.
- 주소: https://ilju60.vercel.app (Vercel 프로젝트 ilju-dogam)
- 일주 계산: (JDN + 49) % 60, 2000-01-01 = 戊午. 음력 표는 한국천문연구원 기준.
