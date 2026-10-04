"""Opens the review page in your browser when a new draft is ready.

Runs on YOUR laptop. Settings come from watcher.env (same folder):
    APP_URL=https://your-app.onrender.com
    REVIEW_USERNAME=admin
    REVIEW_PASSWORD=your-review-password
Uses only the Python standard library: nothing to install.
"""
import base64
import json
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
POLL_SECONDS = 10
LOG_FILE = HERE / "watcher.log"


def log(message: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {message}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
        if len(lines) > 300:
            LOG_FILE.write_text("\n".join(lines[-200:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def load_config() -> dict:
    path = HERE / "watcher.env"
    if not path.exists():
        raise SystemExit("watcher.env not found. See the instructions.")
    config = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if raw and not raw.startswith("#") and "=" in raw:
            key, value = raw.split("=", 1)
            config[key.strip()] = value.strip().strip('"').strip("'")
    for key in ("APP_URL", "REVIEW_USERNAME", "REVIEW_PASSWORD"):
        if not config.get(key):
            raise SystemExit(f"{key} is missing in watcher.env")
    config["APP_URL"] = config["APP_URL"].rstrip("/")
    return config


def fetch_latest_id(config: dict) -> int | None:
    token = base64.b64encode(
        f"{config['REVIEW_USERNAME']}:{config['REVIEW_PASSWORD']}".encode()
    ).decode()
    request = urllib.request.Request(
        config["APP_URL"] + "/api/latest-draft",
        headers={"Authorization": f"Basic {token}"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response).get("id")


def main() -> None:
    config = load_config()
    last_id = None
    log(f"Watcher started. Watching {config['APP_URL']}")

    while True:
        try:
            latest = fetch_latest_id(config)
            if last_id is None:
                # Remember existing drafts so old ones don't pop open at startup.
                last_id = latest or 0
                log(f"Ready. Newest existing draft: {latest}")
            elif latest and latest > last_id:
                last_id = latest
                url = f"{config['APP_URL']}/review/{latest}"
                log(f"New draft {latest}: opening {url}")
                webbrowser.open(url, new=2)
        except urllib.error.HTTPError as error:
            if error.code == 401:
                # Stop: repeated wrong passwords would lock you out for 15 minutes.
                log("Wrong username/password in watcher.env. Stopping.")
                sys.exit(1)
            log(f"Server returned {error.code}. Will retry.")
        except Exception as error:
            log(f"Could not reach the app ({error}). Will retry.")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()