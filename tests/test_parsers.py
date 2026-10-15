"""파서 단위 테스트. 실제 게시판에서 관찰한 구조를 본뜬 HTML(tests/fixtures)로 검증한다.

실행: python -m pytest tests -q   (또는 python tests/test_parsers.py)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scraper"))

import ajou  # noqa: E402
import asan  # noqa: E402
import common  # noqa: E402
import depts  # noqa: E402
import eulji  # noqa: E402
import hanyang  # noqa: E402
import notices  # noqa: E402
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
    assert "eventId=1629" in e.url
    nca = by_title(ev, "NCA")
    assert (nca.start_date, nca.end_date) == ("2026-11-19", "2026-11-20")
    assert nca.id.startswith("amc-x") and nca.url == asan.LIST_URL  # 상세 링크 없는 '예정' 행사
    rng = by_title(ev, "기간 행사")
    assert (rng.start_date, rng.end_date) == ("2026-09-11", "2026-12-05")
    assert by_title(ev, "Genetics").title.endswith("Medical Center")  # &amp; 처리
    assert len({e.id for e in ev}) == 10
    assert e.url.endswith("eventDetail.do?eventId=1629")  # '조회'(사전등록 조회)가 아니라 상세 페이지


def test_asan_detail():
    d = asan.parse_detail(read("asan_detail.html"))
    assert d["location"] == "롯데호텔 에메랄드룸"
    assert (d["reg_start"], d["reg_end"]) == ("2026-08-31", "2026-10-17")
    assert asan.parse_detail("<html><body>장소 없음</body></html>") == {"location": "", "reg_start": "", "reg_end": ""}


def test_hanyang_place_cleanup():
    f = hanyang._clean_place
    assert f("온라인 HMP 세미나 (링크) ☞ https://example.com/x") == "온라인 HMP 세미나"
    assert f("한양대학교병원 본관 3층 HY이음홀") == "한양대학교병원 본관 3층 HY이음홀"
    assert f("(링크) ☞") == ""


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
    assert typo.reg_end == "2026-11-13"  # '사전등록 : 11. 13.(금)까지'
    assert by_title(ev, "공동 심포지엄").reg_end == ""  # 링크만 있고 마감일 없음


def test_eulji():
    rows = eulji.parse_list(read("eulji_list.html"))
    assert len(rows) == 6
    assert rows[2][2] == "https://refer.eulji.or.kr/news/news_pg02_02.jsp?board_code=BOARD_126&board_sequence=20690"
    ev = [e for e in (eulji.to_event(*r) for r in rows) if e]
    assert len(ev) == 3, [e.title for e in ev]  # 진료일정·가정간호·일시 없는 글은 제외
    e = by_title(ev, "비뇨의학과")
    assert (e.id, e.start_date, e.start_time, e.end_time) == ("eulji-20721", "2026-10-23", "18:30", "21:00")
    assert e.title == "2026년 비뇨의학과 개원의 연수강좌"
    assert by_title(ev, "내과 개원의").start_date == "2026-11-08"


def test_ajou():
    ev = ajou.parse_list(read("ajou_list.html"))
    assert len(ev) == 4, [e.title for e in ev]
    e = by_title(ev, "Hebei")
    assert (e.start_date, e.start_time, e.end_time) == ("2026-06-04", "13:40", "17:00")
    assert e.organizer == "외과학교실" and e.location.startswith("Basement Level 1")
    assert e.url.endswith("commBoardHLectureView.do?no=72001")
    assert by_title(ev, "신경과학").start_date == "2026-12-06"
    multi = by_title(ev, "호스피스")
    assert (multi.start_date, multi.end_date, multi.kind) == ("2026-09-09", "2026-09-10", "건강강좌")
    split = by_title(ev, "제목만 링크")
    assert (split.start_date, split.start_time, split.organizer) == ("2026-11-14", "09:00", "정형외과학교실")


def test_depts():
    f = depts.infer_depts
    assert f("신경과", "CADASIL") == ["신경과"]
    assert f("소화기내과", "AIDDS") == ["내과"]
    assert f("", "2026년 비뇨의학과 개원의 연수강좌") == ["비뇨의학과"]
    assert f("", "[SMC 병리과 심포지엄] Digital pathology") == ["병리과"]
    assert f("", "삼성서울병원 로봇수술 30,000례 기념 심포지엄") == ["외과"]
    assert f("", "신경외과 연수강좌") == ["신경외과"]  # 일반 '외과'가 겹치지 않는다
    assert f("", "정보관리부 공동 심포지엄") == ["기타"]
    assert f("태아치료센터", "Fetal Treatment Center Workshop") == ["산부인과"]
    assert f("시뮬레이션센터", "응급 초음파 교육") == ["응급의학과"] or f("시뮬레이션센터", "응급 초음파 교육")[0] == "응급의학과"


def test_robots():
    rp = common.parse_robots("User-agent: *\nDisallow: /private/\nAllow: /\n")
    assert rp.can_fetch(common.ROBOT_NAME, "https://x.kr/notice/list.do")
    assert not rp.can_fetch(common.ROBOT_NAME, "https://x.kr/private/a.do")
    blocked = common.parse_robots("User-agent: *\nDisallow: /\n")
    assert not blocked.can_fetch(common.ROBOT_NAME, "https://x.kr/")


def test_notices_amc():
    ns = notices.parse_amc(read("amc_notice_list.html"))
    got = {n.title: n.category for n in ns}
    assert got == {
        "2026년 하계 서브인턴 프로그램": "subintern",
        "2026년 동계 서브인턴 프로그램 모집 안내": "subintern",
        "2026년도 서울아산병원 레지던트 1년차 모집 공고": "residency",
    }, got
    n = [x for x in ns if "하계" in x.title][0]
    assert n.posted == "2026-06-17" and n.url == "https://edtr.amc.seoul.kr/education/service/notice/view.do?seq=1016"


def test_notices_snuh():
    ns = {n.id: n for n in notices.parse_snuh(read("snuh_recruit_list.html"))}
    assert set(ns) == {"snuh-n26096", "snuh-n26073", "snuh-n25173"}, set(ns)
    assert ns["snuh-n26096"].category == "residency"
    assert (ns["snuh-n26073"].category, ns["snuh-n26073"].reg_end) == ("subintern", "2026-06-19")
    assert ns["snuh-n25173"].reg_end == "2025-12-19"  # 1년 밀려 적힌 마감 연도 보정


def test_notices_more():
    smc = {n.title: n for n in notices.parse_smc(read("smc_recruit_list.html"))}
    assert set(smc) == {"2027년도 임상강사(Fellow) 초빙 안내", "2027년도 레지던트 1년차 모집 공고"}, set(smc)
    r = smc["2027년도 레지던트 1년차 모집 공고"]
    assert (r.reg_start, r.reg_end, r.category) == ("2026-11-20", "2026-11-27", "residency")
    kuh = {n.id: n for n in notices.parse_kuh(read("kuh_recruit_list.html"))}
    assert set(kuh) == {"kuh-n128", "kuh-n108"}, set(kuh)
    assert kuh["kuh-n108"].category == "subintern" and kuh["kuh-n108"].reg_end == "2025-12-12"
    assert notices._clean_title("D--2마감 [목동병원] 2027년도 전공의(인턴) 모집 공고") == "[목동병원] 2027년도 전공의(인턴) 모집 공고"
    assert notices._clean_title("마감 2026년도 인턴 모집 공고 2026-08-10 09:00 ~ 2026-08-12 17:00") == "2026년도 인턴 모집 공고"
    paik = notices.parse_paik(read("paik_recruit_list.html"))
    assert [n.id for n in paik] == ["paik-n1430"]
    assert paik[0].url.endswith("jobId=1430")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
