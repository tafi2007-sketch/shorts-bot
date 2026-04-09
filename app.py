"""
ShortsManager – Flask backend
Run with: python app.py
"""
from flask import Flask, jsonify, request, render_template
import json
import os
import uuid
import threading
import tempfile
from datetime import datetime, date, timedelta

app = Flask(__name__)

# ── Data file paths ─────────────────────────────────────────────
SCHEDULED_FILE          = 'scheduled_posts.json'
HISTORY_FILE            = 'posting_history.json'
SAVED_FILE              = 'saved_clips.json'
HIDDEN_CLIPS_FILE       = 'hidden_clips.json'
USED_CLIPS_GAMING_FILE  = 'used_clips_gaming.json'
USED_CLIPS_VALORANT_FILE= 'used_clips_valorant.json'

# ── Try to import real clip collectors ──────────────────────────
try:
    from find_clips import (
        search_general_gaming, search_valorant,
        load_used_clips,
    )
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
    data  = request.json or {}
    niche = data.get('niche', 'gaming')

    with _search_lock:
        if _search['status'] == 'searching':
            return jsonify({'error': 'Already searching'}), 409
        _search = {'status': 'searching', 'results': [], 'error': None}

    def run():
        global _search
        try:
            if CLIPS_AVAILABLE:
                if niche == 'valorant':
                    twitch, reddit = search_valorant()
                    used_file = USED_CLIPS_VALORANT_FILE
                else:
                    twitch, reddit = search_general_gaming()
                    used_file = USED_CLIPS_GAMING_FILE
                used_urls = load_used_clips(used_file)
                clips = []
                for c in twitch + reddit:
                    clip = {'id': str(uuid.uuid4()), **c}
                    clip['already_used'] = c['url'] in used_urls
                    clips.append(clip)
            else:
                import time; time.sleep(2)
                clips = _mock_clips()
            # Filter out hidden clips
            hidden_urls = set(load_json(HIDDEN_CLIPS_FILE))
            clips = [c for c in clips if c.get('url') not in hidden_urls]
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
# Routes – library
# ═══════════════════════════════════════════════════════════════

@app.route('/api/library', methods=['GET'])
def api_get_library():
    return jsonify(load_json(SAVED_FILE))


@app.route('/api/library/save', methods=['POST'])
def api_library_save():
    data  = request.json or {}
    clips = load_json(SAVED_FILE)
    url   = data.get('url', '')
    if any(c.get('url') == url for c in clips):
        return jsonify({'error': 'Already saved'}), 409
    clip = {
        'id':          str(uuid.uuid4()),
        'title':       data.get('title', ''),
        'source':      data.get('source', ''),
        'url':         url,
        'view_count':  data.get('view_count'),
        'game_name':   data.get('game_name', ''),
        'niche':       data.get('niche', 'gaming'),
        'saved_at':    datetime.now().isoformat(),
        'notes':       '',
    }
    clips.append(clip)
    _save_json(SAVED_FILE, clips)
    return jsonify(clip), 201


@app.route('/api/library/<clip_id>', methods=['DELETE'])
def api_library_delete(clip_id):
    clips = [c for c in load_json(SAVED_FILE) if c['id'] != clip_id]
    _save_json(SAVED_FILE, clips)
    return jsonify({'ok': True})


@app.route('/api/library/<clip_id>/posted', methods=['POST'])
def api_library_posted(clip_id):
    clips = load_json(SAVED_FILE)
    clip  = next((c for c in clips if c['id'] == clip_id), None)
    if not clip:
        return jsonify({'error': 'Not found'}), 404

    # Add to history
    history = load_json(HISTORY_FILE)
    history.append({
        'id':        str(uuid.uuid4()),
        'title':     clip['title'],
        'date':      date.today().strftime('%Y-%m-%d'),
        'posted_at': datetime.now().isoformat(),
        'source':    clip.get('source', 'manual'),
        'url':       clip.get('url', ''),
    })
    _save_json(HISTORY_FILE, history)

    # Add to correct used_clips file
    niche     = clip.get('niche', 'gaming')
    used_file = USED_CLIPS_VALORANT_FILE if niche == 'valorant' else USED_CLIPS_GAMING_FILE
    used      = load_json(used_file)
    if not any(u.get('url') == clip['url'] for u in used):
        used.append({
            'url':       clip['url'],
            'title':     clip['title'],
            'source':    clip.get('source', 'manual'),
            'date_used': datetime.now().isoformat(),
        })
        _save_json(used_file, used)

    # Remove from library
    clips = [c for c in clips if c['id'] != clip_id]
    _save_json(SAVED_FILE, clips)
    return jsonify({'ok': True})


