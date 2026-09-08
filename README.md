# JD Training Studio

A local-first desktop-browser app for turning screenshots and written instructions into narrated training videos. React + Vite frontend, Python + FastAPI backend, local JSON storage, offline Piper narration (with optional online Edge TTS), and FFmpeg MP4 rendering. No paid AI API key is needed.

## Requirements

- Windows 10/11 is the primary target.
- Python 3.11 or newer, with the `py` launcher and pip.
- Node.js 22 LTS or newer, with npm.
- FFmpeg with H.264 (`libx264`) and AAC support.
- Internet is needed only for initial dependency/voice installation. Piper generates narration entirely on this computer. If you explicitly choose an online Edge TTS voice, its narration text is sent to Microsoft. Offline voices never fall back to an online service.

## Quick start on Windows

1. Download/clone this repository to a writable folder and extract it if downloaded as a ZIP.
2. Install Python from https://www.python.org/downloads/ and Node.js from https://nodejs.org/ if needed.
3. Install FFmpeg as described below.
4. Double-click **setup-offline.bat** once while online to install Piper and download both voices (about 127 MB, plus Python dependencies).
5. Double-click **start.bat**. On first launch it creates `.venv`, installs dependencies, builds the frontend, and opens http://127.0.0.1:8000.
6. Keep the terminal window open. Press Ctrl+C to stop the server.

The application binds to loopback only. This is a single-user local app, not an authenticated network service. Do not expose it publicly.

## Fully offline narration

After the one-time setup, disconnect from the internet and use **Generate Narration** or **GENERATE VIDEO** normally. The voice models and speech engine run on your CPU; no GPU, account or API key is needed. New projects/scenes default to offline speech.

Existing projects keep their previous voice selections. Open one and click **Use offline voices for this project** to switch every online scene to the offline default. This clears stale narration references; generate narration or export to create the new audio. The selector separates offline and online voices, and the editor shows when a project contains online scenes.

Manual offline setup (from the repository root, after creating `.venv`):

```powershell
.venv\Scripts\python.exe -m pip install -r backend\requirements-offline.txt
.venv\Scripts\python.exe -m backend.setup_offline
```

The downloader only runs when explicitly invoked. It uses a pinned model revision, verifies model/config checksums, and reuses complete downloads. It is safe to run again to repair a partial setup. To provision a machine without internet, install Python dependencies from a local wheel cache and copy the complete `models/piper` folder from a configured machine. `JD_VOICES_DIR` can point to another local model folder. The app does not download anything during speech generation.

See [VOICE_CREDITS.md](VOICE_CREDITS.md) for the Piper engine and voice model sources/attribution.

To verify real speech and export while Python network paths and Edge TTS are blocked:

```powershell
.venv\Scripts\python.exe -m pip install httpx
.venv\Scripts\python.exe -m backend.test_offline
```

This test requires actual Piper models and FFmpeg. It checks both voices, caching, speed, automatic/manual timing, missing voices, and an MP4 export with generated speech.

## Installing FFmpeg

In a Windows terminal:

```powershell
winget install Gyan.FFmpeg
```

Alternatively download a Windows build linked from https://ffmpeg.org/download.html, extract it, and add the folder containing `ffmpeg.exe` to your user `PATH`. Open a new terminal and run `ffmpeg -version` to confirm. Restart the application after installation.

You can also set an explicit path before launching:

```powershell
$env:FFMPEG_PATH = 'C:\Tools\ffmpeg\bin\ffmpeg.exe'
```

The app displays **FFmpeg: Ready** or **FFmpeg: Not Found**. You can edit and save projects without FFmpeg; narration duration measurement and video export require it. A separate ffprobe installation is not required.

## Manual installation and development

From the repository root:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd frontend
npm install
cd ..
```

Start the backend in one terminal:

```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Start the frontend in another terminal:

```powershell
cd frontend
npm run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` requests to the backend. API documentation is available at http://127.0.0.1:8000/docs.

For a single-server production build, run `npm run build` in `frontend`, then restart the backend. It serves the compiled frontend at port 8000. The Windows launcher performs this automatically.

## Create and edit a training

1. Click **Create Training** or **New Training**. Enter a title, optional subtitle, and choose whether to include an opening title scene.
2. Click **Add scene**, choose a screenshot, and enter a scene title, narration, and optional short caption.
3. Use the scene list to select, duplicate, delete, and move scenes up/down.
4. Choose an English voice (Northern English male is the offline default) and a speed. Offline choices include Northern English male and Jenny (Dioco), a female voice with an Irish accent. Click **Generate Narration**, then **Preview Narration**.
5. Generated narration sets duration to the audio length plus one second. Editing the seconds field sets a manual override; enable **Auto duration** to restore automatic timing. A shorter manual duration trims audio in the export.
6. Click **Play** to preview from the selected scene through the end. Pause resumes from the same position. Previous/Next select a scene. Generate narration first to hear voiceover in this preview.
7. Changes autosave after a short pause. **Save Project** saves immediately. Wait for **Saved locally** before closing. Dashboard and Open Project list saved projects.

The three-scene **Scheduler Training Demo** is created on first startup. Its placeholder images and narration can be replaced. Opening title scenes are independently editable after creation.

