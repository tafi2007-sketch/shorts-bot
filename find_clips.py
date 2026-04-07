# find_clips.py
# ---------------------------------------------------------------
# PURPOSE:
#   Fetches viral gaming clips from TWO sources simultaneously:
#     1. Twitch API  — top clips across ALL games (10,000+ views)
#     2. Reddit RSS  — top posts with video links from 20 subreddits
#   Uses threading so both sources run at the same time.
#   Displays a polished terminal UI with colorama, lets you pick
#   clips, and saves choices to chosen_clips.json.
#
# HOW TO RUN:
#   python find_clips.py
# ---------------------------------------------------------------

import json
import os
import sys
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

import requests
from colorama import Fore, Back, Style, init as colorama_init
from dotenv import load_dotenv

load_dotenv()
colorama_init(autoreset=True)

# ---------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------

OUTPUT_FILE = "chosen_clips.json"
MIN_TWITCH_VIEWS = 10_000

REDDIT_SUBREDDITS = [
    "gaming",
    "Minecraft",
    "minecraftfunny",
    "RobloxFunny",
    "roblox",
    "GrandTheftAutoV",
    "LivestreamFail",
    "FortniteBR",
    "Overwatch",
    "LeagueOfLegends",
    "apexlegends",
    "Unexpected",
    "HoldMyBeer",
    "ThereWasAnAttempt",
    "WatchPeopleDieInside",
    "GamersBeingBros",
    "nextfuckinglevel",
    "softwaregore",
    "valorant",
    "CODWarzone",
]

