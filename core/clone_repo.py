
from __future__ import annotations

import os
import shutil

from git import GitCommandError, Repo


def clone_repository(
    repo_url: str,
    clone_dir: str = "repositories",
    force_reclone: bool = False,
) -> dict:
    """
    Clone a GitHub repository.

    Args:
        repo_url      : Full HTTPS URL  (e.g. https://github.com/user/repo)
        clone_dir     : Parent directory that will hold the clone.
        force_reclone : Delete an existing clone and re-clone from scratch.

    Returns:
        {"success": bool, "path": str | None, "message": str}
    """
    try:
        os.makedirs(clone_dir, exist_ok=True)

        repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        local_path = os.path.join(clone_dir, repo_name)

        if os.path.exists(local_path):
            if force_reclone:
                shutil.rmtree(local_path)
            else:
                return {
                    "success": True,
                    "path": local_path,
                    "message": "Repository already exists locally (cached).",
                }

        Repo.clone_from(repo_url, local_path)
        return {
            "success": True,
            "path": local_path,
            "message": "Repository cloned successfully.",
        }

    except GitCommandError as e:
        return {"success": False, "path": None, "message": f"Git error: {e}"}

    except Exception as e:
        return {"success": False, "path": None, "message": f"Unexpected error: {e}"}
