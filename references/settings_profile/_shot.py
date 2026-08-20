from pathlib import Path
import subprocess

out = Path(__file__).resolve().parent
for i in range(1, 7):
    html = out / f"v0{i}.html"
    png = out / f"v0{i}.png"
    uri = f"http://127.0.0.1:8765/references/settings_profile/v0{i}.html"
    cmd = [
        "npx",
        "playwright",
        "screenshot",
        "--full-page",
        "--channel",
        "chrome",
        "--viewport-size",
        "1920,1080",
        "--wait-for-timeout",
        "1500",
        uri,
        str(png),
    ]
    print("shot", html.name)
    r = subprocess.run(cmd, cwd=str(out), shell=True)
    if r.returncode != 0:
        raise SystemExit(r.returncode)
    print(" ", png.name, png.stat().st_size)
