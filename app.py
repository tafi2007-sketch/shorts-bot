"""
ShortsManager – Flask backend
Run with: python app.py
"""
from flask import Flask, jsonify, request, render_template
import json
import os
import uuid
import threading
from datetime import datetime, date, timedelta

app = Flask(__name__)

# ── Data file paths ─────────────────────────────────────────────
SCHEDULED_FILE  = 'scheduled_posts.json'
HISTORY_FILE    = 'posting_history.json'
SAVED_FILE      = 'saved_clips.json'

# ── Try to import real clip collectors ──────────────────────────
try:
    from find_clips import collect_twitch_clips, collect_reddit_clips
    CLIPS_AVAILABLE = True
except Exception:
    CLIPS_AVAILABLE = False

# ── Global search state ─────────────────────────────────────────
_search = {'status': 'idle', 'results': [], 'error': None}
_search_lock = threading.Lock()


# ═══════════════════════════════════════════════════════════════
# JSON helpers
# ═══════════════════════════════════════════════════════════════

def load_json(path, default=None):
    if default is None:
        default = []
    if not os.path.exists(path):
        _save_json(path, default)
        return default
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return default

def _save_json(path, data):
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=2, default=str)


# ═══════════════════════════════════════════════════════════════
# Domain helpers
# ═══════════════════════════════════════════════════════════════

def _posted_dates():
    posted = set()
    for h in load_json(HISTORY_FILE):
        if h.get('posted_at'):
            posted.add(h['posted_at'][:10])
        elif h.get('date'):
            posted.add(h['date'])
    for s in load_json(SCHEDULED_FILE):
        if s.get('posted'):
            if s.get('posted_at'):
                posted.add(s['posted_at'][:10])
            elif s.get('date'):
                posted.add(s['date'])
    return posted

def _has_posted_today():
    return date.today().strftime('%Y-%m-%d') in _posted_dates()

def _streak():
    posted = _posted_dates()
    if not posted:
        return 0
    streak = 0
    day = date.today()
    if day.strftime('%Y-%m-%d') not in posted:
        day -= timedelta(days=1)
    while day.strftime('%Y-%m-%d') in posted:
        streak += 1
        day -= timedelta(days=1)
    return streak

def _mock_clips():
    return [
        {'id': str(uuid.uuid4()), 'source': 'twitch', 'title': 'Insane 1v5 clutch to win the championship',         'url': 'https://clips.twitch.tv/example1', 'view_count': 89400,  'broadcaster': 'ProGamer_TV',    'subreddit': None,        'game_name': 'Valorant'},
        {'id': str(uuid.uuid4()), 'source': 'twitch', 'title': 'Streamer gets 500 gifted subs in one second',        'url': 'https://clips.twitch.tv/example2', 'view_count': 156000, 'broadcaster': 'BigStreamer',     'subreddit': None,        'game_name': 'Just Chatting'},
        {'id': str(uuid.uuid4()), 'source': 'twitch', 'title': 'Perfect 360 no-scope from across the map',           'url': 'https://clips.twitch.tv/example3', 'view_count': 45200,  'broadcaster': 'SnipeKing',      'subreddit': None,        'game_name': 'CS2'},
        {'id': str(uuid.uuid4()), 'source': 'twitch', 'title': 'Pro leaks secret strat accidentally on stream',      'url': 'https://clips.twitch.tv/example4', 'view_count': 234000, 'broadcaster': 'TopTierPro',     'subreddit': None,        'game_name': 'League of Legends'},
        {'id': str(uuid.uuid4()), 'source': 'twitch', 'title': 'Final kill perfectly ends the championship match',   'url': 'https://clips.twitch.tv/example5', 'view_count': 67800,  'broadcaster': 'ChampionStream', 'subreddit': None,        'game_name': 'Apex Legends'},
        {'id': str(uuid.uuid4()), 'source': 'reddit', 'title': 'Speedrun skip just broke the world record',          'url': 'https://v.redd.it/example6',       'view_count': None,   'broadcaster': None,             'subreddit': 'speedrun',  'game_name': 'speedrun'},
        {'id': str(uuid.uuid4()), 'source': 'reddit', 'title': 'Minecraft player finds rarest structure in survival','url': 'https://v.redd.it/example7',       'view_count': None,   'broadcaster': None,             'subreddit': 'Minecraft', 'game_name': 'Minecraft'},
        {'id': str(uuid.uuid4()), 'source': 'reddit', 'title': 'The luckiest moment in gaming history',              'url': 'https://v.redd.it/example8',       'view_count': None,   'broadcaster': None,             'subreddit': 'gaming',    'game_name': 'gaming'},
        {'id': str(uuid.uuid4()), 'source': 'reddit', 'title': 'This softwaregore clip is absolutely unhinged',      'url': 'https://v.redd.it/example9',       'view_count': None,   'broadcaster': None,             'subreddit': 'softwaregore','game_name': 'softwaregore'},
    ]