@app.route('/api/library/<clip_id>/notes', methods=['POST'])
def api_library_notes(clip_id):
    data  = request.json or {}
    clips = load_json(SAVED_FILE)
    for c in clips:
        if c['id'] == clip_id:
            c['notes'] = data.get('notes', '')
            break
    _save_json(SAVED_FILE, clips)
    return jsonify({'ok': True})


@app.route('/api/library/undo-posted', methods=['POST'])
def api_library_undo_posted():
    data     = request.json or {}
    clip_url = data.get('url', '')
    niche    = data.get('niche', 'gaming')

    # Remove the most-recent matching entry from history
    history = load_json(HISTORY_FILE)
    # Remove last occurrence matching the url
    removed_one = False
    new_history = []
    for h in reversed(history):
        if not removed_one and h.get('url') == clip_url:
            removed_one = True  # skip (remove) this entry
        else:
            new_history.append(h)
    _save_json(HISTORY_FILE, list(reversed(new_history)))

    # Remove from the correct used_clips file
    used_file = USED_CLIPS_VALORANT_FILE if niche == 'valorant' else USED_CLIPS_GAMING_FILE
    used = load_json(used_file)
    used = [u for u in used if u.get('url') != clip_url]
    _save_json(used_file, used)

    # Re-add to saved_clips.json (only if not already there)
    clips = load_json(SAVED_FILE)
    if not any(c.get('url') == clip_url for c in clips):
        restore = {k: v for k, v in data.items()}
        restore.setdefault('saved_at', datetime.now().isoformat())
        clips.append(restore)
        _save_json(SAVED_FILE, clips)

    return jsonify({'ok': True})


@app.route('/api/clips/hide', methods=['POST'])
def api_hide_clip():
    data = request.json or {}
    url  = data.get('url', '')
    if not url:
        return jsonify({'error': 'URL required'}), 400
    hidden = load_json(HIDDEN_CLIPS_FILE)
    if url not in hidden:
        hidden.append(url)
        _save_json(HIDDEN_CLIPS_FILE, hidden)
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
# Routes – YouTube
# ═══════════════════════════════════════════════════════════════

try:
    from youtube_uploader import get_auth_status, get_youtube_service, generate_metadata, upload_video, revoke_token
    YOUTUBE_AVAILABLE = True
except Exception:
    YOUTUBE_AVAILABLE = False

_yt_auth_lock = threading.Lock()


@app.route('/api/youtube/auth-status')
def api_yt_auth_status():
    if not YOUTUBE_AVAILABLE:
        return jsonify({'authenticated': False, 'error': 'YouTube uploader not available'})
    try:
        auth, email = get_auth_status()
        return jsonify({'authenticated': auth, 'email': email})
    except Exception as e:
        return jsonify({'authenticated': False, 'error': str(e)})


@app.route('/api/youtube/authenticate', methods=['POST'])
def api_yt_authenticate():
    if not YOUTUBE_AVAILABLE:
        return jsonify({'success': False, 'error': 'YouTube uploader not available'}), 500

    def run_auth():
        with _yt_auth_lock:
            try:
                get_youtube_service()
            except Exception as e:
                print(f'YouTube auth error: {e}')

    threading.Thread(target=run_auth, daemon=True).start()
    return jsonify({'success': True, 'message': 'OAuth flow started — check your browser'})


@app.route('/api/youtube/disconnect', methods=['POST'])
def api_yt_disconnect():
    if not YOUTUBE_AVAILABLE:
        return jsonify({'success': False, 'error': 'YouTube uploader not available'}), 500
    try:
        revoke_token()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/youtube/generate-metadata', methods=['POST'])
def api_yt_generate_metadata():
    if not YOUTUBE_AVAILABLE:
        return jsonify({'error': 'YouTube uploader not available'}), 500
    data = request.json or {}
    clip_title  = data.get('clip_title', '')
    clip_source = data.get('clip_source', '')
    niche       = data.get('niche', 'gaming')
    clip_url    = data.get('clip_url', '')
    try:
        meta = generate_metadata(clip_title, clip_source, niche, clip_url)
        return jsonify(meta)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/youtube/upload', methods=['POST'])
def api_yt_upload():
    if not YOUTUBE_AVAILABLE:
        return jsonify({'error': 'YouTube uploader not available'}), 500

    video_file = request.files.get('video')
    if not video_file:
        return jsonify({'error': 'No video file provided'}), 400

    title       = request.form.get('title', 'Untitled')
    description = request.form.get('description', '')
    tags_raw    = request.form.get('tags', '')
    category    = request.form.get('category', '20')

    tags = [t.strip() for t in tags_raw.split(',') if t.strip()] if tags_raw else []

    # Save to a temp file
    suffix = os.path.splitext(video_file.filename or 'video.mp4')[1] or '.mp4'
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        video_file.save(tmp.name)
        tmp.close()
        video_id, studio_url = upload_video(tmp.name, title, description, tags, category)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

    return jsonify({'video_id': video_id, 'studio_url': studio_url})


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