VIDEO_DOMAINS = ["v.redd.it", "clips.twitch.tv"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

SPINNER_CHARS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

_ATOM_NS = "http://www.w3.org/2005/Atom"


# ---------------------------------------------------------------
# UI HELPERS
# ---------------------------------------------------------------

def print_header():
    banner = "     🎮 GAMING CLIP FINDER v1.0 🎮     "
    width = len(banner)
    top    = "╔" + "═" * width + "╗"
    middle = "║" + banner + "║"
    bottom = "╚" + "═" * width + "╝"
    print()
    print(Fore.MAGENTA + Style.BRIGHT + top)
    print(Fore.MAGENTA + Style.BRIGHT + middle)
    print(Fore.MAGENTA + Style.BRIGHT + bottom)
    print()


def err(msg: str):
    print(Fore.RED + f"  ✗ {msg}" + Style.RESET_ALL)


def _card_width() -> int:
    try:
        return min(os.get_terminal_size().columns - 2, 60)
    except OSError:
        return 58


def print_card(lines: list[tuple[str, str]]):
    """Print a box card. Each item is (color_prefix, text)."""
    width = _card_width()
    border_color = Fore.WHITE + Style.DIM
    print(border_color + "  ┌" + "─" * width + "┐")
    for color, text in lines:
        # Truncate if needed, pad to width
        visible = text
        if len(visible) > width - 2:
            visible = visible[: width - 5] + "..."
        padded = visible.ljust(width - 2)
        print(border_color + "  │ " + color + padded + border_color + " │")
    print(border_color + "  └" + "─" * width + "┘")


def print_summary(twitch_count: int, reddit_count: int):
    total = twitch_count + reddit_count
    print(
        Fore.GREEN + Style.BRIGHT + f"  ✅ Found "
        + Fore.MAGENTA + Style.BRIGHT + f"{twitch_count} Twitch clips"
        + Fore.WHITE + " │ "
        + Fore.GREEN + Style.BRIGHT + f"{reddit_count} Reddit clips"
        + Fore.WHITE + " │ "
        + Fore.CYAN + Style.BRIGHT + f"{total} total"
        + Style.RESET_ALL
    )
    print()


def print_selection_prompt(total: int):
    width = _card_width()
    border_color = Fore.CYAN + Style.BRIGHT
    lines = [
        (Fore.WHITE + Style.BRIGHT, "Enter clip numbers separated by commas"),
        (Fore.WHITE + Style.DIM,    f"Example:  1,3,5   or type 'all'   (1–{total})"),
    ]
    print()
    print(border_color + "  ┌" + "─" * width + "┐")
    for color, text in lines:
        padded = text.ljust(width - 2)
        print(border_color + "  │ " + color + padded + border_color + " │")
    print(border_color + "  └" + "─" * width + "┘")


# ---------------------------------------------------------------
# SPINNER — runs in its own thread until stopped
# ---------------------------------------------------------------

class Spinner:
    def __init__(self, label: str, color=Fore.CYAN):
        self._label = label
        self._color = color
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop_event.set()
        self._thread.join()
        # Clear the spinner line
        sys.stdout.write("\r" + " " * (len(self._label) + 6) + "\r")
        sys.stdout.flush()

    def _spin(self):
        i = 0
        while not self._stop_event.is_set():
            frame = SPINNER_CHARS[i % len(SPINNER_CHARS)]
            sys.stdout.write(f"\r  {self._color}{frame}{Style.RESET_ALL} {self._label}")
            sys.stdout.flush()
            time.sleep(0.08)
            i += 1


# ---------------------------------------------------------------
# SOURCE 1 — TWITCH API
# ---------------------------------------------------------------

def get_twitch_token() -> str | None:
    client_id     = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")

    if not client_id or not client_secret:
        err("TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET missing from .env")
        return None

    try:
        resp = requests.post(
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id":     client_id,
                "client_secret": client_secret,
                "grant_type":    "client_credentials",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        err(f"Twitch auth failed: {e}")
        return None


def collect_twitch_clips() -> list:
    client_id = os.getenv("TWITCH_CLIENT_ID")
    token = get_twitch_token()
    if not token or not client_id:
        return []

    three_months_ago = (datetime.utcnow() - timedelta(days=90)).strftime('%Y-%m-%dT%H:%M:%SZ')

    try:
        resp = requests.get(
            "https://api.twitch.tv/helix/clips",
            params={"first": 50, "language": "en", "started_at": three_months_ago},
            headers={
                "Authorization": f"Bearer {token}",
                "Client-Id":     client_id,
            },
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json().get("data", [])
    except Exception as e:
        err(f"Twitch clips fetch failed: {e}")
        return []

    clips = []
    for c in raw:
        url = c.get("url", "")
        views = c.get("view_count", 0)
        if not url or views < MIN_TWITCH_VIEWS:
            continue
        clips.append({
            "source":      "twitch",
            "game_name":   c.get("game_id", ""),   # filled with name below if available
            "title":       c.get("title", "No title"),
            "url":         url,
            "view_count":  views,
            "broadcaster": c.get("broadcaster_name", ""),
            "subreddit":   None,
        })

    clips.sort(key=lambda c: c["view_count"], reverse=True)
    return clips


# ---------------------------------------------------------------
# SOURCE 2 — REDDIT RSS
# ---------------------------------------------------------------

def _has_video_link(text: str) -> bool:
    return any(domain in text for domain in VIDEO_DOMAINS)


def _extract_video_url(text: str) -> str | None:
    for domain in VIDEO_DOMAINS:
        idx = text.find(domain)
        if idx == -1:
            continue
        start = idx
        while start > 0 and text[start - 1] not in ('"', "'", " ", "\n", ">"):
            start -= 1
        end = idx
        while end < len(text) and text[end] not in ('"', "'", " ", "\n", "<"):
            end += 1
        url = text[start:end].strip().rstrip("/")
        if url:
            return url
    return None


def fetch_reddit_rss(subreddit: str) -> list:
    feed_url = f"https://www.reddit.com/r/{subreddit}/top.rss?t=month"
    three_months_ago = datetime.now(timezone.utc) - timedelta(days=90)

    try:
        resp = requests.get(feed_url, headers=HEADERS, timeout=15)

        if resp.status_code == 429:
            return []

        resp.raise_for_status()
        root = ET.fromstring(resp.text)

        clips = []
        for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
            updated_el = entry.find(f"{{{_ATOM_NS}}}updated")
            if updated_el is not None and updated_el.text:
                try:
                    post_date = datetime.fromisoformat(updated_el.text.replace("Z", "+00:00"))
                    if post_date < three_months_ago:
                        continue
                except ValueError:
                    pass

            entry_text = ET.tostring(entry, encoding="unicode")

            if not _has_video_link(entry_text):
                continue

            title_el = entry.find(f"{{{_ATOM_NS}}}title")
            title = title_el.text.strip() if title_el is not None and title_el.text else "No title"

            video_url = _extract_video_url(entry_text)
            if not video_url:
                continue

            clips.append({
                "source":      "reddit",
                "game_name":   subreddit,
                "title":       title,
                "url":         video_url,
                "view_count":  None,
                "broadcaster": None,
                "subreddit":   subreddit,
            })

        return clips

    except ET.ParseError:
        return []
    except Exception:
        return []


def collect_reddit_clips() -> list:
    results: dict[str, list] = {}
    threads = []

    def worker(sub):
        results[sub] = fetch_reddit_rss(sub)

    for sub in REDDIT_SUBREDDITS:
        t = threading.Thread(target=worker, args=(sub,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    all_clips = []
    for sub in REDDIT_SUBREDDITS:
        all_clips.extend(results.get(sub, []))
    return all_clips


# ---------------------------------------------------------------
# COMBINE
# ---------------------------------------------------------------

def collect_all_clips() -> tuple[list, list]:
    """Fetch both sources in parallel. Returns (twitch_clips, reddit_clips)."""
    twitch_clips: list = []
    reddit_clips:  list = []

    twitch_spinner = Spinner("Searching Twitch...", Fore.MAGENTA)
    reddit_spinner = Spinner("Searching Reddit...", Fore.GREEN)

    def run_twitch():
        nonlocal twitch_clips
        twitch_clips = collect_twitch_clips()

    def run_reddit():
        nonlocal reddit_clips
        reddit_clips = collect_reddit_clips()

    twitch_spinner.start()
    reddit_spinner.start()

    t1 = threading.Thread(target=run_twitch, daemon=True)
    t2 = threading.Thread(target=run_reddit, daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    twitch_spinner.stop()
    reddit_spinner.stop()

    # Deduplicate Reddit by URL
    seen: set[str] = set()
    unique_reddit = []
    for clip in reddit_clips:
        if clip["url"] not in seen:
            seen.add(clip["url"])
            unique_reddit.append(clip)

    # Deduplicate Twitch by URL
    seen_tw: set[str] = set()
    unique_twitch = []
    for clip in twitch_clips:
        if clip["url"] not in seen_tw:
            seen_tw.add(clip["url"])
            unique_twitch.append(clip)

    return unique_twitch, unique_reddit


# ---------------------------------------------------------------
# DISPLAY
# ---------------------------------------------------------------

def display_clips(twitch_clips: list, reddit_clips: list) -> list:
    """Render all clip cards and return the combined ordered list."""
    all_clips = twitch_clips + reddit_clips

    if not all_clips:
        err("No clips found. Check your .env credentials and internet connection.")
        return []

    print_summary(len(twitch_clips), len(reddit_clips))

    for i, clip in enumerate(all_clips, start=1):
        if clip["source"] == "twitch":
            views_str = f"{clip['view_count']:,}"
            print_card([
                (Fore.MAGENTA + Style.BRIGHT,  f"[{i}] 🟣 TWITCH"),
                (Fore.YELLOW  + Style.BRIGHT,  f"👁  {views_str} views"),
                (Fore.WHITE   + Style.BRIGHT,  f"📺 Streamer: {clip['broadcaster']}"),
                (Fore.WHITE   + Style.BRIGHT,  f"📝 \"{clip['title']}\""),
                (Fore.WHITE   + Style.DIM,     f"🔗 {clip['url']}"),
            ])
        else:
            sub = clip["subreddit"] or clip["game_name"]
            print_card([
                (Fore.GREEN  + Style.BRIGHT, f"[{i}] 🟢 REDDIT • r/{sub}"),
                (Fore.WHITE  + Style.BRIGHT, f"📝 \"{clip['title']}\""),
                (Fore.WHITE  + Style.DIM,    f"🔗 {clip['url']}"),
            ])
        print()

    return all_clips


# ---------------------------------------------------------------
# USER SELECTION
# ---------------------------------------------------------------

def ask_user_to_pick(clips: list) -> list:
    total = len(clips)
    print_selection_prompt(total)

    while True:
        raw = input(
            Fore.CYAN + Style.BRIGHT + "\n  › " + Style.RESET_ALL
        ).strip()

        if not raw:
            print(Fore.YELLOW + "  No clips selected. Exiting." + Style.RESET_ALL)
            return []

        if raw.lower() == "all":
            return clips[:]

        chosen = []
        invalid = []

        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if part.isdigit():
                n = int(part)
                if 1 <= n <= total:
                    chosen.append(clips[n - 1])
                else:
                    invalid.append(part)
            else:
                invalid.append(part)

        if invalid:
            err(f"Invalid entries: {', '.join(invalid)}. Please try again.")
            continue

        if not chosen:
            err("Nothing valid selected. Please try again.")
            continue

        return chosen


# ---------------------------------------------------------------
# SAVE
# ---------------------------------------------------------------

def save_chosen_clips(chosen: list):
    output = []
    for clip in chosen:
        output.append({
            "title":     clip["title"],
            "url":       clip["url"],
            "source":    clip["source"],
            "game_name": clip["game_name"],
        })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(
        Fore.GREEN + Style.BRIGHT
        + f"\n  ✅ Saved {len(chosen)} clip{'s' if len(chosen) != 1 else ''} to {OUTPUT_FILE}"
        + Style.RESET_ALL
    )
    print(Fore.WHITE + Style.DIM + "  Run  python download_clips.py  to download them.\n")


# ---------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------

def main():
    print_header()

    twitch_clips, reddit_clips = collect_all_clips()
    all_clips = display_clips(twitch_clips, reddit_clips)

    if not all_clips:
        return

    chosen = ask_user_to_pick(all_clips)
    if not chosen:
        return

    print()
    print(Fore.CYAN + Style.BRIGHT + f"  Selected {len(chosen)} clip{'s' if len(chosen) != 1 else ''}:")
    for clip in chosen:
        label = f"🟣 Twitch" if clip["source"] == "twitch" else f"🟢 r/{clip['subreddit']}"
        print(Fore.WHITE + f"    • {label} — \"{clip['title']}\"")

    save_chosen_clips(chosen)


if __name__ == "__main__":
    main()