# ═══════════════════════════════════════════════════════════════
# Routes – pages
# ═══════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template('index.html')


# ═══════════════════════════════════════════════════════════════
# Routes – dashboard
# ═══════════════════════════════════════════════════════════════

@app.route('/api/dashboard')
def api_dashboard():
    now = datetime.now()
    hour = now.hour
    greeting = 'morning' if hour < 12 else ('afternoon' if hour < 17 else 'evening')
    posted_today = _has_posted_today()

    # Build combined recent-posts list (history + posted scheduled)
    all_posts = []
    for h in load_json(HISTORY_FILE):
        all_posts.append({'date': h['date'], 'title': h.get('title', 'Untitled'), 'source': h.get('source', 'manual'), 'posted_at': h.get('posted_at')})
    for s in load_json(SCHEDULED_FILE):
        if s.get('posted'):
            all_posts.append({'date': s['date'], 'title': s['title'], 'source': s.get('source', 'manual'), 'posted_at': s.get('posted_at')})

    all_posts.sort(key=lambda x: x.get('posted_at') or x['date'], reverse=True)
    seen, recent = set(), []
    for p in all_posts:
        key = (p['date'], p['title'])
        if key not in seen and len(recent) < 5:
            seen.add(key)
            recent.append(p)

    return jsonify({
        'greeting':     greeting,
        'date':         now.strftime('%A, %B %d, %Y'),
        'streak':       _streak(),
        'posted_today': posted_today,
        'alert':        (not posted_today) and (hour >= 18),
        'recent_posts': recent,
    })


# ═══════════════════════════════════════════════════════════════
# Routes – clip finder
# ═══════════════════════════════════════════════════════════════

@app.route('/api/clips/search', methods=['POST'])
def api_search():
    global _search
    with _search_lock:
        if _search['status'] == 'searching':
            return jsonify({'error': 'Already searching'}), 409
        _search = {'status': 'searching', 'results': [], 'error': None}

    def run():
        global _search
        try:
            if CLIPS_AVAILABLE:
                twitch = collect_twitch_clips()
                reddit = collect_reddit_clips()
                clips = [{'id': str(uuid.uuid4()), **c} for c in twitch + reddit]
            else:
                import time; time.sleep(2)
                clips = _mock_clips()
            with _search_lock:
                _search = {'status': 'done', 'results': clips, 'error': None}
        except Exception as exc:
            with _search_lock:
                _search = {'status': 'error', 'results': [], 'error': str(exc)}

    threading.Thread(target=run, daemon=True).start()
    return jsonify({'message': 'started'})


@app.route('/api/clips/status')
def api_search_status():
    with _search_lock:
        return jsonify(_search)


@app.route('/api/clips/saved', methods=['GET'])
def api_get_saved():
    return jsonify(load_json(SAVED_FILE))


