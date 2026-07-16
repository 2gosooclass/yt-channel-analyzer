# 📊 yt-channel-analyzer

**Instant YouTube channel intelligence — competitor benchmarking, fake-subscriber detection, and retention cliff analysis. No dashboard needed.**

> Built by [2GOSOO AI LAB](https://2gosoo.com) · Works with any public channel worldwide

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![YouTube Data API](https://img.shields.io/badge/YouTube-Data%20API%20v3-red)](https://developers.google.com/youtube/v3)
[![YouTube Analytics API](https://img.shields.io/badge/YouTube-Analytics%20API%20v2-red)](https://developers.google.com/youtube/analytics)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 🤔 Why this exists

YouTube Studio tells you what happened on **your** channel.  
It tells you nothing about your **competitors**.

This toolkit fills that gap:

| Problem | Solution |
|---|---|
| "Is that channel's 100K subscribers real or bought?" | `channel_snapshot.py` — fake-subscriber score in seconds |
| "Which video topics are actually working in my niche?" | Pull any channel's full video list with views, sorted by performance |
| "Where exactly do viewers drop off on my videos?" | `video_retention_report.py` — second-by-second retention curve as CSV |
| "I waste 30 min every week clicking through Studio" | Automate with cron, send reports to Telegram via your AI agent |

---

## ⚡ Quickstart (5 minutes)

```bash
git clone https://github.com/2gosooclass/yt-channel-analyzer
cd yt-channel-analyzer
pip install -r requirements.txt

# Add your YouTube Data API key
echo "YT_API_KEY=your_key_here" > .env

# Analyze any channel
python3 channel_snapshot.py @MrBeast @mkbhd @YourChannel
```

That's it. No OAuth, no browser login — just an API key for competitor analysis.

---

## 🔍 Script 1: `channel_snapshot.py` — Competitor Intelligence

Analyzes **any public YouTube channel**. No channel owner permission needed.

```bash
python3 channel_snapshot.py @z2zlife @veritasium @3blue1brown
```

**Output:**
```
Channel              Subscribers    Total Views    Videos   Avg/Video  Views/Sub  Warning
z2zlife                   58,900        312,805     2,248         139       5.31  ⚠ Fake subs suspected ⚠ Zombie channel
veritasium                 15.4M    2,847,000,000       174  16,362,069     184.9
3blue1brown                 6.8M      617,000,000       153   4,032,026      90.7
```

**Fake-subscriber detection logic (built-in):**
- `views_per_subscriber < 20` → abnormally low engagement ratio
- `avg_views_per_video < 300` (for channels with 5K+ subs) → dead or purchased audience

Results auto-saved to `reports/channel_snapshot_YYYY-MM-DD.csv` for weekly tracking.

---

## 📈 Script 2: `video_retention_report.py` — Your Channel Deep Dive

Pulls **private analytics** from your own channel via OAuth.

```bash
python3 video_retention_report.py dQw4w9WgXcQ
```

**What you get:**
```
=== My Video Title (2026-07-10) ===
Views: 272  Avg Duration(s): 199  Avg %: 32.1  Impressions: 4,312  CTR(%): 6.3

[Traffic Sources]
  BROWSE_FEATURES              146 views
  YT_SEARCH                     71 views
  SUGGESTED_VIDEOS              30 views

Retention curve saved: reports/retention_dQw4w9WgXcQ_2026-07-15.csv
→ Paste this CSV into Claude/ChatGPT for exact cliff-point analysis
```

**The retention CSV** gives you second-by-second drop-off data. Paste it into any AI assistant for pinpoint diagnosis ("viewers drop 8% at 3:12 — check what's on screen there").

---

## 🤖 Automation with cron

```bash
# Weekly competitor snapshot every Monday 9am
0 9 * * 1 cd /path/to/yt-channel-analyzer && python3 channel_snapshot.py @competitor1 @competitor2 >> reports/weekly.log

# Auto retention report 3 days after upload (pair with your upload workflow)
0 9 * * * cd /path/to/yt-channel-analyzer && python3 video_retention_report.py $(cat latest_video_id.txt) >> reports/daily_retention.log
```

Works natively with **Hermes agent** or any local AI agent via cron/launchd for zero-touch weekly reports.

---

## 🛠️ Setup

### Requirements
```bash
pip install -r requirements.txt
```

### For `channel_snapshot.py` (competitor analysis)
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Enable **YouTube Data API v3**
3. Create an **API Key** credential
4. Add to `.env`:
```
YT_API_KEY=your_api_key_here
```

### For `video_retention_report.py` (your channel analytics)
1. Enable **YouTube Analytics API** in the same project
2. Create an **OAuth 2.0 Client ID** → Application type: **Desktop app**
3. Download `client_secret.json` → save in project root
4. First run opens a browser for Google login. After that, `token.json` handles auth automatically.

---

## 📁 Project Structure

```
yt-channel-analyzer/
├── channel_snapshot.py         # Competitor analysis (API key only)
├── video_retention_report.py   # Own channel deep dive (OAuth)
├── requirements.txt
├── .env.example                # Copy to .env and fill in your key
├── .gitignore                  # .env, client_secret.json, token.json excluded
└── reports/                    # Auto-created, all CSVs saved here
```

---

## 🔐 Security

**Never commit your API keys.**  
`.env`, `client_secret.json`, and `token.json` are in `.gitignore` by default.  
If you accidentally push a key, revoke it immediately in [Google Cloud Console](https://console.cloud.google.com/apis/credentials).

---

## 💡 Use Cases

- **Content creators** — track competitor channels weekly, find what topics are winning
- **AI educators** — demo of YouTube API + Python automation (great for courses)
- **Agency / MCN** — bulk channel audits to detect inflated metrics before partnerships
- **Researchers** — collect YouTube data for analysis without scraping
- **AI agent builders** — drop into Hermes / n8n / any agent pipeline for automated reporting

---

## 🗺️ Roadmap

- [ ] `video_list.py` — pull full video catalog of any channel (title, views, tags, publish date)
- [ ] `niche_scanner.py` — scan top 20 channels in a keyword niche, rank by avg views
- [ ] `title_pattern.py` — extract high-performing title patterns using NLP
- [ ] Telegram notification integration (send weekly report to your bot)
- [ ] Dashboard mode (simple HTML report)

PRs welcome. If you find a fake channel in the wild, open an issue with the handle — we'll use it as a test case.

---

## 📄 License

MIT — free to use, modify, and distribute.

---

## 🙋 About

Made by **2GOSOO AI LAB** — AI education for everyone, from beginners to builders.  
YouTube: [2고수클래스](https://www.youtube.com/@2gosooclass)  
Website: [2gosoo.com](https://2gosoo.com)  
Prompt Library: [2GOSOO AI Prompt Lab](https://2gosooaipromptlab.com)

*If this saved you time, a ⭐ helps others find it.*
