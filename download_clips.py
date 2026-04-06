# download_clips.py
# ---------------------------------------------------------------
# PURPOSE:
#   This script downloads video clips using yt-dlp.
#   yt-dlp is a powerful tool that can download videos from
#   Reddit, YouTube, Streamable, and hundreds of other sites.
#
# HOW IT WORKS:
#   1. You paste the video URL(s) you found with find_clips.py
#      into the CLIPS_TO_DOWNLOAD list below.
#   2. Run this script: python download_clips.py
#   3. The videos are saved into the "clips/" folder.
#
# REQUIREMENTS:
#   - yt-dlp must be installed: pip install yt-dlp
# ---------------------------------------------------------------

import yt_dlp    # The download library
import os        # Used to check and create folders

# ---------------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------------

# Folder where downloaded clips will be saved
OUTPUT_FOLDER = "clips"

# ---------------------------------------------------------------
# PASTE YOUR VIDEO URLs HERE
# (Copy URLs from the output of find_clips.py)
# Each URL goes on its own line inside the list, in quotes.
#
# Example:
#   CLIPS_TO_DOWNLOAD = [
#       "https://v.redd.it/abc123",
#       "https://www.youtube.com/watch?v=xyz789",
#   ]
# ---------------------------------------------------------------
CLIPS_TO_DOWNLOAD = [
    # Paste URLs here
]


def download_clip(url: str, output_folder: str):
    """
    Downloads a single video from the given URL into the output folder.
    """
    print(f"\nDownloading: {url}")

    # yt-dlp options
    ydl_opts = {
        # Save files to the clips/ folder with the video title as filename
        "outtmpl": os.path.join(output_folder, "%(title)s.%(ext)s"),

        # Prefer mp4 format, fallback to best available
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",

        # Show a progress bar while downloading
        "quiet": False,
        "no_warnings": False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print(f"  [OK] Saved to '{output_folder}/' folder.")
    except Exception as e:
        print(f"  [ERROR] Failed to download {url}: {e}")


def main():
    """
    Main function: creates the output folder and downloads all clips.
    """
    print("=" * 60)
    print("  CLIP DOWNLOADER")
    print("=" * 60)

    # Create the clips/ folder if it doesn't exist yet
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        print(f"Created folder: {OUTPUT_FOLDER}/")

    # Check if the user has added any URLs
    if not CLIPS_TO_DOWNLOAD:
        print("\n[!] No URLs found in CLIPS_TO_DOWNLOAD.")
        print("    Open download_clips.py and paste video URLs into the list.")
        return

    print(f"\nFound {len(CLIPS_TO_DOWNLOAD)} clip(s) to download.\n")

    # Download each URL one by one
    for url in CLIPS_TO_DOWNLOAD:
        download_clip(url, OUTPUT_FOLDER)

    print("\n" + "=" * 60)
    print("  ALL DOWNLOADS COMPLETE")
    print(f"  Check your '{OUTPUT_FOLDER}/' folder for the videos.")
    print("=" * 60)


# ---------------------------------------------------------------
# Run the script when executed directly (python download_clips.py)
# ---------------------------------------------------------------
if __name__ == "__main__":
    main()
