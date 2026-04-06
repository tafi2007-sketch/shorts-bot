# generate_metadata.py
# ---------------------------------------------------------------
# PURPOSE:
#   Uses the Claude AI API to automatically generate YouTube metadata
#   optimised for funny gaming Shorts:
#     - A fun, energetic title referencing the specific game
#     - A description with gaming hashtags
#     - A list of gaming-relevant tags
#
# HOW IT WORKS:
#   1. Describe your clip (what happens, which game) in the variable below.
#   2. This script sends that to Claude AI.
#   3. Claude writes the YouTube title, description, and tags.
#   4. The result is saved as a .txt file in the "metadata/" folder.
#
# REQUIREMENTS:
#   - anthropic package: pip install anthropic
#   - ANTHROPIC_API_KEY environment variable set
#     (see README.md for instructions)
# ---------------------------------------------------------------

import anthropic   # The official Claude AI Python library
import os          # Used to read environment variables and manage folders
import re          # Used to clean up filenames

# ---------------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------------

OUTPUT_FOLDER = "metadata"

# ---------------------------------------------------------------
# DESCRIBE YOUR CLIP HERE
#
# Include what happens AND which game it's from.
# Claude will reference the game name in the title and tags.
#
# Example:
#   CLIP_DESCRIPTION = "Minecraft: A creeper sneaks up and explodes
#   right as the player finishes building their house."
# ---------------------------------------------------------------
CLIP_DESCRIPTION = (
    "Describe your funny gaming clip here. "
    "Include the game name and what happens. "
    "Example: Minecraft - A creeper blew up my entire build right as I placed the last block."
)

# Optional: set the game name directly if you know it.
# Leave as empty string "" to let Claude figure it out from the description.
GAME_NAME = ""

# ---------------------------------------------------------------
# THE PROMPT TEMPLATE
# ---------------------------------------------------------------
PROMPT_TEMPLATE = """You are a YouTube Shorts content strategist specialising in funny viral gaming clips.

A creator has a clip with the following description:
"{clip_description}"
{game_line}
Write YouTube metadata for this Short. Your tone must be fun, energetic, and hype — like a gaming creator talking to their audience. Format your response EXACTLY like this:

TITLE:
[One punchy, fun title under 70 characters. Must reference the specific game by name. Make it feel exciting and relatable to gamers.]

DESCRIPTION:
[2-3 sentences hyping up what happens in the clip. Keep it energetic and casual. End with relevant hashtags including #{game_tag} #gaming #funnymoments #shorts]

TAGS:
[20-25 comma-separated tags. Must include: the game name, gaming, funny gaming moments, funny gaming clips, gaming fails, gaming highlights, shorts, youtube shorts, and other tags relevant to the specific game and moment]

Keep it fun, relatable, and optimised to get views from gaming fans."""


def _build_prompt(clip_description: str, game_name: str) -> str:
    """Builds the final prompt, optionally injecting a known game name."""
    if game_name:
        game_line = f'\nThe game featured in the clip is: {game_name}\n'
    else:
        game_line = ""
    return PROMPT_TEMPLATE.format(
        clip_description=clip_description,
        game_line=game_line,
        game_tag=game_name.lower().replace(" ", "") if game_name else "gaming",
    )


def generate_metadata(clip_description: str, game_name: str = "") -> str:
    """
    Sends the clip description to Claude and returns the generated metadata.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable is not set.\n"
            "Please follow the instructions in README.md to set your API key."
        )

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_prompt(clip_description, game_name)

    print("Sending request to Claude AI...")

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return message.content[0].text


def save_metadata(metadata_text: str, clip_description: str, output_folder: str) -> str:
    """
    Saves the generated metadata to a .txt file in the metadata/ folder.
    """
    safe_name = re.sub(r"[^\w\s]", "", clip_description[:40])
    safe_name = safe_name.strip().replace(" ", "_")
    filename = f"{safe_name}.txt"
    filepath = os.path.join(output_folder, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("CLIP DESCRIPTION:\n")
        f.write(clip_description + "\n")
        f.write("\n" + "=" * 60 + "\n\n")
        f.write("GENERATED YOUTUBE METADATA:\n\n")
        f.write(metadata_text)

    print(f"  [OK] Metadata saved to: {filepath}")
    return filepath


def main():
    print("=" * 60)
    print("  YOUTUBE METADATA GENERATOR (powered by Claude AI)")
    print("  Optimised for: Funny Gaming Shorts")
    print("=" * 60)

    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        print(f"Created folder: {OUTPUT_FOLDER}/")

    print(f"\nClip description:\n  {CLIP_DESCRIPTION}")
    if GAME_NAME:
        print(f"Game: {GAME_NAME}")
    print()

    try:
        metadata = generate_metadata(CLIP_DESCRIPTION, GAME_NAME)

        print("\n--- GENERATED METADATA ---\n")
        print(metadata)
        print("\n--------------------------\n")

        save_metadata(metadata, CLIP_DESCRIPTION, OUTPUT_FOLDER)

    except ValueError as e:
        print(f"\n[ERROR] {e}")
    except Exception as e:
        print(f"\n[ERROR] Something went wrong: {e}")

    print("\n" + "=" * 60)
    print("  DONE. Check the 'metadata/' folder for your results.")
    print("=" * 60)


if __name__ == "__main__":
    main()
