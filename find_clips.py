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

OUTPUT_FILE              = "chosen_clips.json"
USED_CLIPS_FILE          = "used_clips.json"          # legacy / CLI default
USED_CLIPS_GAMING_FILE   = "used_clips_gaming.json"
USED_CLIPS_VALORANT_FILE = "used_clips_valorant.json"
MIN_TWITCH_VIEWS         = 10_000
MIN_TWITCH_VIEWS_VALORANT = 1_000

VALORANT_SUBREDDITS_SPECIFIC = [
    "ValorantClips",
    "ValorantCompetitive",
    "VALORANT",
    "ValorantMemes",
    "AgentAcademy",
]

VALORANT_SUBREDDITS_FILTERED = [
    "LivestreamFail",
    "gaming",
    "GamersBeingBros",
]

VALORANT_KEYWORDS = [
    "valorant", "valo", "val", "vct", "radiant", "immortal",
    "episode", "riot games", "jett", "reyna", "sage", "omen",
    "phoenix", "sova", "breach", "brimstone", "cypher", "killjoy",
    "raze", "skye", "yoru", "astra", "kayo", "chamber", "neon",
    "fade", "harbor", "gekko", "deadlock", "iso", "clove", "vyse",
    "tejo", "waylay",
]

REDDIT_SUBREDDITS = [
    # General Gaming
    "gaming",
    "LivestreamFail",
    "GamersBeingBros",
    "Unexpected",
    # Multiplayer/FPS
    "FortniteBR",
    "Overwatch",
    "leagueoflegends",
    "valorant",
    "apexlegends",
    "CODWarzone",
    "RocketLeague",
    "GlobalOffensive",
    "Competitiveoverwatch",
    "smashbros",
    "Battlefield",
    "Rainbow6",
    "halo",
    "destiny2",
    "Warframe",
    # Sandbox/Casual
    "Minecraft",
    "minecraftfunny",
    "RobloxFunny",
    "roblox",
    "GrandTheftAutoV",
    "gtaonline",
    "NoMansSkyTheGame",
    "Terraria",
    "StardewValley",
    "AnimalCrossing",
    # Highlight/Clip Focused
    "perfectlycutscreams",
    "softwaregore",
    "techsupportgore",
    "oops",
    "killthelive",
    # Streamer Clips
    "TwitchMoments",
    # RPG/Adventure
    "Eldenring",
    "skyrim",
    "cyberpunkgame",
    "witcher",
    "Genshin_Impact",
    "HonkaiStarRail",
    "RedDeadRedemption",
    "darksouls",
    # Sports Games
    "FIFA",
    "NBA2k",
    "EAFC",
]

VIDEO_DOMAINS = ["v.redd.it", "clips.twitch.tv"]

NON_GAMING_CATEGORIES = {
    "just chatting",
    "irl",
    "music",
    "art",
    "pools, hot tubs, and beaches",
    "sports",
    "talk shows & podcasts",
    "asmr",
    "travel & outdoors",
    "food & drink",
    "gambling",
    "slots",
}

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
# USED CLIPS TRACKING
# ---------------------------------------------------------------

def load_used_clips(file_path: str = USED_CLIPS_FILE) -> set[str]:
    """Load used clip URLs from a JSON file. Returns a set of URLs."""
    if not os.path.exists(file_path):
        return set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {entry["url"] for entry in data if "url" in entry}
    except Exception:
        return set()


def save_used_clips(chosen: list, file_path: str = USED_CLIPS_FILE):
    """Append newly chosen clips to a used-clips JSON file."""
    existing = []
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []

    existing_urls = {e["url"] for e in existing if "url" in e}
    date_used = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for clip in chosen:
        if clip["url"] not in existing_urls:
            existing.append({
                "url":       clip["url"],
                "title":     clip["title"],
                "source":    clip["source"],
                "date_used": date_used,
            })
            existing_urls.add(clip["url"])

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


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


