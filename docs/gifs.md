# 30s Demo GIF Workflow

Target output file:
- `docs/assets/gifs/quantvision-demo.gif`

Storyboard (30s):
1. Login (2s)
2. Load AAPL (3s)
3. Run anomaly detection (5s)
4. Show results (10s)
5. Export report (5s)

Recommended tools:
- OBS (capture screen)
- ffmpeg (trim and optimize)
- gifcap (optional quick crop/export)

## Recording Steps
1. Launch app and prepare demo data:
	- `task demo:bootstrap`
	- `task run`
2. Start OBS recording at 1280x720, 30 FPS.
3. Execute the storyboard in one smooth sequence.
4. Save recording as `docs/assets/gifs/raw-demo.mp4`.

## Convert MP4 to GIF with ffmpeg
```bash
ffmpeg -i docs/assets/gifs/raw-demo.mp4 -vf "fps=10,scale=960:-1:flags=lanczos" -t 30 docs/assets/gifs/quantvision-demo.gif
```

Optional palette optimization:
```bash
ffmpeg -i docs/assets/gifs/raw-demo.mp4 -vf "fps=10,scale=960:-1:flags=lanczos,palettegen" docs/assets/gifs/palette.png
ffmpeg -i docs/assets/gifs/raw-demo.mp4 -i docs/assets/gifs/palette.png -lavfi "fps=10,scale=960:-1:flags=lanczos[x];[x][1:v]paletteuse" -t 30 docs/assets/gifs/quantvision-demo.gif
```

## Notes
- Keep the cursor movement intentional and slow during metric highlights.
- If file size is too large, lower FPS to 8 or width to 800.
