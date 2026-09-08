# Build verification

Verified on 8 September 2026 in a Windows development environment.

## Screenshot annotations and zoom/pan update

- Tested all five drawing tools in the real browser: arrows, highlights, numbered steps, blur and solid covers, including resizing and save/reopen persistence.
- Tested camera start/end framing, zoom, dragging to pan, playback and pause. Pausing preserves the current camera frame until editing resumes.
- Rendered and fully decoded a real MP4. Pixel checks verified annotations, blur, solid covers, camera movement and captions remaining fixed while the screenshot moves.
- Verified invalid coordinates/zoom are rejected and older scenes default to no annotations or camera movement.
- Re-ran the offline narration and full workflow suites after the rendering changes; real speech, captioned 1080p H.264/AAC exports and full decoding passed.
- Repeat the isolated export checks with `python -m backend.test_visuals`.

## Offline narration update

- Downloaded both pinned Piper voice models and verified their SHA-256 checksums.
- Generated real speech with Northern English male and Jenny (Dioco), including punctuation/Unicode text.
- Blocked external Python socket connections, HTTP session creation, and Edge TTS during the dedicated test; local loopback was allowed for Windows asyncio internals.
- Verified audio caching, invalidation on voice/speed changes, +100% speed, narration + 1 second automatic duration, and manual duration preservation.
- Exported and fully decoded a real MP4 whose narration was generated in the background export job using Piper.
- Confirmed missing model/engine/voice errors remain friendly and never invoke an online fallback.
- React DOM testing against the running HTTP API also passed: switching an existing online project to offline voices, autosaving, generating real Piper narration, and reaching VIDEO READY. Browser audio playback was stubbed; this is not a visual browser test.
- Offline model setup is separate from runtime. `setup-offline.bat` provisions the normal `.venv`; the full double-click setup/launcher remains subject to the environment limitation below.

## Original MVP checks

- FastAPI server started successfully on loopback.
- Frontend HTML, JavaScript, CSS, health and project endpoints returned HTTP 200.
- React source compiled and bundled successfully with the installed esbuild executable.
- A React DOM smoke test (Happy DOM, real HTTP API) exercised dashboard loading, project creation, adding scenes, duplication, up/down ordering, deletion, autosave, Play/Pause state changes, dashboard navigation and reopening the saved project.
- Integration test created title and image scenes, uploaded a PNG, rejected an invalid image, saved/reordered/reopened, and rejected a stale revision.
- Real Microsoft Edge TTS generated British-English narration. Audio duration was measured and scene duration set to narration + 1 second.
- FFmpeg produced a real 1920×1080 H.264/AAC MP4 with title scene, screenshot scenes, caption, narration and silent padding. Full decode completed successfully.
- Project persisted across application startup; the demo was not duplicated.
- Mutations from an unrelated web origin were rejected.

## Environment limitations

- FFmpeg was not installed on the system PATH. Tests used a downloaded FFmpeg 7.1 binary via `FFMPEG_PATH`. Install FFmpeg normally before using the launcher.
- This environment's bundled Node runtime returns `spawn EPERM` when Vite starts its build subprocesses. The source was compiled with esbuild directly for HTTP and React DOM testing. The standard `npm run build` and the complete double-click launcher still need verification in a normal Windows terminal.
- During the initial MVP checks the automated browser returned `ERR_BLOCKED_BY_CLIENT` for localhost. Browser access subsequently worked for the annotation/zoom update described above. Audible playback and Windows Explorer launch remain unverified. Initial DOM Play/Pause tests stubbed media playback.
- There is no paid API dependency. Edge TTS worked during these tests but still requires internet access and service availability.

Run `python -m backend.test_workflow` after installing the documented test dependency to repeat the integration checks. Generated test data is isolated under `test-results/` and excluded from Git.
