# JD Training Studio

A local-first desktop-browser app for turning screenshots and written instructions into narrated training videos. React + Vite frontend, Python + FastAPI backend, local JSON storage, Edge TTS narration, and FFmpeg MP4 rendering. No paid AI API key is needed.

## Requirements

- Windows 10/11 is the primary target.
- Python 3.11 or newer, with the `py` launcher and pip.
- Node.js 22 LTS or newer, with npm.
- FFmpeg with H.264 (`libx264`) and AAC support.
- Internet for initial dependency installation and Edge TTS generation. Narration text is sent to Microsoft's Edge TTS service; images and project files stay local. Previously generated audio can be reused offline.

## Quick start on Windows

1. Download/clone this repository to a writable folder and extract it if downloaded as a ZIP.
2. Install Python from https://www.python.org/downloads/ and Node.js from https://nodejs.org/ if needed.
3. Install FFmpeg as described below.
4. Double-click **start.bat**. On first launch it creates `.venv`, installs dependencies, builds the frontend, and opens http://127.0.0.1:8000.
5. Keep the terminal window open. Press Ctrl+C to stop the server.

The application binds to loopback only. This is a single-user local app, not an authenticated network service. Do not expose it publicly.

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
4. Choose an English voice (British Sonia is the default) and a speed. Click **Generate Narration**, then **Preview Narration**.
5. Generated narration sets duration to the audio length plus one second. Editing the seconds field sets a manual override; enable **Auto duration** to restore automatic timing. A shorter manual duration trims audio in the export.
6. Click **Play** to preview from the selected scene through the end. Pause resumes from the same position. Previous/Next select a scene. Generate narration first to hear voiceover in this preview.
7. Changes autosave after a short pause. **Save Project** saves immediately. Wait for **Saved locally** before closing. Dashboard and Open Project list saved projects.

The three-scene **Scheduler Training Demo** is created on first startup. Its placeholder images and narration can be replaced. Opening title scenes are independently editable after creation.

## Generate a video

Every ordinary scene needs an image. Narration is optional; a scene without text plays silently. Click **GENERATE VIDEO**. The app saves edits, generates/reuses narration, renders scenes in order, and combines them into a 1920×1080 H.264/AAC MP4. Short fades through black separate scenes. Progress appears above the editor; editing is locked during generation.

At **VIDEO READY**, use **Play Video**, **Download MP4**, or **Open Video Location**. The latter opens Windows Explorer at that project's output folder; on other platforms it displays the folder path. Editing invalidates the current export link, but earlier exported files are retained.

## Files and backups

```text
backend/
  main.py              API, storage, demo and background jobs
  media.py             Narration, captions, title frames and FFmpeg
  requirements.txt
  test_workflow.py     Integration smoke test
frontend/
  src/main.jsx         Dashboard and editor
  src/style.css        Responsive layout
  vite.config.js
  package.json
  pnpm-lock.yaml       Recorded dependency versions (npm also supported)
launch.py              Opens the browser after backend readiness
start.bat              Windows setup/build/launch
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
- **Narration failed:** Edge TTS is a free online service and can be unavailable or blocked by a firewall. Check your connection and retry. No paid fallback is used.
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

The test uses isolated `test-results` storage, creates multiple scenes, uploads and rejects images, reorders, saves/reopens, checks stale revisions, attempts real Edge TTS, verifies auto duration, exports and decodes a real MP4, checks 1080p H.264/AAC, and checks persistence across application startup. If TTS is unavailable it reports that explicitly and tests the encoder separately.

See `VERIFICATION.md` for what was personally verified in the build environment and its restrictions.

## Scope

This MVP includes only screenshot scenes, captions, narration, local persistence, preview, and export. AI script generation, avatars, document import, branding templates, quizzes, SCORM and LMS integration are intentionally not implemented. A useful next improvement would be fully offline narration.
