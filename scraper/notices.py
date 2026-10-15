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
_RECRUIT = re.compile(r"모집|선발|프로그램|공고|초빙")
_SKIP = re.compile(r"합격|지원\s*현황|경쟁률|기숙사|결과|장애인|직원|체험형|간호|면접|필기시험|장소")
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


_LEAD = re.compile(r"^(?:(?:D-+\d+|D-day|오늘)\s*(?:마감)?|진행중|접수중|마감|접수)\s*")
_TRAIL_DATE = re.compile(r"\s*20\d{2}[.\-/]\d{1,2}[.\-/]\d{1,2}.*$")


def _clean_title(t: str) -> str:
    """목록 링크에 섞여 들어오는 'D-3', '마감', 뒤쪽 접수기간을 떼어 낸다."""
    prev = None
    while prev != t:
        prev, t = t, _LEAD.sub("", t)
    return _TRAIL_DATE.sub("", t).strip()


# ---------------- 공통: 표 형식 채용 게시판 ----------------
def parse_rows(html: str, id_re: re.Pattern, hospital: str, url_fmt: str,
               keep=lambda text: True) -> list[Notice]:
    """링크 하나가 공고 한 건인 목록. 같은 행에서 날짜를 찾아 '시작 ~ 마감' 또는 게시일로 쓴다."""
    out: dict[str, Notice] = {}
    for a in make_soup(html).find_all("a"):
        src = (a.get("href") or "") + " " + (a.get("onclick") or "")
        m = id_re.search(src)
        if not m or m.group(1) in out:
            continue
        inner = a.find(["strong", "b"]) or a.select_one(".tit, .title, .subject")
        title = _clean_title(clean((inner or a).get_text(" ")))
        cat = categorize(title)
        if not cat:
            continue
        row = clean(item_container(a, id_re).get_text(" "))
        if not keep(row):
            continue
        dates = _dates(row)
        n = Notice(id=f"{hospital}-n{m.group(1)}", hospital=hospital, category=cat, title=title,
                   url=url_fmt.format(id=m.group(1)))
        if len(dates) >= 2:
            n.reg_start, n.reg_end = dates[0], _fix_span(dates[0], dates[1])
            n.posted = n.reg_start
        elif dates:
            n.posted = dates[0]
        out[m.group(1)] = n
    return list(out.values())


# ---------------- 삼성서울병원 ----------------
SMC_LIST = "https://www.samsunghospital.com/home/recruit/recruitInfo/recruitNotice.do"
_SMC_ID = re.compile(r"RECRUIT_CD=([0-9A-Za-z]+)")


def parse_smc(html: str) -> list[Notice]:
    return parse_rows(html, _SMC_ID, "smc",
                      "https://www.samsunghospital.com/home/recruit/recruitInfo/recruitNoticeView.do?RECRUIT_CD={id}")


def scrape_smc() -> list[Notice]:
    found: dict[str, Notice] = {}
    for page in range(1, 4):
        for n in parse_smc(fetch(SMC_LIST, params={"cPage": f"{page:02d}"}, name=f"smc-recruit-{page}")):
            found.setdefault(n.id, n)
    return list(found.values())


# ---------------- 건국대학교병원 (의사직 채용공고) ----------------
KUH_LIST = "https://www.kuh.ac.kr/m/recruit/docApply/noticeList.do"
_KUH_ID = re.compile(r"anc_seq\D{0,3}(\d+)")


def parse_kuh(html: str) -> list[Notice]:
    return parse_rows(html, _KUH_ID, "kuh", "https://www.kuh.ac.kr/recruit/docApply/noticeView.do?anc_seq={id}")


def scrape_kuh() -> list[Notice]:
    return parse_kuh(fetch(KUH_LIST, name="kuh-recruit-1"))


# ---------------- 이화의료원 (목동·서울병원) ----------------
EUMC_LIST = "https://www.eumc.ac.kr/intro/recrut/list.do"
_EUMC_ID = re.compile(r"bbs_no=(\d+)")


def parse_eumc(html: str) -> list[Notice]:
    return parse_rows(html, _EUMC_ID, "eumc", "https://www.eumc.ac.kr/intro/recrut/view.do?bbs_no={id}")


def scrape_eumc() -> list[Notice]:
    found: dict[str, Notice] = {}
    # 검색이 동작하지 않아 진행중 목록과 마감 목록 앞쪽을 매일 읽는다(새 공고는 올라오는 날 잡힌다)
    for status, pages in (("I", 1), ("E", 2)):
        for page in range(1, pages + 1):
            html = fetch(EUMC_LIST, params={"bid_status": status, "pageIndex": page}, name=f"eumc-recruit-{status}{page}")
            for n in parse_eumc(html):
                found.setdefault(n.id, n)
    return list(found.values())


# ---------------- 인제대학교 백병원 (상계·일산) ----------------
PAIK_LIST = "https://www.paik.ac.kr/recruit/user/job/list.do"
_PAIK_ID = re.compile(r"(?:view\(\s*'|jobId=)(\d+)")
_PAIK_HERE = re.compile(r"상계백|서울백|일산백|백중앙")
_PAIK_AWAY = re.compile(r"부산백|해운대백")


def parse_paik(html: str) -> list[Notice]:
    return parse_rows(html, _PAIK_ID, "paik", "https://www.paik.ac.kr/recruit/user/job/view.do?jobId={id}",
                      keep=lambda row: bool(_PAIK_HERE.search(row)) and not _PAIK_AWAY.search(row))


def scrape_paik() -> list[Notice]:
    found: dict[str, Notice] = {}
    for i, q in enumerate(("전공의", "인턴", "레지던트")):
        html = fetch(PAIK_LIST, params={"searchCondition": "1", "searchKeyword": q, "pageIndex": "1"},
                     name=f"paik-recruit-{i}")
        for n in parse_paik(html):
            found.setdefault(n.id, n)
    return list(found.values())


SOURCES = [
    (AMC_KEY, "서울아산병원", AMC_LIST, scrape_amc),
    (SNUH_KEY, "서울대학교병원", SNUH_LIST, scrape_snuh),
    ("smc", "삼성서울병원", SMC_LIST, scrape_smc),
    ("kuh", "건국대학교병원", KUH_LIST, scrape_kuh),
    ("eumc", "이화의료원(목동·서울)", EUMC_LIST, scrape_eumc),
    ("paik", "인제대 백병원(상계·일산)", PAIK_LIST, scrape_paik),
]
