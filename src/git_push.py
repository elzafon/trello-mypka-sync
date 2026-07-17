import subprocess

from src.config import PKA_REPO_PATH


def _run(args):
    return subprocess.run(
        ["git", "-C", PKA_REPO_PATH] + args,
        capture_output=True, text=True,
    )


def pull_rebase():
    """
    Run `git pull --rebase` against PKA_REPO_PATH.

    The PKA repo is written to by more than one automation on this VM
    (this sync job, pax-vm's research job, and manual pushes from other
    machines). Any of them can advance origin/main between this job's
    `fetch_cards()` and its own `git push`. Rebasing onto the latest
    origin/main before we touch anything — and again as a one-shot retry
    right before push — is what keeps our push a fast-forward.

    Returns {success: bool, message: str}. Failure here is non-fatal to
    the caller: it's logged and the run continues, since the working
    tree may still be clean enough to write/commit/push successfully.
    """
    result = _run(["pull", "--rebase"])
    if result.returncode != 0:
        return {
            "success": False,
            "message": f"git pull --rebase failed: {(result.stderr or result.stdout).strip()}",
        }
    return {"success": True, "message": (result.stdout or "Already up to date.").strip()}


def push_cards(written_files, card_names):
    """
    Stage, commit, and push written_files to the PKA git repo.

    Args:
        written_files: list of absolute file paths that were written
        card_names:    list of card names for the commit message

    Returns:
        dict: {success: bool, committed_files: list, message: str}
    """
    if not written_files:
        return {"success": True, "committed_files": [], "message": "Nothing to commit"}

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
        push_err = result.stderr.strip()
        rebase_result = pull_rebase()
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
