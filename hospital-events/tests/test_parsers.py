"""파서 단위 테스트. 실제 게시판에서 관찰한 구조를 본뜬 HTML(tests/fixtures)로 검증한다.

실행: python -m pytest tests -q   (또는 python tests/test_parsers.py)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scraper"))

import asan  # noqa: E402
import hanyang  # noqa: E402
import samsung  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


def read(name):
    return (FIX / name).read_text(encoding="utf-8")


def by_title(events, part):
    hits = [e for e in events if part in e.title]
    assert len(hits) == 1, f"{part!r} 일치 {len(hits)}건"
    return hits[0]


def test_samsung():
    ev = samsung.parse_list(read("samsung_list.html"))
    assert len(ev) == 3
    e = by_title(ev, "어린이공공전문진료")
    assert (e.start_date, e.start_time, e.end_time) == ("2026-09-13", "09:00", "16:00")
    assert e.location == "삼성서울병원 암병원 지하 2층 대강당"
    assert (e.reg_start, e.reg_end) == ("2026-07-29", "2026-09-09")
    assert e.url.endswith("scienceView.do?seq=23230")
    multi = by_title(ev, "2일 일정")
    assert (multi.start_date, multi.end_date) == ("2026-10-03", "2026-10-04")
    assert multi.kind == "건강강좌"
    assert by_title(ev, "외과 심포지엄").kind == "학술"


def test_asan():
    ev = asan.parse_list(read("asan_list.html"))
    assert len(ev) == 10, [e.title for e in ev]
    e = by_title(ev, "CADASIL")
    assert (e.id, e.start_date, e.start_time, e.end_time) == ("amc-1629", "2026-11-20", "08:45", "17:55")
    assert e.organizer == "신경과"
    assert e.url.endswith("eventId=1629")
    nca = by_title(ev, "NCA")
    assert (nca.start_date, nca.end_date) == ("2026-11-19", "2026-11-20")
    assert nca.id.startswith("amc-x") and nca.url == asan.LIST_URL  # 상세 링크 없는 '예정' 행사
    rng = by_title(ev, "기간 행사")
    assert (rng.start_date, rng.end_date) == ("2026-09-11", "2026-12-05")
    assert by_title(ev, "Genetics").title.endswith("Medical Center")  # &amp; 처리
    assert len({e.id for e in ev}) == 10


def test_hanyang():
    ev = hanyang.parse_list(read("hanyang_list.html"))
    assert len(ev) == 3
    e = by_title(ev, "공동 심포지엄")
    assert (e.id, e.start_date, e.start_time, e.end_time) == ("hyumc-438", "2026-10-29", "15:00", "17:05")
    assert "HY이음홀" not in e.location or e.location.startswith("서울 성동구")
    assert e.url.endswith("no=438")
    assert by_title(ev, "핑크 힐링").kind == "건강강좌"
    typo = by_title(ev, "(TEST) 연수강좌")
    assert typo.start_date == "2026-11-28"  # 제목의 연도로 바로잡힘


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