## Generate a video

Every ordinary scene needs an image. Narration is optional; a scene without text plays silently. Click **GENERATE VIDEO**. The app saves edits, generates/reuses narration with each scene's selected engine, renders scenes in order, and combines them into a 1920×1080 H.264/AAC MP4. Short fades through black separate scenes. Progress appears above the editor; editing is locked during generation.

At **VIDEO READY**, use **Play Video**, **Download MP4**, or **Open Video Location**. The latter opens Windows Explorer at that project's output folder; on other platforms it displays the folder path. Editing invalidates the current export link, but earlier exported files are retained.

## Files and backups

To also save completed MP4s in an easy-to-find folder, create `settings.local.json` in the repository root:

```json
{"video_output_dir": "C:\\Users\\YourName\\Desktop\\Training output"}
```

Alternatively set `JD_VIDEO_OUTPUT_DIR` to an absolute folder path. New exports receive a title, timestamp and unique suffix; existing files are not overwritten. **Open Video Location** opens this chosen folder for those exports. A project-local copy remains available for in-app playback and backups. This machine-specific setting is excluded from Git. Older exports keep their original locations.

```text
backend/
  main.py              API, storage, demo and background jobs
  media.py             Narration, captions, title frames and FFmpeg
  offline_tts.py       Local Piper inference and voice discovery
  setup_offline.py     One-time verified voice downloader
  requirements.txt
  requirements-offline.txt
  test_workflow.py     Integration smoke test
  test_offline.py      Real offline speech/export test
frontend/
  src/main.jsx         Dashboard and editor
  src/style.css        Responsive layout
  vite.config.js
  package.json
  pnpm-lock.yaml       Recorded dependency versions (npm also supported)
launch.py              Opens the browser after backend readiness
start.bat              Windows setup/build/launch
setup-offline.bat      One-time engine/voice installation
models/piper/          Downloaded voices; excluded from Git
VOICE_CREDITS.md       Engine and voice attribution
projects/              Created at first run; excluded from Git
  <project-id>/
    project.json
    images/
    audio/
    output/
logs/studio.log        Rotating technical error log; excluded from Git
```

Back up the entire `projects` folder, not just JSON files. Restore complete project folders under `projects` while the app is stopped, then reopen the dashboard. `JD_PROJECTS_DIR` can point to another local storage directory. Assets are retained when scenes are deleted so existing exports and duplicates remain safe; unused-media cleanup is not implemented.

## Troubleshooting

- **Python/Node not found:** install the requirements and open a new terminal. The launcher expects `py` and `npm.cmd` on PATH.
- **First launch cannot install packages:** check connectivity/proxy settings. Run the manual installation commands to see the failing dependency.
- **FFmpeg not found:** verify `ffmpeg -version` in a new terminal and restart the backend. Check `FFMPEG_PATH` if set.
- **Unsupported image:** use PNG, JPEG or WebP, at most 20 MB and 40 megapixels. Uploads are normalized to PNG, corrected for orientation, and limited to 3840×2160.
- **Missing narration:** enter text and generate narration to hear it. Empty narration is deliberately silent. Changing text, voice or speed invalidates the old audio.
- **Offline narration unavailable:** run `setup-offline.bat` once while online, then restart the app and click **Refresh voices**. It installs Piper and repairs missing/corrupt model/config files using checksums. No network is used during Piper synthesis.
- **Online narration failed:** Edge TTS may be unavailable or blocked. Select an offline voice or check your connection and retry. No automatic online fallback is used.
- **Video failed:** ensure FFmpeg supports libx264/AAC, check disk space and `logs/studio.log`. The job can be retried. Keep the backend running while exporting; jobs are not resumable after shutdown.
- **Save conflict:** another window modified the project. Reopen the project before continuing. Avoid editing one project in multiple windows.
- **Missing project/media files:** restore a backup or upload/regenerate the missing media. Corrupted project JSON files are skipped in the dashboard and logged.
- **Blank page/404 at port 8000:** run `npm run build` in `frontend`, then restart the backend; alternatively use the Vite dev server on port 5173.
- **Port already in use:** stop the previous server before starting another instance.

## Validation

Run the integration test from the repository root:

```powershell
.venv\Scripts\python.exe -m pip install httpx
.venv\Scripts\python.exe -m backend.test_workflow
```

The test uses isolated `test-results` storage, creates multiple scenes, uploads and rejects images, reorders, saves/reopens, checks stale revisions, tests real offline Piper speech by default (`--online` explicitly selects Edge TTS), verifies auto duration, exports and decodes a real MP4, checks 1080p H.264/AAC, and checks persistence across application startup. If the offline engine is not installed, the general smoke test reports it explicitly and tests the encoder separately. The dedicated offline test requires real voices and never substitutes a tone for speech.

See `VERIFICATION.md` for what was personally verified in the build environment and its restrictions.

## Scope

This MVP includes only screenshot scenes, captions, narration, local persistence, preview, and export. AI script generation, avatars, document import, branding templates, quizzes, SCORM and LMS integration are intentionally not implemented. Offline narration is included. A useful next improvement would be a packaged Windows installer.
