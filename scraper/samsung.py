"""삼성서울병원 학술행사.

목록: https://www.samsunghospital.com/home/info/scienceList.do?cPage=N
상세: .../scienceView.do?seq=번호
"""
from __future__ import annotations

import re

from common import Event, classify, clean, fetch, hhmm, item_container, make_soup

KEY = "smc"
NAME = "삼성서울병원"
BASE = "https://www.samsunghospital.com"
LIST_URL = BASE + "/home/info/scienceList.do"
PAGES = 3  # 한 페이지에 10건, 최근 30건이면 앞으로의 일정을 충분히 덮는다

_SEQ = re.compile(r"seq=(\d+)")
_TIME = re.compile(
    r"시간\s*:\s*(\d{4}-\d{2}-\d{2})\s*(?:(\d{1,2})\s*:\s*(\d{2}))?"
    r"(?:\s*~\s*(?:(\d{4}-\d{2}-\d{2})\s*(?:(\d{1,2})\s*:\s*(\d{2}))?)?)?"
)
_PLACE = re.compile(r"장소\s*:\s*(.+?)(?=\s*(?:신청중|신청마감|신청예정|신청기간|접수|$))")
_REG = re.compile(r"신청기간\s*:\s*(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})")


def parse_list(html: str) -> list[Event]:
    soup = make_soup(html)
    events: dict[str, Event] = {}
    for a in soup.select('a[href*="scienceView.do"]'):
        m = _SEQ.search(a["href"])
        if not m or m.group(1) in events:
            continue
        seq = m.group(1)
        box = item_container(a, _SEQ)
        text = clean(box.get_text(" "))
        t = _TIME.search(text)
        if not t:
            continue
        title = clean(a.get_text()) or clean((box.find(["h3", "h4", "strong"]) or a).get_text())
        if not title:
            continue
        start_date, sh, sm, end_date, eh, em = t.groups()
        place = _PLACE.search(text)
        reg = _REG.search(text)
        events[seq] = Event(
            id=f"{KEY}-{seq}",
            hospital=KEY,
            title=title,
            start_date=start_date,
            end_date=end_date or start_date,
            start_time=hhmm(sh, sm) if sh else "",
            end_time=hhmm(eh, em) if eh else "",
            location=clean(place.group(1)) if place else "",
            organizer="",
            url=f"{BASE}/home/info/scienceView.do?seq={seq}",
            reg_start=reg.group(1) if reg else "",
            reg_end=reg.group(2) if reg else "",
            kind=classify(title),
        )
    return list(events.values())


def scrape() -> list[Event]:
    found: dict[str, Event] = {}
    for page in range(1, PAGES + 1):
        html = fetch(LIST_URL, params={"cPage": page}, name=f"{KEY}-list-{page}")
        before = len(found)
        for ev in parse_list(html):
            found.setdefault(ev.id, ev)
        if len(found) == before:  # 새 항목이 없으면 더 볼 필요 없다
            break
    if not found:
        raise RuntimeError("삼성서울병원: 목록에서 행사를 찾지 못했습니다 (페이지 구조가 바뀌었을 수 있음)")
    return list(found.values())
