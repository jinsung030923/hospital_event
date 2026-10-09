"""모든 병원 수집기를 실행하고 docs/events.json 을 갱신한다.

사용법:
    python scraper/run.py --out docs/events.json [--dump raw-html]

한 병원이 실패해도 나머지는 계속 진행하고, 실패한 병원은 기존 데이터를 그대로 둔다.
모든 병원이 실패했을 때만 종료 코드 1을 돌려준다(GitHub Actions에서 실패로 표시됨).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import asan  # noqa: E402
import hanyang  # noqa: E402
import samsung  # noqa: E402
from common import KST, set_dump_dir  # noqa: E402

# 새 병원을 추가하려면 모듈을 하나 만들고 여기에 한 줄을 넣는다.
# 목록 순서가 화면의 색상 순서가 된다.
SOURCES = [samsung, asan, hanyang]
KEEP_DAYS = 180  # 이보다 오래 지난 행사는 정리한다


def load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"events": [], "sources": {}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/events.json")
    parser.add_argument("--dump", default=None, help="원본 HTML 저장 폴더 (오류 확인용)")
    args = parser.parse_args()

    set_dump_dir(args.dump)
    out = Path(args.out)
    data = load(out)
    merged = {e["id"]: e for e in data.get("events", [])}
    sources = data.get("sources", {})
    now = datetime.now(KST)
    failures = 0

    for mod in SOURCES:
        try:
            events = mod.scrape()
            for ev in events:
                merged[ev.id] = ev.to_dict()
            sources[mod.KEY] = {"ok": True, "count": len(events),
                                "checked_at": now.isoformat(timespec="minutes"), "error": ""}
            print(f"[ok]   {mod.NAME}: {len(events)}건")
        except Exception as exc:  # noqa: BLE001 - 병원 하나의 실패가 전체를 막지 않게 한다
            failures += 1
            prev = sources.get(mod.KEY, {})
            sources[mod.KEY] = {"ok": False, "count": prev.get("count", 0),
                                "checked_at": prev.get("checked_at", ""), "error": str(exc)[:300]}
            print(f"[fail] {mod.NAME}: {exc}", file=sys.stderr)

    cutoff = (now - timedelta(days=KEEP_DAYS)).date().isoformat()
    events = [e for e in merged.values() if e["end_date"] >= cutoff]
    events.sort(key=lambda e: (e["start_date"], e["start_time"], e["id"]))

    result = {
        "updated_at": now.isoformat(timespec="minutes"),
        "hospitals": {m.KEY: {"name": m.NAME} for m in SOURCES},
        "sources": sources,
        "events": events,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"저장: {out} (행사 {len(events)}건)")
    return 1 if failures == len(SOURCES) else 0


if __name__ == "__main__":
    sys.exit(main())
