try:
    import fcntl
except ImportError:  # non-POSIX (Windows dev/CI) — lock degrades to no-op
    fcntl = None
import os
import subprocess
import sys
import time

from src.config import PKA_REPO_PATH

# ---------------------------------------------------------------------------
# Cross-writer serialization lock (tsk-2026-07-18-001).
#
# Three independent automations write to the SAME /home/ubuntu/pka working
# tree and .git on this VM: this Trello sync (every 15m), the openclaw
# container's `git pull --rebase` cron (every 5m), and pax-vm's research job
# (every 2h). They previously raced on the shared index / FETCH_HEAD whenever
# two ticks coincided (:00/:15/:30/:45, and :00 for all three every 2h),
# producing `fatal: Cannot rebase onto multiple branches` on ~33% of ticks.
#
# All three writers now take this same exclusive flock around their git
# critical section, so they serialize instead of racing. The lock file lives
# inside .git, which git never tracks. If the .git dir is absent (e.g. unit
# tests pointing PKA_REPO_PATH at a fake path), the lock degrades to a no-op
# rather than crashing the writer — production always has a real .git.
# ---------------------------------------------------------------------------
_PKA_WRITER_LOCK = os.path.join(PKA_REPO_PATH, ".git", "pka-writer.lock")
_LOCK_TIMEOUT_S = 120


class _PkaWriterLock:
    """Exclusive, timeout-bounded flock shared by all PKA writers on this VM."""

    def __init__(self, path=_PKA_WRITER_LOCK, timeout=_LOCK_TIMEOUT_S):
        self._path = path
        self._timeout = timeout
        self._fd = None

    def __enter__(self):
        if fcntl is None:
            # non-POSIX (Windows dev/CI): no flock available. The writer race
            # only exists on the Linux VM, so skip locking cleanly here.
            self._fd = None
            return self
        try:
            self._fd = os.open(self._path, os.O_CREAT | os.O_RDWR, 0o644)
        except OSError as exc:
            # Repo/.git dir not present (unit tests with a fake path). Degrade
            # to no-op rather than crash; real deployments always have .git.
            sys.stderr.write(
                f"pka writer lock unavailable ({exc}); proceeding without lock\n"
            )
            self._fd = None
            return self

        deadline = time.monotonic() + self._timeout
        while True:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    os.close(self._fd)
                    self._fd = None
                    raise TimeoutError(
                        f"pka writer lock not acquired within {self._timeout}s"
                    )
                time.sleep(0.5)

    def __exit__(self, *exc):
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None
        return False


def _run(args):
    return subprocess.run(
        ["git", "-C", PKA_REPO_PATH] + args,
        capture_output=True, text=True,
    )


def _pull_rebase():
    """Unlocked pull --rebase. Caller must already hold the writer lock."""
    result = _run(["pull", "--rebase"])
    if result.returncode != 0:
        return {
            "success": False,
            "message": f"git pull --rebase failed: {(result.stderr or result.stdout).strip()}",
        }
    return {"success": True, "message": (result.stdout or "Already up to date.").strip()}


def pull_rebase():
    """
    Run `git pull --rebase` against PKA_REPO_PATH, under the shared writer lock.

    The PKA repo is written to by more than one automation on this VM
    (this sync job, pax-vm's research job, the openclaw container cron, and
    manual pushes from other machines). Any of them can advance origin/main
    between this job's `fetch_cards()` and its own `git push`. Rebasing onto
    the latest origin/main before we touch anything — and again as a one-shot
    retry right before push — is what keeps our push a fast-forward. The
    writer lock ensures no other VM automation is mid-rebase on the shared
    index while we do it.

    Returns {success: bool, message: str}. Failure here is non-fatal to
    the caller: it's logged and the run continues, since the working
    tree may still be clean enough to write/commit/push successfully.
    """
    try:
        with _PkaWriterLock():
            return _pull_rebase()
    except TimeoutError as exc:
        return {"success": False, "message": str(exc)}


def _push_cards_locked(written_files, card_names):
    """Body of push_cards; caller holds the writer lock."""
    result = _run(["add"] + written_files)
    if result.returncode != 0:
        return {
            "success": False,
            "committed_files": [],
            "message": f"git add failed: {result.stderr.strip()}",
        }

    names_summary = ", ".join(card_names[:5])
    if len(card_names) > 5:
        names_summary += f" (+{len(card_names) - 5} more)"
    commit_msg = f"Sync from Trello: {names_summary}"

    result = _run(["commit", "-m", commit_msg])
    if result.returncode != 0:
        combined = (result.stdout + result.stderr).lower()
        if "nothing to commit" in combined or "nothing added to commit" in combined:
            return {"success": True, "committed_files": [], "message": "Nothing to commit"}
        return {
            "success": False,
            "committed_files": [],
            "message": f"git commit failed: {(result.stderr or result.stdout).strip()}",
        }

    result = _run(["push"])
    if result.returncode != 0:
        # Most push failures on this shared repo are a non-fast-forward
        # rejection caused by another writer landing a commit between our
        # fetch and our push (see tsk-2026-07-17-001). One rebase-and-retry
        # clears that class of failure without giving up the archive step.
        # We already hold the writer lock here, so use the unlocked rebase.
        push_err = result.stderr.strip()
        rebase_result = _pull_rebase()
        if rebase_result["success"]:
            result = _run(["push"])
            if result.returncode == 0:
                return {"success": True, "committed_files": written_files, "message": commit_msg}
            push_err = result.stderr.strip()
        return {
            "success": False,
            "committed_files": written_files,
            "message": f"git push failed: {push_err}",
        }

    return {"success": True, "committed_files": written_files, "message": commit_msg}


def push_cards(written_files, card_names):
    """
    Stage, commit, and push written_files to the PKA git repo, under the
    shared writer lock so the whole add/commit/push/retry sequence is atomic
    with respect to the other VM automations writing the same repo.

    Args:
        written_files: list of absolute file paths that were written
        card_names:    list of card names for the commit message

    Returns:
        dict: {success: bool, committed_files: list, message: str}
    """
    if not written_files:
        return {"success": True, "committed_files": [], "message": "Nothing to commit"}

    try:
        with _PkaWriterLock():
            return _push_cards_locked(written_files, card_names)
    except TimeoutError as exc:
        return {
            "success": False,
            "committed_files": [],
            "message": str(exc),
        }
