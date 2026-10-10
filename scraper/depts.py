"""행사 제목·주관 부서에서 진료과를 추정한다.

병원마다 '주관' 칸의 유무와 표기가 달라서(삼성·한양은 주관 없음) 한 곳에서 같은 규칙으로 처리한다.
규칙은 위에서부터 검사하며, 한 행사가 여러 진료과에 걸리면 최대 3개까지 붙인다.
주관 부서에서 찾은 결과가 있으면 그것을 쓰고, 없을 때만 제목에서 찾는다.
"""
from __future__ import annotations

import re

OTHER = "기타"

RULES: list[tuple[str, str]] = [
    ("신경외과", r"신경외과|neurosurg"),
    ("정형외과", r"정형외과|orthop"),
    ("흉부외과", r"흉부외과|심장혈관흉부|cardiothoracic"),
    ("성형외과", r"성형외과|plastic surg"),
    ("산부인과", r"산부인과|산과|부인과|산전|태아|난임|출산|obstet|gynec|fetal"),
    ("소아청소년과", r"소아청소년|소아과|소아|어린이|신생아|pediatr|neonat"),
    ("신경과", r"신경과|뇌신경|뇌졸중|치매|두통|뇌전증|neurology"),
    ("정신건강의학과", r"정신건강|정신과|psychiat"),
    ("영상의학과", r"영상의학|방사선과|radiolog"),
    ("병리과", r"병리|patholog"),
    ("마취통증의학과", r"마취|통증|anesthes"),
    ("응급의학과", r"응급|emergency"),
    ("비뇨의학과", r"비뇨|urolog"),
    ("안과", r"안과|ophthalm"),
    ("이비인후과", r"이비인후|otolaryn"),
    ("피부과", r"피부과|dermat"),
    ("재활의학과", r"재활|rehabil"),
    ("가정의학과", r"가정의학|family medicine"),
    ("핵의학과", r"핵의학|nuclear medicine"),
    ("방사선종양학과", r"방사선종양|radiation oncol"),
    ("중환자의학", r"중환자|critical care|ventilator"),
    ("외과", r"외과|수술|이식|간담도췌|대장항문|유방|갑상선|surgery|surgical"),
    ("내과", r"내과|소화기|순환기|호흡기|내분비|당뇨|혈액종양|신장|류마티스|알레르기|노년|부정맥|고혈압|internal medicine|gastroenter|endocrin"),
    ("종양(암)", r"암병원|암센터|항암|종양|암신속|oncolog"),
    ("치과", r"치과|구강"),
]
_COMPILED = [(name, re.compile(pat, re.I)) for name, pat in RULES]
_SPECIFIC_SURGERY = {"신경외과", "정형외과", "흉부외과", "성형외과"}


def _match(text: str) -> list[str]:
    found = [name for name, rx in _COMPILED if rx.search(text or "")]
    if _SPECIFIC_SURGERY & set(found) and "외과" in found:
        found.remove("외과")  # '신경외과'가 일반 '외과'로 한 번 더 잡히지 않게 한다
    return found


def infer_depts(organizer: str, title: str) -> list[str]:
    found = _match(organizer) or _match(title)
    return found[:3] or [OTHER]
