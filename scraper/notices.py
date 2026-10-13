"""서브인턴십·전공의 모집 공고 수집.

출처
- 서울아산병원 교육수련 공지: https://edtr.amc.seoul.kr/education/service/notice/list.do
  (본문 날짜는 이미지에만 있어 게시일과 링크만 쓴다)
- 서울대학교병원 채용공고: https://www.snuh.org/about/news/recruit/recruList.do?searchWord=...
  (목록에 모집기간이 있어 신청 마감 D-day를 만들 수 있다)

결과는 docs/notices.json 에 저장한다. 행사(events.json)와 달리 날짜가 아니라 공고 단위다.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from urllib.parse import urljoin

from common import clean, fetch, item_container, make_soup, ymd

SUBINTERN = "subintern"
RESIDENCY = "residency"

_SUB = re.compile(r"서브\s*인턴|subintern|선택\s*실습|elective", re.I)
_RES = re.compile(r"전공의|레지던트|인턴|전임의|펠로우|fellow", re.I)
_RECRUIT = re.compile(r"모집|선발|프로그램|공고")
_SKIP = re.compile(r"합격|지원\s*현황|기숙사|결과|장애인|직원|체험형|간호|면접\s*일정|필기시험")
_DATE = re.compile(r"(20\d{2})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})")


@dataclass
class Notice:
    id: str
    hospital: str
    category: str
    title: str
    url: str
    posted: str = ""
    reg_start: str = ""
    reg_end: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def categorize(title: str) -> str | None:
    if _SKIP.search(title) or not _RECRUIT.search(title):
        return None
    if _SUB.search(title):
        return SUBINTERN
    if _RES.search(title):
        return RESIDENCY
    return None


def _dates(text: str) -> list[str]:
    out = []
    for m in _DATE.finditer(text):
        try:
            out.append(ymd(*m.groups()))
        except ValueError:
            pass
    return out


def _fix_span(start: str, end: str) -> str:
    """'2025-12-12 ~ 2026-12-19'처럼 마감 연도가 1년 밀려 적힌 경우를 바로잡는다.

    접수기간이 반년을 넘는 일은 없으므로, 그런 경우 시작 연도로 맞춘다.
    """
    from datetime import date
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    if (e - s).days > 180:
        try:
            fixed = e.replace(year=s.year)
        except ValueError:
            return end
        if fixed >= s:
            return fixed.isoformat()
    return end


# ---------------- 서울아산병원 ----------------
AMC_KEY = "amc"
AMC_LIST = "https://edtr.amc.seoul.kr/education/service/notice/list.do"
_AMC_SEQ = re.compile(r"notice/view\.do\?seq=(\d+)")


def parse_amc(html: str) -> list[Notice]:
    out: dict[str, Notice] = {}
    for a in make_soup(html).find_all("a", href=True):
        m = _AMC_SEQ.search(a["href"])
        if not m or m.group(1) in out:
            continue
        title = clean(a.get_text(" "))
        cat = categorize(title)
        if not cat:
            continue
        dates = _dates(clean(item_container(a, _AMC_SEQ).get_text(" ")))
        out[m.group(1)] = Notice(
            id=f"amc-n{m.group(1)}", hospital=AMC_KEY, category=cat, title=title,
            url=urljoin(AMC_LIST, a["href"]), posted=dates[0] if dates else "",
        )
    return list(out.values())


def scrape_amc() -> list[Notice]:
    return parse_amc(fetch(AMC_LIST, name="amc-notice-1"))


# ---------------- 서울대학교병원 ----------------
SNUH_KEY = "snuh"
SNUH_LIST = "https://www.snuh.org/about/news/recruit/recruList.do"
_SNUH_ID = re.compile(r"recruit_id\D{0,4}(\d+)")
SNUH_QUERIES = ("서브인턴", "서브 인턴", "전공의", "레지던트", "인턴")


def parse_snuh(html: str) -> list[Notice]:
    out: dict[str, Notice] = {}
    for a in make_soup(html).find_all("a", href=True):
        m = _SNUH_ID.search(a["href"]) or _SNUH_ID.search(a.get("onclick", ""))
        if not m or m.group(1) in out:
            continue
        title = clean(a.get_text(" "))
        cat = categorize(title)
        if not cat:
            continue
        dates = _dates(clean(item_container(a, _SNUH_ID).get_text(" ")))
        rid = m.group(1)
        n = Notice(
            id=f"snuh-n{rid}", hospital=SNUH_KEY, category=cat, title=title,
            url=f"https://www.snuh.org/about/news/recruit/recruView.do?recruit_id={rid}",
        )
        if len(dates) >= 2:
            n.reg_start, n.reg_end = dates[0], dates[1]
            n.reg_end = _fix_span(n.reg_start, n.reg_end)
            n.posted = n.reg_start
        elif dates:
            n.posted = dates[0]
        out[rid] = n
    return list(out.values())


def scrape_snuh() -> list[Notice]:
    found: dict[str, Notice] = {}
    for i, q in enumerate(SNUH_QUERIES):
        html = fetch(SNUH_LIST, params={"searchKey": "", "searchWord": q}, name=f"snuh-recruit-{i}")
        for n in parse_snuh(html):
            found.setdefault(n.id, n)
    return list(found.values())


SOURCES = [
    (AMC_KEY, "서울아산병원", AMC_LIST, scrape_amc),
    (SNUH_KEY, "서울대학교병원", SNUH_LIST, scrape_snuh),
]
