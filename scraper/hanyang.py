"""한양대학교병원 학술행사.

목록: https://seoul.hyumc.com/hyumc/board/seminarBoardList.do?page=N
상세: .../seminarBoardView.do?no=번호
(목록 링크가 javascript:page_move('seminarBoardView', { no: 438 }) 형태다)
"""
from __future__ import annotations

import re

from common import Event, classify, clean, fetch, hhmm, make_soup, ymd

KEY = "hyumc"
NAME = "한양대학교병원"
BASE = "https://seoul.hyumc.com"
LIST_URL = BASE + "/hyumc/board/seminarBoardList.do"
PAGES = 2  # 글 번호 내림차순이라 최근 20건이면 앞으로의 일정을 덮는다

_NO = re.compile(r"seminarBoardView.*?no:\s*(\d+)")
_DATE = re.compile(
    r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*"
    r"(?:(\d{1,2}):(\d{2}))?(?:\s*~\s*(\d{1,2}):(\d{2}))?"
)
_LEAD = re.compile(r"^(?:D-\d+|D-day|D\+\d+|종료|진행중|예정|접수중)\s*")
_PLACE = re.compile(r"장\s*소\s*[:：]\s*(.+?)(?=\s+(?:[-○▶●■]|주\s*제|사전|참가|연\s*사|대\s*상|주\s*관|비\s*용)|$)")
_ORG = re.compile(r"주\s*[관최]\s*[:：]\s*(\S+)")


_URL = re.compile(r"https?://\S*")
_NOISE = re.compile(r"\(\s*(?:링크|클릭|바로가기)\s*\)|[☞▶▷→※●■○◆◇★☆]")


def _clean_place(raw: str) -> str:
    """'온라인 HMP 세미나 (링크) ☞ https://...' 같은 값에서 안내 문구와 주소를 걷어낸다."""
    text = _URL.sub("", raw)
    text = _NOISE.sub(" ", text)
    return clean(text).strip(" -,:;")[:60]


def _title(anchor, text: str) -> str:
    strong = anchor.select_one("strong, b, .tit, .title, .subject, dt")
    if strong and clean(strong.get_text()):
        return clean(strong.get_text())
    body = _LEAD.sub("", text)
    cut = body.find("안녕하십니까")
    return clean(body[:cut] if cut > 0 else body[:80])


def _fix_year(title: str, start: str, end: str) -> tuple[str, str]:
    """게시판 일시 칸에 전년도가 잘못 적힌 경우를 제목의 연도로 바로잡는다.

    예: 제목은 '2026 ... 연수강좌', 일시 칸은 '2025년 11월 28일'.
    """
    m = re.match(r"\s*(20\d{2})\b", title)
    if m and int(m.group(1)) != int(start[:4]) and abs(int(m.group(1)) - int(start[:4])) == 1:
        year = m.group(1)
        return year + start[4:], year + end[4:]
    return start, end


def parse_list(html: str) -> list[Event]:
    soup = make_soup(html)
    events: dict[str, Event] = {}
    for a in soup.find_all("a", href=True):
        m = _NO.search(a["href"])
        if not m or m.group(1) in events:
            continue
        no = m.group(1)
        text = clean(a.get_text(" "))
        dates = list(_DATE.finditer(text))
        if not dates:
            continue
        d = dates[-1]  # 일시는 항상 글 끝에 붙어 있다
        y, mo, da, sh, sm, eh, em = d.groups()
        try:
            start = ymd(y, mo, da)
        except ValueError:
            continue
        title = _title(a, text)
        if not title:
            continue
        start, end = _fix_year(title, start, start)
        place = _PLACE.search(text)
        org = _ORG.search(text)
        events[no] = Event(
            id=f"{KEY}-{no}", hospital=KEY, title=title,
            start_date=start, end_date=end,
            start_time=hhmm(sh, sm) if sh else "",
            end_time=hhmm(eh, em) if eh else "",
            location=_clean_place(place.group(1)) if place else "",
            organizer=clean(org.group(1)) if org else "",
            url=f"{BASE}/hyumc/board/seminarBoardView.do?no={no}",
            kind=classify(title),
        )
    return list(events.values())


def scrape() -> list[Event]:
    found: dict[str, Event] = {}
    for page in range(1, PAGES + 1):
        html = fetch(LIST_URL, params={"page": page}, name=f"{KEY}-list-{page}")
        for ev in parse_list(html):
            found.setdefault(ev.id, ev)
    if not found:
        raise RuntimeError("한양대학교병원: 목록에서 행사를 찾지 못했습니다 (페이지 구조가 바뀌었을 수 있음)")
    return list(found.values())