HARDCODED_GAMES = {
    "27471":      "Minecraft",
    "493244":     "Roblox",
    "32982":      "Grand Theft Auto V",
    "33214":      "Fortnite",
    "21779":      "League of Legends",
    "516575":     "Valorant",
    "511224":     "Apex Legends",
    "512710":     "Call of Duty: Warzone",
    "515025":     "Overwatch 2",
    "1745202096": "EA Sports FC",
}


def get_top_games(client_id: str, token: str) -> dict[str, str]:
    """Fetch top 20 games from Twitch. Returns {game_id: game_name}."""
    try:
        resp = requests.get(
            "https://api.twitch.tv/helix/games/top?first=20",
            headers={
                "Authorization": f"Bearer {token}",
                "Client-Id":     client_id,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return {g["id"]: g["name"] for g in resp.json().get("data", [])}
    except Exception as e:
        err(f"Twitch top games fetch failed: {e}")
        return {}


def fetch_clips_for_game(game_id: str, game_name: str, client_id: str, token: str,
                          three_months_ago: str) -> list:
    """Fetch up to 10 clips for a single game."""
    url = (
        f"https://api.twitch.tv/helix/clips"
        f"?game_id={game_id}&first=10&language=en&started_at={three_months_ago}"
    )
    try:
        resp = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Client-Id":     client_id,
            },
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json().get("data", [])
    except Exception:
        return []

    clips = []
    for c in raw:
        clip_url = c.get("url", "")
        views = c.get("view_count", 0)
        if not clip_url or views < MIN_TWITCH_VIEWS:
            continue
        clips.append({
            "source":      "twitch",
            "game_name":   game_name,
            "title":       c.get("title", "No title"),
            "url":         clip_url,
            "view_count":  views,
            "broadcaster": c.get("broadcaster_name", ""),
            "subreddit":   None,
        })
    return clips


def collect_twitch_clips() -> list:
    client_id = os.getenv("TWITCH_CLIENT_ID")
    token = get_twitch_token()
    if not token or not client_id:
        return []

    three_months_ago = (
        datetime.now(timezone.utc) - timedelta(days=14)
    ).strftime('%Y-%m-%dT%H:%M:%SZ')

    # Step 1: get current top 20 games
    top_games = get_top_games(client_id, token)

    # Step 2 & 3: merge with hardcoded list (top_games wins on name if overlap)
    combined_games: dict[str, str] = {**HARDCODED_GAMES, **top_games}

    # Step 4: fetch clips for all games simultaneously
    results: dict[str, list] = {}

    def worker(gid: str, gname: str):
        results[gid] = fetch_clips_for_game(gid, gname, client_id, token, three_months_ago)

    threads = [
        threading.Thread(target=worker, args=(gid, gname), daemon=True)
        for gid, gname in combined_games.items()
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Combine, deduplicate by URL, sort by view_count
    seen_urls: set[str] = set()
    clips = []
    for game_clips in results.values():
        for clip in game_clips:
            if clip["url"] not in seen_urls:
                seen_urls.add(clip["url"])
                clips.append(clip)

    clips.sort(key=lambda c: c["view_count"], reverse=True)

    # Filter out non-gaming categories
    clips = [
        c for c in clips
        if c.get("game_name") and c["game_name"].lower() not in NON_GAMING_CATEGORIES
    ]

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
    feed_url = f"https://www.reddit.com/r/{subreddit}/top.rss?t=week"
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    try:
        resp = requests.get(feed_url, headers=HEADERS, timeout=15)

        if resp.status_code == 429:
            return []

        resp.raise_for_status()
        root = ET.fromstring(resp.text)

        clips = []
        for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
            published_el = entry.find(f"{{{_ATOM_NS}}}published")
            if published_el is not None and published_el.text:
                try:
                    post_date = datetime.fromisoformat(published_el.text.replace("Z", "+00:00"))
                    if post_date < seven_days_ago:
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
# VALORANT-SPECIFIC SOURCES
# ---------------------------------------------------------------

def collect_valorant_twitch_clips() -> list:
    """Fetch Twitch clips for Valorant (game_id=516575)."""
    client_id = os.getenv("TWITCH_CLIENT_ID")
    token = get_twitch_token()
    if not token or not client_id:
        return []

    fourteen_days_ago = (
        datetime.now(timezone.utc) - timedelta(days=14)
    ).strftime('%Y-%m-%dT%H:%M:%SZ')

    url = (
        f"https://api.twitch.tv/helix/clips"
        f"?game_id=516575&first=20&language=en&started_at={fourteen_days_ago}"
    )
    try:
        resp = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Client-Id":     client_id,
            },
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json().get("data", [])
    except Exception:
        return []

    clips = []
    for c in raw:
        clip_url = c.get("url", "")
        views = c.get("view_count", 0)
        if not clip_url or views < MIN_TWITCH_VIEWS_VALORANT:
            continue
        clips.append({
            "source":      "twitch",
            "game_name":   "Valorant",
            "title":       c.get("title", "No title"),
            "url":         clip_url,
            "view_count":  views,
            "broadcaster": c.get("broadcaster_name", ""),
            "subreddit":   None,
        })
    clips.sort(key=lambda c: c["view_count"], reverse=True)
    return clips


def collect_valorant_reddit_clips() -> list:
    """Fetch Reddit clips from Valorant-specific and filtered general subreddits."""
    results: dict[str, list] = {}
    threads = []

    kw_lower = [k.lower() for k in VALORANT_KEYWORDS]

    def worker(sub: str, filter_kw: bool):
        clips = fetch_reddit_rss(sub)
        if filter_kw:
            clips = [c for c in clips if any(k in c["title"].lower() for k in kw_lower)]
        results[sub] = clips

    for sub in VALORANT_SUBREDDITS_SPECIFIC:
        t = threading.Thread(target=worker, args=(sub, False), daemon=True)
        threads.append(t)
        t.start()

    for sub in VALORANT_SUBREDDITS_FILTERED:
        t = threading.Thread(target=worker, args=(sub, True), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    all_clips = []
    for sub in VALORANT_SUBREDDITS_SPECIFIC + VALORANT_SUBREDDITS_FILTERED:
        all_clips.extend(results.get(sub, []))
    return all_clips


# ---------------------------------------------------------------
# NICHE SEARCH ENTRY POINTS
# ---------------------------------------------------------------

def _dedup(clips: list) -> list:
    seen: set[str] = set()
    out = []
    for c in clips:
        if c["url"] not in seen:
            seen.add(c["url"])
            out.append(c)
    return out


def search_general_gaming() -> tuple[list, list]:
    """Fetch general gaming clips from all sources. Returns (twitch_clips, reddit_clips)."""
    twitch_clips: list = []
    reddit_clips: list = []

    def run_twitch():
        nonlocal twitch_clips
        twitch_clips = collect_twitch_clips()

    def run_reddit():
        nonlocal reddit_clips
        reddit_clips = collect_reddit_clips()

    t1 = threading.Thread(target=run_twitch, daemon=True)
    t2 = threading.Thread(target=run_reddit, daemon=True)
    t1.start(); t2.start()
    t1.join();  t2.join()

    return _dedup(twitch_clips), _dedup(reddit_clips)


def fetch_valorant_classics(year: int, offset: int = 0, limit: int = 10) -> list:
    """Fetch all-time top Valorant clips for a specific year, sorted by view count."""
    client_id = os.getenv("TWITCH_CLIENT_ID")
    token = get_twitch_token()
    if not token or not client_id:
        return []

    url = f"https://api.twitch.tv/helix/clips?game_id=516575&first=100&language=en&started_at={year}-01-01T00:00:00Z&ended_at={year}-12-31T23:59:59Z"
    try:
        resp = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Client-Id":     client_id,
            },
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json().get("data", [])
    except Exception:
        return []

    raw.sort(key=lambda c: c.get("view_count", 0), reverse=True)

    used_valorant = load_used_clips(USED_CLIPS_VALORANT_FILE)
    hidden_clips: set[str] = set()
    hidden_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hidden_clips.json")
    if os.path.exists(hidden_path):
        try:
            with open(hidden_path, "r", encoding="utf-8") as f:
                hidden_clips = set(json.load(f))
        except Exception:
            hidden_clips = set()

    filtered = []
    for rank, c in enumerate(raw, start=1):
        clip_url = c.get("url", "")
        if not clip_url:
            continue
        if clip_url in used_valorant or clip_url in hidden_clips:
            continue
        filtered.append({
            "title":      c.get("title", "No title"),
            "url":        clip_url,
            "view_count": c.get("view_count", 0),
            "game_name":  "Valorant",
            "source":     "twitch",
            "year":       year,
            "rank":       rank,
        })

    return filtered[offset: offset + limit]


def search_valorant() -> tuple[list, list]:
    """Fetch Valorant-specific clips from all sources. Returns (twitch_clips, reddit_clips)."""
    twitch_clips: list = []
    reddit_clips: list = []

    def run_twitch():
        nonlocal twitch_clips
        twitch_clips = collect_valorant_twitch_clips()

    def run_reddit():
        nonlocal reddit_clips
        reddit_clips = collect_valorant_reddit_clips()

    t1 = threading.Thread(target=run_twitch, daemon=True)
    t2 = threading.Thread(target=run_reddit, daemon=True)
    t1.start(); t2.start()
    t1.join();  t2.join()

    return _dedup(twitch_clips), _dedup(reddit_clips)


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

def display_clips(twitch_clips: list, reddit_clips: list, used_urls: set[str]) -> list:
    """Render all clip cards and return the combined ordered list."""
    all_clips = twitch_clips + reddit_clips

    if not all_clips:
        err("No clips found. Check your .env credentials and internet connection.")
        return []

    print_summary(len(twitch_clips), len(reddit_clips))

    for i, clip in enumerate(all_clips, start=1):
        already_used = clip["url"] in used_urls
        if clip["source"] == "twitch":
            views_str = f"{clip['view_count']:,}"
            lines = [
                (Fore.MAGENTA + Style.BRIGHT, f"[{i}] 🟣 TWITCH • {clip['game_name']}"),
                (Fore.YELLOW  + Style.BRIGHT, f"👁  {views_str} views"),
                (Fore.WHITE   + Style.BRIGHT, f"📺 Streamer: {clip['broadcaster']}"),
                (Fore.WHITE   + Style.BRIGHT, f"📝 \"{clip['title']}\""),
                (Fore.WHITE   + Style.DIM,    f"🔗 {clip['url']}"),
            ]
            if already_used:
                lines.insert(1, (Fore.YELLOW + Style.BRIGHT, f"⚠️  ALREADY USED"))
        else:
            sub = clip["subreddit"] or clip["game_name"]
            lines = [
                (Fore.GREEN + Style.BRIGHT, f"[{i}] 🟢 REDDIT • r/{sub}"),
                (Fore.WHITE + Style.BRIGHT, f"📝 \"{clip['title']}\""),
                (Fore.WHITE + Style.DIM,    f"🔗 {clip['url']}"),
            ]
            if already_used:
                lines.insert(1, (Fore.YELLOW + Style.BRIGHT, f"⚠️  ALREADY USED"))
        print_card(lines)
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

    save_used_clips(chosen)

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

    used_urls = load_used_clips()

    twitch_clips, reddit_clips = collect_all_clips()
    all_clips = display_clips(twitch_clips, reddit_clips, used_urls)

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
