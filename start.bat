@echo off
setlocal enabledelayedexpansion

:: ========================================
::  STARTUP
:: ========================================
cls
echo ========================================
echo  🎬 ShortsManager - Starting Up...
echo ========================================
echo.

echo ⏳ Syncing with GitHub...
git pull origin master --no-rebase >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Synced successfully - you have the latest version
) else (
    echo.
    echo ========================================
    echo ⚠  WARNING: SYNC FAILED
    echo ========================================
    echo Could not sync with GitHub.
    echo This may be because:
    echo  - You have no internet connection
    echo  - GitHub is unreachable
    echo.
    echo Your local data is safe, but if you
    echo made changes on another device they
    echo won't be here yet.
    echo.
    echo DO NOT use this on another device
    echo until you see a successful sync.
    echo.
    echo Press any key to open anyway, or
    echo close this window to cancel.
    echo ========================================
    pause >nul
)

echo.
echo ⏳ Checking for package updates...
pip install -r requirements.txt -q
echo ✅ Ready! Opening ShortsManager...
echo.

:: Run the app (browser opens automatically)
python app.py

:: ========================================
::  ON CLOSE - runs after Ctrl+C or app stops
:: ========================================
cls
echo ========================================
echo  💾 ShortsManager - Saving ^& Syncing...
echo ========================================
echo.

:: Check if there are any changes
git diff --quiet 2>nul && git diff --cached --quiet 2>nul
if %errorlevel% neq 0 (
    echo 📦 Changes detected - saving to GitHub...
    git add .
    git commit -m "auto-sync %date% %time%"
    git push origin master:main >nul 2>&1
    if %errorlevel% equ 0 (
        echo ✅ Changes saved to GitHub successfully
    ) else (
        echo.
        echo ========================================
        echo ⚠  WARNING: COULD NOT SAVE TO GITHUB
        echo ========================================
        echo Your changes are saved on THIS device
        echo but could NOT be synced to GitHub.
        echo.
        echo DO NOT open the app on another device
        echo until this is resolved.
        echo.
        echo To fix manually, run:
        echo   git push origin master:main
        echo.
        echo Press any key to close.
        echo ========================================
        pause >nul
    )
) else (
    echo ✅ No changes to sync
)

echo.
echo Goodbye! 👋
timeout /t 2 >nul
endlocal
