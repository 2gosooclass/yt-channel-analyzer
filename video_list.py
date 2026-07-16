#!/usr/bin/env python3
"""
경쟁 채널 영상 전체 분석 — YouTube Data API v3
용도: 아무 공개 채널의 영상 전체(또는 최근 N개)를 뽑아서
     제목/조회수/좋아요/댓글/길이/태그/업로드날짜를 표+CSV로 출력.
     조회수 상위 영상의 제목 패턴, 태그 빈도, 최적 영상 길이 분석 포함.

사용법:
  python3 video_list.py @경쟁채널핸들
  python3 video_list.py @채널1 @채널2 --top 20        # 상위 20개만
  python3 video_list.py @채널1 --days 90              # 최근 90일 영상만
  python3 video_list.py @채널1 --analyze              # 패턴 분석 포함
"""

import sys
import os
import csv
import re
import datetime
from pathlib import Path
from collections import Counter
from typing import Optional, Tuple, List, Dict

try:
    from dotenv import load_dotenv
except ImportError:
    print("pip install python-dotenv --break-system-packages")
    sys.exit(1)

try:
    from googleapiclient.discovery import build
except ImportError:
    print("pip install google-api-python-client --break-system-packages")
    sys.exit(1)

load_dotenv(Path(__file__).parent / ".env")
API_KEY = os.getenv("YT_API_KEY")
if not API_KEY:
    print("에러: .env 파일에 YT_API_KEY가 없습니다.")
    sys.exit(1)

youtube = build("youtube", "v3", developerKey=API_KEY)


def resolve_channel_id(handle_or_id: str) -> Tuple[Optional[str], str]:
    if handle_or_id.startswith("UC") and len(handle_or_id) == 24:
        resp = youtube.channels().list(part="snippet", id=handle_or_id).execute()
        items = resp.get("items", [])
        return handle_or_id, items[0]["snippet"]["title"] if items else handle_or_id

    handle = handle_or_id.lstrip("@")
    try:
        resp = youtube.channels().list(part="snippet", forHandle=handle).execute()
        items = resp.get("items", [])
        if items:
            return items[0]["id"], items[0]["snippet"]["title"]
    except Exception:
        pass

    try:
        resp = youtube.search().list(part="snippet", q=handle_or_id, type="channel", maxResults=1).execute()
        items = resp.get("items", [])
        if items:
            cid = items[0]["snippet"]["channelId"]
            return cid, items[0]["snippet"]["title"]
    except Exception:
        pass

    return None, handle_or_id


def get_uploads_playlist_id(channel_id: str) -> Optional[str]:
    resp = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    items = resp.get("items", [])
    if not items:
        return None
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def parse_duration(iso_dur: str) -> int:
    """ISO 8601 duration → 초"""
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_dur or "")
    if not m:
        return 0
    h, mn, s = m.groups(default="0")
    return int(h) * 3600 + int(mn) * 60 + int(s)


def fmt_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def get_all_videos(channel_id: str, days: Optional[int] = None) -> List[Dict]:
    playlist_id = get_uploads_playlist_id(channel_id)
    if not playlist_id:
        return []

    cutoff = None
    if days:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)

    video_ids = []
    next_token = None

    while True:
        resp = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_token,
        ).execute()

        for item in resp.get("items", []):
            pub = item["contentDetails"].get("videoPublishedAt", "")
            if cutoff and pub:
                pub_dt = datetime.datetime.fromisoformat(pub.replace("Z", "+00:00"))
                if pub_dt < cutoff:
                    return _fetch_video_details(video_ids)
            video_ids.append(item["contentDetails"]["videoId"])

        next_token = resp.get("nextPageToken")
        if not next_token:
            break

    return _fetch_video_details(video_ids)


def _fetch_video_details(video_ids: list[str]) -> list[dict]:
    videos = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        resp = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(batch),
        ).execute()

        for v in resp.get("items", []):
            sn = v["snippet"]
            st = v.get("statistics", {})
            dur = parse_duration(v["contentDetails"].get("duration", ""))
            videos.append({
                "video_id": v["id"],
                "title": sn.get("title", ""),
                "published_at": sn.get("publishedAt", "")[:10],
                "views": int(st.get("viewCount", 0)),
                "likes": int(st.get("likeCount", 0)),
                "comments": int(st.get("commentCount", 0)),
                "duration_sec": dur,
                "duration": fmt_duration(dur),
                "tags": sn.get("tags", []),
                "description": sn.get("description", "")[:200],
            })
    return videos


