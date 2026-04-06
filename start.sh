#!/bin/bash

# Colours
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
WHITE='\033[1;37m'
RESET='\033[0m'

# ========================================
#  ON CLOSE — runs when script exits
# ========================================
on_close() {
    echo ""
    clear
    echo -e "${WHITE}========================================${RESET}"
    echo -e "${WHITE} 💾 ShortsManager - Saving & Syncing...${RESET}"
    echo -e "${WHITE}========================================${RESET}"
    echo ""

    if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
        echo -e "${BLUE}📦 Changes detected - saving to GitHub...${RESET}"
        git add .
        git commit -m "auto-sync $(date '+%Y-%m-%d %H:%M')"
        if git push origin master:main >/dev/null 2>&1; then
            echo -e "${GREEN}✅ Changes saved to GitHub successfully${RESET}"
        else
            echo ""
            echo -e "${RED}========================================${RESET}"
            echo -e "${YELLOW}⚠  WARNING: COULD NOT SAVE TO GITHUB${RESET}"
            echo -e "${RED}========================================${RESET}"
            echo -e "${WHITE}Your changes are saved on THIS device${RESET}"
            echo -e "${WHITE}but could NOT be synced to GitHub.${RESET}"
            echo ""
            echo -e "${WHITE}DO NOT open the app on another device${RESET}"
            echo -e "${WHITE}until this is resolved.${RESET}"
            echo ""
            echo -e "${WHITE}To fix manually, run:${RESET}"
            echo -e "${YELLOW}  git push origin master:main${RESET}"
            echo ""
            echo -e "${WHITE}Press any key to close.${RESET}"
            echo -e "${RED}========================================${RESET}"
            read -n 1 -s
        fi
    else
        echo -e "${GREEN}✅ No changes to sync${RESET}"
    fi

    echo ""
    echo -e "${WHITE}Goodbye! 👋${RESET}"
    sleep 2
    exit 0
}

trap on_close EXIT INT TERM

# ========================================
#  STARTUP
# ========================================
clear
echo -e "${WHITE}========================================${RESET}"
echo -e "${WHITE} 🎬 ShortsManager - Starting Up...${RESET}"
echo -e "${WHITE}========================================${RESET}"
echo ""

echo -e "${BLUE}⏳ Syncing with GitHub...${RESET}"
if git pull origin master --no-rebase >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Synced successfully - you have the latest version${RESET}"
else
    echo ""
    echo -e "${RED}========================================${RESET}"
    echo -e "${YELLOW}⚠  WARNING: SYNC FAILED${RESET}"
    echo -e "${RED}========================================${RESET}"
    echo -e "${WHITE}Could not sync with GitHub.${RESET}"
    echo -e "${WHITE}This may be because:${RESET}"
    echo -e "${WHITE} - You have no internet connection${RESET}"
    echo -e "${WHITE} - GitHub is unreachable${RESET}"
    echo ""
    echo -e "${WHITE}Your local data is safe, but if you${RESET}"
    echo -e "${WHITE}made changes on another device they${RESET}"
    echo -e "${WHITE}won't be here yet.${RESET}"
    echo ""
    echo -e "${WHITE}DO NOT use this on another device${RESET}"
    echo -e "${WHITE}until you see a successful sync.${RESET}"
    echo ""
    echo -e "${WHITE}Press any key to open anyway, or${RESET}"
    echo -e "${WHITE}close this window to cancel.${RESET}"
    echo -e "${RED}========================================${RESET}"
    read -n 1 -s
fi

echo ""
echo -e "${BLUE}⏳ Checking for package updates...${RESET}"
pip3 install -r requirements.txt -q
echo -e "${GREEN}✅ Ready! Opening ShortsManager...${RESET}"
echo ""

# Run the app (browser opens automatically)
python3 app.py
