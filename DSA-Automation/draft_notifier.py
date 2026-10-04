
import time
import webbrowser
import subprocess
from pathlib import Path

# Your existing review page URL goes here.
REVIEW_URL = "http://127.0.0.1:8000/review"

# Your existing LeetCode repository
REPO_URL = "https://github.com/udayasri-2076/Leetcode.git"

CHECK_SECONDS = 10

def get_latest_commit():
    try:
        result = subprocess.run(
            ["git", "ls-remote", REPO_URL, "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
            check=True
        )
        return result.stdout.split()[0]
    except Exception as exc:
        print("GitHub check failed:", exc)
        return None

print("DSA draft notifier started.")

last_commit = get_latest_commit()

if last_commit is None:
    print("Could not connect to GitHub. Check Git installation/network.")

while True:
    time.sleep(CHECK_SECONDS)

    current_commit = get_latest_commit()

    if current_commit and current_commit != last_commit:
        last_commit = current_commit
        print("New repository commit detected!")
        print("Opening your existing review page in Edge...")

        webbrowser.open(REVIEW_URL, new=2)