def analyze_patterns(videos: list[dict], channel_name: str):
    if not videos:
        return

    views = [v["views"] for v in videos]
    views_sorted = sorted(views, reverse=True)
    top_20_cutoff = views_sorted[max(0, len(views_sorted) // 5 - 1)] if len(views_sorted) >= 5 else 0

    top_videos = [v for v in videos if v["views"] >= top_20_cutoff]
    bottom_videos = [v for v in videos if v["views"] < top_20_cutoff]

    print(f"\n{'='*80}")
    print(f"  패턴 분석: {channel_name} ({len(videos)}개 영상)")
    print(f"{'='*80}")

    # 기본 통계
    avg_views = sum(views) / len(views)
    median_views = sorted(views)[len(views) // 2]
    print(f"\n[기본 통계]")
    print(f"  평균 조회수: {avg_views:,.0f}  /  중앙값: {median_views:,}  /  최고: {max(views):,}  /  최저: {min(views):,}")

    # 조회수 상위 10개
    print(f"\n[조회수 TOP 10]")
    for i, v in enumerate(sorted(videos, key=lambda x: x["views"], reverse=True)[:10], 1):
        print(f"  {i:2d}. {v['views']:>10,}회  {v['duration']:>7}  {v['published_at']}  {v['title'][:60]}")

    # 태그 분석: 상위 영상 vs 하위 영상
    top_tags = Counter()
    bottom_tags = Counter()
    for v in top_videos:
        top_tags.update(t.lower() for t in v["tags"])
    for v in bottom_videos:
        bottom_tags.update(t.lower() for t in v["tags"])

    print(f"\n[상위 20% 영상에만 자주 나오는 태그] (하위에 없거나 적은 것)")
    top_only = []
    for tag, cnt in top_tags.most_common(30):
        bottom_cnt = bottom_tags.get(tag, 0)
        if cnt >= 2 and (bottom_cnt == 0 or cnt / max(bottom_cnt, 1) > 2):
            top_only.append((tag, cnt, bottom_cnt))
    for tag, tc, bc in top_only[:15]:
        print(f"  '{tag}' — 상위 {tc}회 vs 하위 {bc}회")

    # 영상 길이별 평균 조회수
    buckets = {"~3분": [], "3~8분": [], "8~15분": [], "15~30분": [], "30분+": []}
    for v in videos:
        d = v["duration_sec"]
        if d <= 180:
            buckets["~3분"].append(v["views"])
        elif d <= 480:
            buckets["3~8분"].append(v["views"])
        elif d <= 900:
            buckets["8~15분"].append(v["views"])
        elif d <= 1800:
            buckets["15~30분"].append(v["views"])
        else:
            buckets["30분+"].append(v["views"])

    print(f"\n[영상 길이별 평균 조회수]")
    for bucket, vlist in buckets.items():
        if vlist:
            avg = sum(vlist) / len(vlist)
            print(f"  {bucket:>8}: {avg:>10,.0f}  ({len(vlist)}개 영상)")

    # 업로드 요일별 평균 조회수
    day_views = {i: [] for i in range(7)}
    day_names = ["월", "화", "수", "목", "금", "토", "일"]
    for v in videos:
        try:
            dt = datetime.date.fromisoformat(v["published_at"])
            day_views[dt.weekday()].append(v["views"])
        except (ValueError, TypeError):
            pass

    print(f"\n[업로드 요일별 평균 조회수]")
    for i in range(7):
        vlist = day_views[i]
        if vlist:
            avg = sum(vlist) / len(vlist)
            print(f"  {day_names[i]}요일: {avg:>10,.0f}  ({len(vlist)}개)")

    # 제목 길이 vs 조회수
    short_title = [v for v in videos if len(v["title"]) <= 30]
    long_title = [v for v in videos if len(v["title"]) > 30]
    if short_title and long_title:
        short_avg = sum(v["views"] for v in short_title) / len(short_title)
        long_avg = sum(v["views"] for v in long_title) / len(long_title)
        print(f"\n[제목 길이별 평균 조회수]")
        print(f"  30자 이하: {short_avg:>10,.0f}  ({len(short_title)}개)")
        print(f"  30자 초과: {long_avg:>10,.0f}  ({len(long_title)}개)")

    # 제목에 자주 등장하는 키워드 (상위 영상)
    title_words = Counter()
    stop = {"the", "a", "an", "is", "are", "of", "in", "to", "for", "and", "or", "이", "그", "이것", "을", "를", "에", "의", "로", "는", "가", "도"}
    for v in top_videos:
        words = re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}', v["title"].lower())
        title_words.update(w for w in words if w not in stop)

    print(f"\n[상위 영상 제목에 자주 등장하는 키워드]")
    for word, cnt in title_words.most_common(15):
        print(f"  '{word}' — {cnt}회")

    print()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="경쟁 채널 영상 전체 분석")
    parser.add_argument("channels", nargs="+", help="@핸들 또는 채널ID")
    parser.add_argument("--top", type=int, default=0, help="조회수 상위 N개만 출력")
    parser.add_argument("--days", type=int, default=None, help="최근 N일 영상만")
    parser.add_argument("--analyze", action="store_true", help="패턴 분석 포함")
    args = parser.parse_args()

    out_dir = Path(__file__).parent / "reports"
    out_dir.mkdir(exist_ok=True)

    for target in args.channels:
        cid, ch_name = resolve_channel_id(target)
        if not cid:
            print(f"[실패] {target} → 채널을 찾을 수 없습니다")
            continue

        print(f"\n{ch_name} 영상 가져오는 중...")
        videos = get_all_videos(cid, days=args.days)
        if not videos:
            print(f"  영상이 없습니다.")
            continue

        videos.sort(key=lambda x: x["views"], reverse=True)
        display = videos[:args.top] if args.top > 0 else videos

        print(f"\n{'순위':>4}  {'조회수':>10}  {'좋아요':>7}  {'댓글':>5}  {'길이':>7}  {'업로드일':>10}  제목")
        print("-" * 110)
        for i, v in enumerate(display, 1):
            print(f"{i:4d}  {v['views']:>10,}  {v['likes']:>7,}  {v['comments']:>5,}  "
                  f"{v['duration']:>7}  {v['published_at']}  {v['title'][:55]}")

        # CSV 저장
        safe_name = re.sub(r'[^\w]', '_', ch_name)[:30]
        fname = out_dir / f"videos_{safe_name}_{datetime.date.today().isoformat()}.csv"
        with open(fname, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "video_id", "title", "published_at", "views", "likes",
                "comments", "duration", "duration_sec", "tags", "description"
            ])
            writer.writeheader()
            for v in videos:
                row = {**v, "tags": "|".join(v["tags"])}
                writer.writerow(row)
        print(f"\n전체 {len(videos)}개 영상 저장됨: {fname}")

        if args.analyze:
            analyze_patterns(videos, ch_name)


if __name__ == "__main__":
    main()
