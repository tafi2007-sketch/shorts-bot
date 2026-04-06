# YouTube Shorts Bot — Karma & Justice Niche

Automate finding, downloading, and generating metadata for viral karma/justice video clips.

---

## Folder Structure

```
shorts-bot/
├── find_clips.py        # Search Reddit for viral karma/justice clips
├── download_clips.py    # Download chosen clips to your computer
├── generate_metadata.py # Use Claude AI to write YouTube titles & descriptions
├── clips/               # Downloaded videos are saved here
├── metadata/            # Generated YouTube metadata (.txt files) are saved here
├── requirements.txt     # Python packages needed
└── README.md            # This file
```

---

## Setup (Do This Once)

### Step 1 — Install Python
Download and install Python from https://www.python.org/downloads/
Make sure to check "Add Python to PATH" during installation.

### Step 2 — Open a terminal in this folder
- On Windows: open the `shorts-bot` folder, then click the address bar, type `cmd`, and press Enter.

### Step 3 — Install required packages
```
pip install -r requirements.txt
```

### Step 4 — Set your Claude API key
You need an API key from Anthropic to use `generate_metadata.py`.

1. Go to https://console.anthropic.com and create a free account.
2. Create an API key.
3. Set it as an environment variable:

**Windows (Command Prompt):**
```
setx ANTHROPIC_API_KEY "your-api-key-here"
```
Close and reopen your terminal after running this.

---

## How to Use

### Step 1 — Find viral clips
```
python find_clips.py
```
This searches Reddit and prints a list of viral video URLs.
Copy any URL you like for the next step.

---

### Step 2 — Download a clip
1. Open `download_clips.py` in a text editor.
2. Find the `CLIPS_TO_DOWNLOAD` list (around line 50).
3. Paste your URLs inside the list like this:

```python
CLIPS_TO_DOWNLOAD = [
    "https://v.redd.it/abc123",
    "https://www.youtube.com/watch?v=xyz",
]
```

4. Save the file and run:
```
python download_clips.py
```
Your videos will appear in the `clips/` folder.

---

### Step 3 — Generate YouTube metadata
1. Open `generate_metadata.py` in a text editor.
2. Find the `CLIP_DESCRIPTION` variable (around line 50).
3. Replace the placeholder text with a description of your clip. Example:

```python
CLIP_DESCRIPTION = "A speeding driver cuts off a police car and immediately gets pulled over."
```

4. Save the file and run:
```
python generate_metadata.py
```
A `.txt` file with your YouTube title, description, and tags will appear in the `metadata/` folder.

---

## Tips

- The best time to post YouTube Shorts is between 6 PM – 10 PM in your target audience's timezone.
- Always check that you have the right to repost a clip before uploading it.
- Use the generated metadata as a starting point — feel free to edit it before posting.
