
import subprocess


def notify_draft_ready():
    """Show a Windows desktop notification when a draft is ready."""
    try:
        from winotify import Notification

        Notification(
            app_id="DSA Automation",
            title="New DSA Draft Ready",
            msg="Your solution is ready for review.",
            duration="short"
        ).show()
    except ImportError:
        # Fallback if winotify is not installed.
        try:
            import winsound
            winsound.MessageBeep()
        except Exception:
            pass
    except Exception as exc:
        print(f"Desktop notification failed: {exc}")
