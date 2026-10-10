"""아주대학교병원 '강좌·교육' 게시판의 학술행사 탭.

목록: https://hosp.ajoumc.or.kr/board/commBoardHLectureList.do?searchCode=004002000&page=N
상세: .../commBoardHLectureView.do?no=번호  (목록 링크가 javascript:page_move('commBoardHLectureView', { no: N }) 형태)

한 행에 구분(학술행사/건강강좌), 제목, 일시(2026-06-04(목) 13:40-17:00), 장소, 주관 부서, 상태가 함께 들어 있다.
"""
from __future__ import annotations

import re

from common import Event, classify, clean, fetch, hhmm, item_container, make_soup, ymd

KEY = "ajou"
NAME = "아주대학교병원"
BASE = "https://hosp.ajoumc.or.kr"
LIST_URL = BASE + "/board/commBoardHLectureList.do"
PAGES = 2

_NO = re.compile(r"commBoardHLectureView\D*?(?:no\s*[:=]\s*)(\d+)")
_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})\s*(?:\([^)]*\))?")
_TIMES = re.compile(r"\s*(\d{1,2}):(\d{2})\s*[-~–]\s*(\d{1,2}):(\d{2})")
_END_DAY = re.compile(r"\s*~\s*(?:(\d{4})-(\d{2})-)?(\d{1,2})\s*(?:\([^)]*\))?")
_TAGS = re.compile(r"^(?:(?:학술행사|건강강좌|전체|종료|접수중|접수예정|접수마감|마감|진행중)\s*)+")
_STATUS = re.compile(r"\s*(?:종료|접수중|접수예정|접수마감|마감|진행중)\s*$")
_ORG = re.compile(r"(\S*(?:학교실|센터|연구소|사업단|교육연구단|위원회|팀|과))$")


def _title(anchor, box, text: str) -> str:
    own = clean(anchor.get_text(" "))
    if own and not _DATE.search(own):
        return _TAGS.sub("", own).strip()
    head = _TAGS.sub("", text[: _DATE.search(text).start()]).strip()
    if head:
        return head
    strong = box.select_one("strong, b, .tit, .title, .subject, dt, h3, h4")
    return clean(strong.get_text()) if strong else ""


def parse_list(html: str) -> list[Event]:
    soup = make_soup(html)
    events: dict[str, Event] = {}
    for a in soup.find_all("a", href=True):
        m = _NO.search(a["href"])
        if not m or m.group(1) in events:
            continue
        no = m.group(1)
        box = item_container(a, _NO)
        text = clean(box.get_text(" "))
        d = _DATE.search(text)
        if not d:
            continue
        try:
            start = ymd(*d.groups())
        except ValueError:
            continue
        title = _title(a, box, text)
        if not title:
            continue

        rest = text[d.end():]
        end, st, et = start, "", ""
        tm = _TIMES.match(rest)
        if tm:
            st, et = hhmm(*tm.groups()[:2]), hhmm(*tm.groups()[2:])
            rest = rest[tm.end():]
        else:
            ed = _END_DAY.match(rest)
            if ed:
                try:
                    end = ymd(ed.group(1) or start[:4], ed.group(2) or start[5:7], ed.group(3))
                except ValueError:
                    pass
                rest = rest[ed.end():]
        rest = _STATUS.sub("", clean(rest))
        org = _ORG.search(rest)
        organizer = org.group(1) if org else ""
        place = clean(rest[: org.start()] if org else rest)
        place = re.sub(r"^장\s*소\s*[:：]\s*", "", place)
        place = re.sub(r"\s*(?:주\s*관|주\s*최)\s*[:：]?\s*$", "", place)

        public = text.lstrip().startswith("건강강좌") or classify(title) == "건강강좌"
        events[no] = Event(
            id=f"{KEY}-{no}", hospital=KEY, title=title,
            start_date=start, end_date=end, start_time=st, end_time=et,
            location=place[:60], organizer=organizer,
            url=f"{BASE}/board/commBoardHLectureView.do?no={no}",
            kind="건강강좌" if public else "학술",
        )
    return list(events.values())


def scrape() -> list[Event]:
    found: dict[str, Event] = {}
    for page in range(1, PAGES + 1):
        html = fetch(LIST_URL, params={"searchCode": "004002000", "page": page}, name=f"{KEY}-list-{page}")
        before = len(found)
        for ev in parse_list(html):
            found.setdefault(ev.id, ev)
        if len(found) == before:
            break
    if not found:
        raise RuntimeError("아주대학교병원: 목록에서 행사를 찾지 못했습니다 (페이지 구조가 바뀌었을 수 있음)")
    return list(found.values())
