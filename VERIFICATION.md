# Build verification

Verified on 8 September 2026 in a Windows development environment.

## Passed

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
- The automated browser returned `ERR_BLOCKED_BY_CLIENT` for localhost. No visual browser interaction, audible playback, or Windows Explorer launch was personally verified. DOM Play/Pause tests stubbed media playback; they verify state changes, not sound.
- There is no paid API dependency. Edge TTS worked during these tests but still requires internet access and service availability.

Run `python -m backend.test_workflow` after installing the documented test dependency to repeat the integration checks. Generated test data is isolated under `test-results/` and excluded from Git.
