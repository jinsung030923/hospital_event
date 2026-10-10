"""병원 학술행사 수집기 공통 모듈."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

KST = ZoneInfo("Asia/Seoul")
USER_AGENT = (
    "Mozilla/5.0 (compatible; HospitalEventCalendar/1.0; "
    "personal study project, once-a-day crawl)"
)

# 일반인 대상 건강강좌를 가려내기 위한 키워드 (의료인 대상 학술행사와 구분)
PUBLIC_KEYWORDS = (
    "건강강좌", "공개강좌", "공개 강좌", "건강교실", "부모교육",
    "가족참여", "환자 교실", "환자교실", "환우", "캠페인",
)

ROBOT_NAME = "HospitalEventCalendar"

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ko,en;q=0.8"})
_dump_dir: Path | None = None


def set_dump_dir(path: str | None) -> None:
    """원본 HTML을 저장할 폴더를 지정한다 (파서 오류 확인용)."""
    global _dump_dir
    _dump_dir = Path(path) if path else None
    if _dump_dir:
        _dump_dir.mkdir(parents=True, exist_ok=True)


_robots: dict[str, robotparser.RobotFileParser | None] = {}


def parse_robots(text: str) -> robotparser.RobotFileParser:
    rp = robotparser.RobotFileParser()
    rp.parse(text.splitlines())
    return rp


def allowed(url: str) -> bool:
    """사이트의 robots.txt 가 이 주소의 수집을 허용하는지 확인한다.

    robots.txt 가 없거나(4xx) 읽을 수 없으면 제한이 없는 것으로 본다.
    """
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if origin not in _robots:
        try:
            res = _session.get(origin + "/robots.txt", timeout=15)
            _robots[origin] = parse_robots(res.text) if res.status_code == 200 else None
        except requests.RequestException:
            _robots[origin] = None
    rp = _robots[origin]
    return True if rp is None else rp.can_fetch(ROBOT_NAME, url)


def fetch(url: str, *, params: dict | None = None, name: str = "page",
          retries: int = 3, pause: float = 1.0) -> str:
    """페이지를 내려받아 HTML 문자열로 돌려준다. 실패하면 RuntimeError."""
    if not allowed(url):
        raise RuntimeError(f"robots.txt 가 이 주소의 자동 수집을 허용하지 않습니다: {url}")
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            res = _session.get(url, params=params, timeout=30)
            res.raise_for_status()
            if not res.encoding or res.encoding.lower() == "iso-8859-1":
                res.encoding = res.apparent_encoding
            html = res.text
            if _dump_dir:
                (_dump_dir / f"{name}.html").write_text(html, encoding="utf-8")
            time.sleep(pause)  # 서버 부담을 줄이기 위한 간격
            return html
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"요청 실패: {url} ({last_error})")


def make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def ymd(year: int, month: int, day: int) -> str:
    """유효한 날짜인지 확인하고 YYYY-MM-DD 문자열로 만든다."""
    return date(int(year), int(month), int(day)).isoformat()


def hhmm(hour: str | int, minute: str | int) -> str:
    return f"{int(hour):02d}:{int(minute):02d}"


def classify(title: str) -> str:
    """제목으로 의료인 대상 '학술'과 일반 대상 '건강강좌'를 구분한다."""
    return "건강강좌" if any(k in title for k in PUBLIC_KEYWORDS) else "학술"


def item_container(anchor, key_re: re.Pattern):
    """링크 하나가 속한 '행사 한 건' 영역(가장 바깥 요소)을 찾는다.

    위로 올라가다가 다른 행사의 링크가 섞이기 직전까지를 한 건으로 본다.
    """
    def keys(node) -> set[str]:
        found = set()
        links = ([node] if node.name == "a" and node.has_attr("href") else []) + node.find_all("a", href=True)
        for a in links:
            m = key_re.search(a["href"])
            if m:
                found.add(m.group(0))
        return found

    own = keys(anchor)
    node = anchor
    while node.parent is not None and node.parent.name not in ("body", "html", "[document]"):
        if not keys(node.parent) <= own:
            break
        node = node.parent
    return node


@dataclass
class Event:
    id: str
    hospital: str
    title: str
    start_date: str
    end_date: str
    start_time: str = ""
    end_time: str = ""
    location: str = ""
    organizer: str = ""
    url: str = ""
    reg_start: str = ""
    reg_end: str = ""
    kind: str = "학술"

    def to_dict(self) -> dict:
        return asdict(self)
