"""을지대학교병원(노원·의정부) 진료협력 공지에 올라오는 연수강좌.

목록: https://refer.eulji.or.kr/news/news_pg02_01.jsp?board_code=BOARD_126&str_page=N
상세: .../news_pg02_02.jsp?board_code=BOARD_126&board_sequence=번호

학술행사 전용 게시판이 없고 일반 공지에 섞여 있다. 제목에 '(일시: 2026.10.23(금), 18:30~21:00)'가
들어 있는 연수강좌·심포지엄만 골라 쓴다. 장소는 포스터 이미지에만 있어서 비워 둔다.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from common import Event, classify, clean, fetch, hhmm, make_soup, ymd

KEY = "eulji"
NAME = "을지대학교병원"
BASE = "https://refer.eulji.or.kr"
LIST_URL = BASE + "/news/news_pg02_01.jsp"
BOARD = "BOARD_126"
PAGES = 3  # 한 페이지 10건. 최근 30건이면 앞으로의 연수강좌를 덮는다

_SEQ = re.compile(r"board_sequence=(\d+)")
_TOPIC = re.compile(r"연수강좌|심포지엄|심포지움|학술|세미나|워크숍|워크샵|컨퍼런스|학술대회")
_WHEN = re.compile(
    r"일시\s*[:：]\s*(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?\s*(?:\([^)]*\))?"
    r"(?:\s*,?\s*(\d{1,2}):(\d{2})\s*(?:[~\-–]\s*(\d{1,2}):(\d{2}))?)?"
)
_WHEN_PAREN = re.compile(r"\s*\(\s*일시\s*[:：](?:[^()]|\([^()]*\))*\)")


def parse_list(html: str) -> list[tuple[str, str, str]]:
    """(번호, 제목, 상세주소) 목록. 게시판의 모든 행을 돌려준다."""
    rows: dict[str, tuple[str, str, str]] = {}
    for a in make_soup(html).find_all("a", href=True):
        m = _SEQ.search(a["href"])
        if not m or m.group(1) in rows:
            continue
        title = clean(a.get_text(" "))
        if title:
            rows[m.group(1)] = (m.group(1), title, urljoin(LIST_URL, a["href"]))
    return list(rows.values())


def to_event(seq: str, title: str, url: str) -> Event | None:
    if not _TOPIC.search(title):
        return None
    w = _WHEN.search(title)
    if not w:
        return None
    y, mo, da, sh, sm, eh, em = w.groups()
    try:
        start = ymd(y, mo, da)
    except ValueError:
        return None
    short = clean(_WHEN_PAREN.sub("", title))
    short = re.sub(r"\s*안내\s*$", "", short) or title
    return Event(
        id=f"{KEY}-{seq}", hospital=KEY, title=short,
        start_date=start, end_date=start,
        start_time=hhmm(sh, sm) if sh else "",
        end_time=hhmm(eh, em) if eh else "",
        url=url, kind=classify(short),
    )


def scrape() -> list[Event]:
    seen: set[str] = set()
    events: dict[str, Event] = {}
    for page in range(1, PAGES + 1):
        html = fetch(LIST_URL, params={"board_code": BOARD, "str_page": page}, name=f"{KEY}-list-{page}")
        new_rows = [r for r in parse_list(html) if r[0] not in seen]
        if not new_rows:
            break
        for seq, title, url in new_rows:
            seen.add(seq)
            ev = to_event(seq, title, url)
            if ev:
                events[ev.id] = ev
    if not seen:
        raise RuntimeError("을지대학교병원: 게시판에서 글을 찾지 못했습니다 (페이지 구조가 바뀌었을 수 있음)")
    return list(events.values())  # 연수강좌 글이 없는 기간이면 빈 목록도 정상이다
