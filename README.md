# 병원 학술행사 달력

서울권 대학병원(삼성서울병원·서울아산병원·한양대학교병원)의 학술행사를 하루 한 번 모아서 **달력 + 날짜별 목록**으로 보여주는 정적 웹사이트입니다.

- 화면: `docs/index.html` (빌드 없음, `docs/events.json`을 읽어서 그림)
- 수집: `scraper/` (Python, requests + BeautifulSoup)
- 자동화: `.github/workflows/scrape.yml` (매일 06:17 KST 실행 → `docs/events.json` 커밋)

## 처음 한 번 설정

1. 이 폴더를 GitHub 저장소로 올립니다.
2. 저장소 **Settings → Pages → Build and deployment**: Source = *Deploy from a branch*, Branch = `main`, Folder = `/docs`.
3. **Actions 탭 → 행사 수집 → Run workflow** 로 한 번 실행합니다.
4. 실행 로그에서 병원별 결과를 확인합니다.
   - `[ok]   서울아산병원: 12건` → 정상
   - `[fail] ...` → 해당 병원 파서가 현재 HTML과 맞지 않는 것. 같은 실행의 **Artifacts → raw-html** 을 내려받아 `scraper/<병원>.py`의 정규식/선택자를 고치면 됩니다.
5. 이후에는 매일 자동으로 갱신됩니다.

## 로컬에서 실행

```bash
pip install -r scraper/requirements.txt
python tests/test_parsers.py                      # 파서 단위 테스트
python scraper/run.py --out docs/events.json --dump raw-html
python -m http.server -d docs 8000                # http://localhost:8000
```

## 병원 추가하기

1. `scraper/<병원>.py` 를 만들고 `KEY`, `NAME`, `scrape() -> list[Event]` 를 구현합니다 (`samsung.py` 참고).
2. `scraper/run.py` 의 `SOURCES` 에 한 줄 추가합니다. 목록 순서가 화면 색상 순서입니다.
3. `tests/fixtures/` 에 목록 HTML 샘플을 두고 `tests/test_parsers.py` 에 테스트를 추가합니다.

## 알아둘 점

- 한 병원이 실패해도 나머지는 계속 수집하고, 실패한 병원의 기존 데이터는 유지됩니다. 모든 병원이 실패하면 워크플로가 실패로 표시됩니다.
- 행사는 ID 기준으로 합쳐 저장하므로, 병원이 게시물을 삭제하거나 취소해도 이 사이트의 기록은 남습니다. 180일이 지나면 정리됩니다.
- 서울대병원·서울성모·고대안암·경희대·이대는 통합 학술행사 게시판이 없거나 목록이 오래되어 제외했습니다. 세브란스는 게시판이 갱신되지 않고 있습니다.
- 수집은 병원당 2~3개 페이지, 요청 사이 1초 간격으로 하루 한 번만 합니다. 각 병원의 이용약관과 robots.txt를 확인하고 사용하세요.
- 일정은 바뀔 수 있으므로 화면의 원문 링크에서 최종 확인하세요.
