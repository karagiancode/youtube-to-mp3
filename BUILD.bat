@echo off
cd /d "%~dp0"

echo === STEP 1: Install dependencies ===
pip install yt-dlp pyinstaller --quiet
echo Done.
echo.

echo === STEP 2: Build EXE ===
python -m PyInstaller --onefile --noconsole --name YT_to_MP3 yt_downloader.py --clean
echo.

echo === STEP 3: Copy to OUTPUT ===
if exist "OUTPUT" rmdir /s /q "OUTPUT"
mkdir "OUTPUT"

if exist "dist\YT_to_MP3.exe" (
    copy "dist\YT_to_MP3.exe" "OUTPUT\"
    echo Copied YT_to_MP3.exe
) else (
    echo ERROR: exe not found in dist!
    dir /s /b dist
    pause
    exit /b 1
)

if exist "ffmpeg.exe"  copy "ffmpeg.exe"  "OUTPUT\"
if exist "ffprobe.exe" copy "ffprobe.exe" "OUTPUT\"

echo.
echo === OUTPUT contents ===
dir /b "OUTPUT"
echo.
echo Location: %CD%\OUTPUT
echo.
explorer "%CD%\OUTPUT"
pause
