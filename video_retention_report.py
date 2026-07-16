#!/usr/bin/env python3
"""
내 채널 영상 성과 리포트 — YouTube Analytics API v2 (OAuth 필요, 본인 채널만)
용도: 오늘 스크린샷으로 확인했던 CTR / 평균시청시간 / 노출수 / 트래픽소스를
     초 단위 리텐션 곡선까지 포함해서 CSV로 뽑는다. 클로드에 CSV 붙여넣으면
     스크린샷보다 훨씬 정밀한 절벽 지점 분석이 가능.

최초 1회 설정 (OAuth):
1. Google Cloud Console에서 OAuth 클라이언트(Desktop app) 만들고 client_secret.json 다운로드
   같은 폴더에 저장
2. pip install google-auth-oauthlib google-api-python-client python-dotenv --break-system-packages
3. 최초 실행 시 브라우저가 뜨고 로그인 → token.json 자동 생성 (이후 재사용, 재로그인 불필요)

사용법:
  python3 video_retention_report.py <video_id> [<video_id2> ...]
  (video_id는 유튜브 URL의 v= 뒤 11자리, 또는 studio URL의 video ID)

예: python3 video_retention_report.py dQw4w9WgXcQ

cron 등록 예시 (매일 오전 9시, 최근 업로드 자동 추적):
  0 9 * * * cd /path/to/yt-scripts && python3 video_retention_report.py $(cat latest_video_id.txt) >> daily_retention.log 2>&1
"""

import sys
import os
import csv
import datetime
from pathlib import Path

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
except ImportError:
    print("pip install google-auth-oauthlib google-api-python-client --break-system-packages 먼저 실행하세요")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
CLIENT_SECRET_FILE = SCRIPT_DIR / "client_secret.json"
TOKEN_FILE = SCRIPT_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/yt-analytics.readonly",
          "https://www.googleapis.com/auth/youtube.readonly"]


def get_credentials():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_FILE.exists():
                print(f"에러: {CLIENT_SECRET_FILE} 이 없습니다. Google Cloud Console에서 "
                      f"OAuth 클라이언트(Desktop app) 만들고 client_secret.json으로 저장하세요.")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
            creds = flow.run_local_server(port=0, host="0.0.0.0")
        TOKEN_FILE.write_text(creds.to_json())
    return creds


def get_video_meta(youtube_data, video_id: str) -> dict:
    resp = youtube_data.videos().list(part="snippet,contentDetails", id=video_id).execute()
    items = resp.get("items", [])
    if not items:
        return {}
    sn = items[0]["snippet"]
    return {"title": sn.get("title"), "published_at": sn.get("publishedAt", "")[:10]}


def get_overview_metrics(youtube_analytics, channel_id, video_id, start, end):
    resp = youtube_analytics.reports().query(
        ids=f"channel=={channel_id}",
        startDate=start,
        endDate=end,
        metrics="views,averageViewDuration,averageViewPercentage,impressions,impressionsClickThroughRate",
        filters=f"video=={video_id}",
    ).execute()
    rows = resp.get("rows")
    if not rows:
        return {}
    cols = [c["name"] for c in resp["columnHeaders"]]
    return dict(zip(cols, rows[0]))


def get_retention_curve(youtube_analytics, channel_id, video_id, start, end):
    """초 단위 상대 리텐션 곡선 (elapsedVideoTimeRatio 0.0~1.0, audienceWatchRatio)"""
    resp = youtube_analytics.reports().query(
        ids=f"channel=={channel_id}",
        startDate=start,
        endDate=end,
        metrics="audienceWatchRatio,relativeRetentionPerformance",
        dimensions="elapsedVideoTimeRatio",
        filters=f"video=={video_id}",
        sort="elapsedVideoTimeRatio",
    ).execute()
    return resp.get("rows", [])


def get_traffic_sources(youtube_analytics, channel_id, video_id, start, end):
    resp = youtube_analytics.reports().query(
        ids=f"channel=={channel_id}",
        startDate=start,
        endDate=end,
        metrics="views",
        dimensions="insightTrafficSourceType",
        filters=f"video=={video_id}",
        sort="-views",
    ).execute()
    return resp.get("rows", [])


def main():
    if len(sys.argv) < 2:
        print("사용법: python3 video_retention_report.py <video_id> [<video_id2> ...]")
        sys.exit(1)

    creds = get_credentials()
    youtube_data = build("youtube", "v3", credentials=creds)
    youtube_analytics = build("youtubeAnalytics", "v2", credentials=creds)

    # 내 채널 ID 자동 조회
    ch_resp = youtube_data.channels().list(part="id", mine=True).execute()
    channel_id = ch_resp["items"][0]["id"]

    end = datetime.date.today().isoformat()
    start = "2020-01-01"  # 게시 이후 전체 기간

    out_dir = SCRIPT_DIR / "reports"
    out_dir.mkdir(exist_ok=True)

    for video_id in sys.argv[1:]:
        meta = get_video_meta(youtube_data, video_id)
        overview = get_overview_metrics(youtube_analytics, channel_id, video_id, start, end)
        retention = get_retention_curve(youtube_analytics, channel_id, video_id, start, end)
        traffic = get_traffic_sources(youtube_analytics, channel_id, video_id, start, end)

        print(f"\n=== {meta.get('title', video_id)} ({meta.get('published_at', '?')}) ===")
        print(f"조회수: {overview.get('views')}  "
              f"평균시청(초): {overview.get('averageViewDuration')}  "
              f"평균시청비율(%): {overview.get('averageViewPercentage')}  "
              f"노출수: {overview.get('impressions')}  "
              f"CTR(%): {overview.get('impressionsClickThroughRate')}")

        print("\n[트래픽 소스]")
        for r in traffic:
            print(f"  {r[0]:<25} {r[1]}회")

        # 리텐션 곡선 CSV로 저장 (클로드에 붙여넣기용)
        fname = out_dir / f"retention_{video_id}_{end}.csv"
        with open(fname, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["elapsed_ratio", "audience_watch_ratio", "relative_retention_vs_similar"])
            writer.writerows(retention)
        print(f"\n리텐션 곡선 저장됨: {fname}")
        print("  → 이 CSV를 클로드에 붙여넣으면 절벽 구간을 정확한 %로 짚어드립니다.")


if __name__ == "__main__":
    main()
