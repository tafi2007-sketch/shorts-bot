"""
youtube_uploader.py — YouTube API logic for ShortsManager
"""
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

CREDENTIALS_FILE = os.getenv('YOUTUBE_CREDENTIALS_FILE', 'youtube_credentials.json')
TOKEN_FILE = 'youtube_token.json'
SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube',
]


def get_youtube_service():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())

    return build('youtube', 'v3', credentials=creds)


def get_auth_status():
    """Return (authenticated: bool, email: str|None)."""
    if not os.path.exists(TOKEN_FILE):
        return False, None
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, 'w') as f:
                f.write(creds.to_json())
        if creds.valid:
            # Try to get account email from token file
            with open(TOKEN_FILE, 'r') as f:
                data = json.load(f)
            email = None  # OAuth2 token doesn't include email by default
            return True, email
    except Exception:
        pass
    return False, None


def revoke_token():
    """Delete the saved token file to disconnect YouTube."""
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)


def generate_metadata(clip_title, clip_source, niche, clip_url):
    import anthropic
    client = anthropic.Anthropic()

    system_prompt = (
        "You are an expert YouTube Shorts content strategist with deep knowledge of what performs "
        "best on YouTube in 2026. You have analysed thousands of viral gaming and Valorant Shorts "
        "channels. Generate metadata that maximises discoverability and click-through rate."
    )

    user_prompt = f"""Generate YouTube Shorts metadata for this clip:

Title: {clip_title}
Source: {clip_source}
Niche: {niche}
URL: {clip_url}

Generate:
- Title: max 60 chars, hook-first, high CTR, includes game name
- Description: 3-4 sentences, describes the clip, ends with call to action to subscribe, includes 3-5 inline hashtags. Always end with #Shorts
- Tags: list of 25-30 tags mixing broad (gaming, shorts, clips) and specific (Valorant, VCT, gaming highlights etc)
- Category: always return "20" (Gaming category ID)

Return ONLY valid JSON in this exact format:
{{"title": "...", "description": "...", "tags": [...], "category": "20"}}"""

    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=1024,
        messages=[{'role': 'user', 'content': user_prompt}],
        system=system_prompt,
    )

    content = message.content[0].text.strip()
    match = re.search(r'\{.*\}', content, re.DOTALL)
    if match:
        content = match.group(0)

    return json.loads(content)


def upload_video(video_file_path, title, description, tags, category_id):
    from googleapiclient.http import MediaFileUpload

    youtube = get_youtube_service()

    if '#Shorts' not in description:
        description = description + '\n\n#Shorts'

    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(',') if t.strip()]

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': category_id or '20',
        },
        'status': {
            'privacyStatus': 'private',
        }
    }

    media = MediaFileUpload(
        video_file_path,
        mimetype='video/*',
        resumable=True,
        chunksize=5 * 1024 * 1024,  # 5 MB chunks
    )

    insert_request = youtube.videos().insert(
        part='snippet,status',
        body=body,
        media_body=media,
    )

    response = None
    print('Starting YouTube upload...')
    while response is None:
        status, response = insert_request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f'Upload progress: {pct}%')

    video_id = response['id']
    studio_url = f'https://studio.youtube.com/video/{video_id}/edit'
    print(f'Upload complete! Video ID: {video_id}')
    return video_id, studio_url