@app.route('/api/clips/saved', methods=['POST'])
def api_save_clip():
    data = request.json or {}
    clips = load_json(SAVED_FILE)
    clip = {
        'id':          str(uuid.uuid4()),
        'title':       data.get('title', ''),
        'source':      data.get('source', ''),
        'url':         data.get('url', ''),
        'view_count':  data.get('view_count'),
        'broadcaster': data.get('broadcaster', ''),
        'subreddit':   data.get('subreddit', ''),
        'game_name':   data.get('game_name', ''),
        'saved_at':    datetime.now().isoformat(),
    }
    clips.append(clip)
    _save_json(SAVED_FILE, clips)
    return jsonify(clip), 201


@app.route('/api/clips/saved/<clip_id>', methods=['DELETE'])
def api_delete_saved(clip_id):
    clips = [c for c in load_json(SAVED_FILE) if c['id'] != clip_id]
    _save_json(SAVED_FILE, clips)
    return jsonify({'ok': True})


# ═══════════════════════════════════════════════════════════════
# Routes – scheduler
# ═══════════════════════════════════════════════════════════════

@app.route('/api/schedule', methods=['GET'])
def api_get_schedule():
    return jsonify(load_json(SCHEDULED_FILE))


@app.route('/api/schedule', methods=['POST'])
def api_create_post():
    data = request.json or {}
    posts = load_json(SCHEDULED_FILE)
    post = {
        'id':         str(uuid.uuid4()),
        'date':       data.get('date', ''),
        'time':       data.get('time', '12:00'),
        'title':      data.get('title', ''),
        'source':     data.get('source', 'manual'),
        'posted':     False,
        'created_at': datetime.now().isoformat(),
    }
    posts.append(post)
    _save_json(SCHEDULED_FILE, posts)
    return jsonify(post), 201


@app.route('/api/schedule/<post_id>', methods=['PUT'])
def api_update_post(post_id):
    data = request.json or {}
    posts = load_json(SCHEDULED_FILE)
    for p in posts:
        if p['id'] == post_id:
            for k, v in data.items():
                if k != 'id':
                    p[k] = v
            break
    _save_json(SCHEDULED_FILE, posts)
    return jsonify({'ok': True})


@app.route('/api/schedule/<post_id>', methods=['DELETE'])
def api_delete_post(post_id):
    all_posts = load_json(SCHEDULED_FILE)
    deleted = next((p for p in all_posts if p['id'] == post_id), None)
    posts = [p for p in all_posts if p['id'] != post_id]
    _save_json(SCHEDULED_FILE, posts)

    # If the post was marked as posted, remove matching entries from history too
    if deleted and deleted.get('posted'):
        title = deleted.get('title', '')
        sched_date = deleted.get('date', '')
        history = load_json(HISTORY_FILE)
        history = [
            h for h in history
            if not (
                h.get('title') == title and
                (h.get('scheduled_date') == sched_date or h.get('date') == sched_date)
            )
        ]
        _save_json(HISTORY_FILE, history)

    return jsonify({'ok': True})


@app.route('/api/schedule/<post_id>/posted', methods=['POST'])
def api_mark_posted(post_id):
    posts = load_json(SCHEDULED_FILE)
    marked = None
    for p in posts:
        if p['id'] == post_id:
            p['posted']    = True
            p['posted_at'] = datetime.now().isoformat()
            marked = p
            break
    _save_json(SCHEDULED_FILE, posts)

    if marked:
        history = load_json(HISTORY_FILE)
        history.append({
            'id':             str(uuid.uuid4()),
            'title':          marked['title'],
            'date':           marked['date'],
            'scheduled_date': marked['date'],
            'posted_at':      marked['posted_at'],
            'source':         marked.get('source', 'manual'),
        })
        _save_json(HISTORY_FILE, history)

    return jsonify({'ok': True})


# ═══════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    def _open_browser():
        import time, webbrowser
        time.sleep(1.2)
        webbrowser.open('http://localhost:5000')

    threading.Thread(target=_open_browser, daemon=True).start()
    app.run(debug=True, use_reloader=False, port=5000)
