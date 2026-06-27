import subprocess

from src.config import PKA_REPO_PATH


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

    repo = PKA_REPO_PATH

    result = subprocess.run(
        ["git", "-C", repo, "add"] + written_files,
        capture_output=True, text=True,
    )
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

    result = subprocess.run(
        ["git", "-C", repo, "commit", "-m", commit_msg],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        combined = (result.stdout + result.stderr).lower()
        if "nothing to commit" in combined or "nothing added to commit" in combined:
            return {"success": True, "committed_files": [], "message": "Nothing to commit"}
        return {
            "success": False,
            "committed_files": [],
            "message": f"git commit failed: {(result.stderr or result.stdout).strip()}",
        }

    result = subprocess.run(
        ["git", "-C", repo, "push"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return {
            "success": False,
            "committed_files": written_files,
            "message": f"git push failed: {result.stderr.strip()}",
        }

    return {"success": True, "committed_files": written_files, "message": commit_msg}
