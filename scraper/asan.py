"""서울아산병원 학술행사.

목록: https://www.amc.seoul.kr/asan/academy/event/eventList.do
상세: .../eventDetail.do?eventId=번호   (목록의 '조회' 링크는 사전등록 조회 화면이라 쓰지 않는다)
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime

from common import KST, Event, classify, clean, fetch, hhmm, make_soup, ymd

KEY = "amc"
NAME = "서울아산병원"
BASE = "https://www.amc.seoul.kr"
LIST_URL = BASE + "/asan/academy/event/eventList.do"
PAGES = 2  # 목록은 날짜 내림차순이라 1페이지에 앞으로의 일정이 대부분 들어 있다

_DATE = re.compile(r"행사일\s*:\s*(\d{4})\.(\d{1,2})\.(\d{1,2})(?:\s*\([^)]*\))?")
_TIMES = re.compile(r"\s*(\d{1,2}):(\d{2})\s*~\s*(\d{1,2}):(\d{2})")
_END_DATE = re.compile(r"\s*~\s*(?:(\d{4})\.)?(\d{1,2})\.(\d{1,2})")
_ORG = re.compile(r"주관\s*:\s*(.+?)\s*(?=\|?\s*행사일)")
_EVENT_ID = re.compile(r"eventId=(\d+)")
_PLACE = re.compile(r"장\s*소\s*:\s*(.+?)(?=\s*(?:위치\s*보기|일시\s*:|담당\s*연락처|주관\s*:|주최|$))")
_SKIP_LINKS = {"신청", "조회", "신청마감", "자세히보기", "참가신청", "신청접수중", "예정", "행사종료"}


def _items(soup):
    """'행사일'이 정확히 한 번 들어 있는 가장 바깥 li/tr 이 행사 한 건이다."""
    out = []
    for node in soup.find_all(["li", "tr"]):
        if clean(node.get_text(" ")).count("행사일") != 1:
            continue
        parent = node.find_parent(["li", "tr"])
        if parent is not None and clean(parent.get_text(" ")).count("행사일") == 1:
            continue
        out.append(node)
    return out


def parse_list(html: str) -> list[Event]:
    soup = make_soup(html)
    events: dict[str, Event] = {}
    for box in _items(soup):
        text = clean(box.get_text(" "))
        d = _DATE.search(text)
        if not d:
            continue
        y, mo, da = map(int, d.groups())
        try:
            start_date = ymd(y, mo, da)
        except ValueError:
            continue

        end_date, start_time, end_time = start_date, "", ""
        rest = text[d.end():]
        tm = _TIMES.match(rest)
        if tm:
            start_time, end_time = hhmm(*tm.groups()[:2]), hhmm(*tm.groups()[2:])
        else:
            ed = _END_DATE.match(rest)
            if ed:
                ey = int(ed.group(1) or y)
                try:
                    end_date = ymd(ey, int(ed.group(2)), int(ed.group(3)))
                except ValueError:
                    pass

        title = ""
        for a in box.find_all("a"):
            label = clean(a.get_text())
            if label and label not in _SKIP_LINKS:
                title = label
                break
        if not title:
            continue

        org = _ORG.search(text)
        event_id = None
        for a in box.find_all("a", href=True):
            m = _EVENT_ID.search(a["href"])
            if m:
                event_id = m.group(1)
                break
        if event_id:
            uid, url = f"{KEY}-{event_id}", f"{BASE}/asan/academy/event/eventDetail.do?eventId={event_id}"
        else:  # 상세 링크가 없는 행사(예정)는 제목+날짜로 고유 번호를 만든다
            digest = hashlib.sha1(f"{title}|{start_date}".encode()).hexdigest()[:8]
            uid, url = f"{KEY}-x{digest}", LIST_URL

        events.setdefault(uid, Event(
            id=uid, hospital=KEY, title=title,
            start_date=start_date, end_date=end_date,
            start_time=start_time, end_time=end_time,
            location="", organizer=clean(org.group(1)) if org else "",
            url=url, kind=classify(title),
        ))
    return list(events.values())


def parse_detail(html: str) -> str:
    """상세 페이지에서 장소 한 줄을 꺼낸다. 없으면 빈 문자열."""
    text = clean(make_soup(html).get_text(" "))
    for m in _PLACE.finditer(text):
        place = clean(m.group(1))
        if place:
            return place[:60]
    return ""


def scrape(known: dict | None = None) -> list[Event]:
    """known: 이미 저장된 행사(id -> dict). 장소가 있는 행사는 상세 페이지를 다시 읽지 않는다."""
    found: dict[str, Event] = {}
    for page in range(1, PAGES + 1):
        params = {"pageIndex": page} if page > 1 else None
        html = fetch(LIST_URL, params=params, name=f"{KEY}-list-{page}")
        before = len(found)
        for ev in parse_list(html):
            found.setdefault(ev.id, ev)
        if len(found) == before:  # 2페이지 파라미터가 맞지 않으면 같은 목록이 오므로 여기서 멈춘다
            break
    if not found:
        raise RuntimeError("서울아산병원: 목록에서 행사를 찾지 못했습니다 (페이지 구조가 바뀌었을 수 있음)")

    # 장소는 상세 페이지에만 있다. 앞으로 열릴 행사만, 아직 장소를 모르는 것만 읽는다.
    today = datetime.now(KST).date().isoformat()
    known = known or {}
    for ev in found.values():
        old_place = (known.get(ev.id) or {}).get("location", "")
        if old_place:
            ev.location = old_place
            continue
        if ev.end_date < today or ev.url == LIST_URL:
            continue
        try:
            ev.location = parse_detail(fetch(ev.url, name=f"{KEY}-detail-{ev.id.split('-')[1]}"))
        except Exception as exc:  # noqa: BLE001 - 장소를 못 읽어도 행사 자체는 저장한다
            print(f"  (장소 건너뜀) {ev.id}: {exc}")
    return list(found.values())
