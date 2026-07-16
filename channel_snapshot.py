#!/usr/bin/env python3
"""
채널 스냅샷 리포트 — YouTube Data API v3
용도: 여러 채널(내 채널 + 경쟁/벤치마킹 채널)의 구독자/조회수/영상수/영상당평균을
     한 번에 뽑아서 표로 정리. 허수 채널 판별(총조회수÷구독자, 총조회수÷영상수)에 사용.

필요한 것:
- pip install google-api-python-client python-dotenv --break-system-packages
- 같은 폴더에 .env 파일 만들고 아래 한 줄 추가:
    YT_API_KEY=여기에_Data_API_키

사용법:
  python3 channel_snapshot.py @z2zlife @LatinHeatMove UCxxxxxxxx
  (핸들 @이름 또는 채널ID 둘 다 가능, 여러 개 공백으로 구분)

cron 등록 예시 (매주 월요일 오전 9시):
  0 9 * * 1 cd /path/to/yt-scripts && python3 channel_snapshot.py @내채널 @z2zlife >> weekly_report.log 2>&1
"""

import sys
import os
import csv
import datetime
from pathlib import Path
from typing import Optional, Dict

try:
    from dotenv import load_dotenv
except ImportError:
    print("pip install python-dotenv --break-system-packages 먼저 실행하세요")
    sys.exit(1)

try:
    from googleapiclient.discovery import build
except ImportError:
    print("pip install google-api-python-client --break-system-packages 먼저 실행하세요")
    sys.exit(1)

load_dotenv(Path(__file__).parent / ".env")
API_KEY = os.getenv("YT_API_KEY")

if not API_KEY:
    print("에러: .env 파일에 YT_API_KEY가 없습니다.")
    sys.exit(1)

youtube = build("youtube", "v3", developerKey=API_KEY)


def resolve_channel_id(handle_or_id: str) -> Optional[str]:
    """@handle 이든 UCxxxx 채널ID든 받아서 채널ID로 변환"""
    if handle_or_id.startswith("UC") and len(handle_or_id) == 24:
        return handle_or_id

    handle = handle_or_id.lstrip("@")
    try:
        resp = youtube.channels().list(part="id", forHandle=handle).execute()
        items = resp.get("items", [])
        if items:
            return items[0]["id"]
    except Exception as e:
        print(f"  [경고] {handle_or_id} handle 조회 실패: {e}")

    # 구버전 폴백: search로 채널 찾기
    try:
        resp = youtube.search().list(part="snippet", q=handle_or_id, type="channel", maxResults=1).execute()
        items = resp.get("items", [])
        if items:
            return items[0]["snippet"]["channelId"]
    except Exception as e:
        print(f"  [경고] {handle_or_id} search 폴백 실패: {e}")

    return None


def get_channel_stats(channel_id: str) -> Optional[dict]:
    resp = youtube.channels().list(
        part="snippet,statistics",
        id=channel_id
    ).execute()
    items = resp.get("items", [])
    if not items:
        return None

    ch = items[0]
    stats = ch["statistics"]
    snippet = ch["snippet"]

    subs = int(stats.get("subscriberCount", 0)) if not stats.get("hiddenSubscriberCount") else None
    views = int(stats.get("viewCount", 0))
    video_count = int(stats.get("videoCount", 0))

    avg_views = round(views / video_count, 1) if video_count > 0 else 0
    views_per_sub = round(views / subs, 2) if subs and subs > 0 else None

    # 허수 판별 플래그
    warning = ""
    if subs and subs >= 5000:
        if views_per_sub is not None and views_per_sub < 20:
            warning = "⚠ 구독자 대비 조회수 매우 낮음 (허수 의심)"
        if avg_views < 300:
            warning += " ⚠ 영상당 평균 조회수 매우 낮음"

    return {
        "channel_id": channel_id,
        "title": snippet.get("title"),
        "published_at": snippet.get("publishedAt", "")[:10],
        "subscribers": subs,
        "total_views": views,
        "video_count": video_count,
        "avg_views_per_video": avg_views,
        "views_per_subscriber": views_per_sub,
        "warning": warning.strip(),
    }


def main():
    if len(sys.argv) < 2:
        print("사용법: python3 channel_snapshot.py @핸들1 @핸들2 UCxxxx...")
        sys.exit(1)

    targets = sys.argv[1:]
    rows = []

    print(f"{'채널명':<20} {'구독자':>10} {'총조회수':>12} {'영상수':>8} {'영상당평균':>10} {'조회/구독비':>10}  경고")
    print("-" * 100)

    for t in targets:
        cid = resolve_channel_id(t)
        if not cid:
            print(f"  [실패] {t} → 채널을 찾을 수 없습니다")
            continue
        stats = get_channel_stats(cid)
        if not stats:
            print(f"  [실패] {t} → 통계를 가져올 수 없습니다")
            continue
        rows.append(stats)
        subs_disp = f"{stats['subscribers']:,}" if stats['subscribers'] is not None else "비공개"
        vps_disp = f"{stats['views_per_subscriber']}" if stats['views_per_subscriber'] is not None else "-"
        print(f"{stats['title'][:19]:<20} {subs_disp:>10} {stats['total_views']:>12,} "
              f"{stats['video_count']:>8,} {stats['avg_views_per_video']:>10,} {vps_disp:>10}  {stats['warning']}")

    # CSV 저장 (허실장이 텔레그램으로 보내거나 누적 트래킹할 때 사용)
    out_dir = Path(__file__).parent / "reports"
    out_dir.mkdir(exist_ok=True)
    fname = out_dir / f"channel_snapshot_{datetime.date.today().isoformat()}.csv"
    with open(fname, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n저장됨: {fname}")


if __name__ == "__main__":
    main()
