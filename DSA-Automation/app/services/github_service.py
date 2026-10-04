import base64
import os

import httpx
from dotenv import load_dotenv

load_dotenv()


class GitHubService:
    """
    Handles GitHub API operations.
    """

    BASE_URL = "https://api.github.com"

    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        self.owner = os.getenv("GITHUB_OWNER")

        if not self.token:
            raise ValueError(
                "GITHUB_TOKEN is missing in .env"
            )

        if not self.owner:
            raise ValueError(
                "GITHUB_OWNER is missing in .env"
            )

        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    # =========================================================
    # READ: Repository/File Contents
    # =========================================================

    async def get_contents(
        self,
        repo: str,
        path: str = "",
        ref: str | None = None,
    ):
        """
        Get the contents of a file or directory
        from a GitHub repository.
        """

        url = (
            f"{self.BASE_URL}/repos/"
            f"{self.owner}/{repo}/contents/{path}"
        )

        params = {}

        if ref:
            params["ref"] = ref

        async with httpx.AsyncClient() as client:

            response = await client.get(
                url,
                headers=self.headers,
                params=params,
            )

        response.raise_for_status()

        return response.json()

    async def get_file_text(
        self,
        repo: str,
        path: str,
        ref: str | None = None,
    ) -> str:
        """
        Get the text content of a file from GitHub.
        """

        data = await self.get_contents(
            repo=repo,
            path=path,
            ref=ref,
        )

        if isinstance(data, list):

            raise ValueError(
                f"Expected a file, but got a directory: {path}"
            )

        content = data.get("content")

        if not content:

            raise ValueError(
                f"No content found for file: {path}"
            )

        return base64.b64decode(
            content
        ).decode("utf-8")

    # =========================================================
    # READ: Commit
    # =========================================================

    async def get_commit(
        self,
        repo: str,
        commit_sha: str,
    ):
        """
        Get information about a GitHub commit.
        """

        url = (
            f"{self.BASE_URL}/repos/"
            f"{self.owner}/{repo}/commits/{commit_sha}"
        )

        async with httpx.AsyncClient() as client:

            response = await client.get(
                url,
                headers=self.headers,
            )

        response.raise_for_status()

        return response.json()

    # =========================================================
    # READ: Compare Commits
    # =========================================================

    async def compare_commits(
        self,
        repo: str,
        before_sha: str,
        after_sha: str,
    ):
        """
        Compare two commits.
        """

        url = (
            f"{self.BASE_URL}/repos/"
            f"{self.owner}/{repo}/compare/"
            f"{before_sha}...{after_sha}"
        )

        async with httpx.AsyncClient() as client:

            response = await client.get(
                url,
                headers=self.headers,
            )

        response.raise_for_status()

        return response.json()

    # =========================================================
    # READ: Repository Tree
    # =========================================================

    async def get_repository_tree(
        self,
        repo: str,
        branch: str = "main",
    ):
        """
        Get the complete file/folder tree of a repository.

        We use this to understand the folder structure
        that the user has already created in the DSA repo.
        """

        url = (
            f"{self.BASE_URL}/repos/"
            f"{self.owner}/{repo}/git/trees/{branch}"
        )

        params = {
            "recursive": "1"
        }

        async with httpx.AsyncClient() as client:

            response = await client.get(
                url,
                headers=self.headers,
                params=params,
            )

        response.raise_for_status()

        return response.json()

    # =========================================================
    # WRITE: Get Branch Reference
    # =========================================================

    async def get_branch_reference(
        self,
        repo: str,
        branch: str = "main",
    ) -> dict:
        """
        Get the current commit SHA and tree SHA
        for a branch.
        """

        url = (
            f"{self.BASE_URL}/repos/"
            f"{self.owner}/{repo}/git/ref/heads/{branch}"
        )

        async with httpx.AsyncClient() as client:

            response = await client.get(
                url,
                headers=self.headers,
            )

        response.raise_for_status()

        data = response.json()

        object_data = data.get(
            "object",
            {},
        )

        commit_sha = object_data.get(
            "sha"
        )

        if not commit_sha:
            raise ValueError(
                f"Could not determine current commit SHA "
                f"for branch: {branch}"
            )

        commit_data = await self.get_commit(
            repo=repo,
            commit_sha=commit_sha,
        )

        tree_data = commit_data.get(
            "commit",
            {},
        ).get(
            "tree",
            {},
        )

        tree_sha = tree_data.get(
            "sha"
        )

        if not tree_sha:

            raise ValueError(
                f"Could not determine current tree SHA "
                f"for branch: {branch}"
            )

        return {
            "branch": branch,
            "commit_sha": commit_sha,
            "tree_sha": tree_sha,
        }

    # =========================================================
    # WRITE: Check Existing File
    # =========================================================

    async def file_exists(
        self,
        repo: str,
        path: str,
        branch: str = "main",
    ) -> bool:
        """
        Check whether a file already exists.

        Existing files must be preserved.
        """

        try:

            await self.get_contents(
                repo=repo,
                path=path,
                ref=branch,
            )

            return True

        except httpx.HTTPStatusError as error:

            if error.response.status_code == 404:
                return False

            raise

    # =========================================================
    # WRITE: Create Blob
    # =========================================================

    async def create_blob(
        self,
        repo: str,
        content: str,
    ) -> str:
        """
        Create a Git blob containing file content.

        Returns the blob SHA.
        """

        url = (
            f"{self.BASE_URL}/repos/"
            f"{self.owner}/{repo}/git/blobs"
        )

        payload = {
            "content": content,
            "encoding": "utf-8",
        }

        async with httpx.AsyncClient() as client:

            response = await client.post(
                url,
                headers=self.headers,
                json=payload,
            )

        response.raise_for_status()

        data = response.json()

        blob_sha = data.get(
            "sha"
        )

        if not blob_sha:

            raise ValueError(
                "GitHub did not return a blob SHA."
            )

        return blob_sha

    # =========================================================
    # WRITE: Create Tree
    # =========================================================

    async def create_tree(
        self,
        repo: str,
        base_tree_sha: str,
        files: dict[str, str],
    ) -> str:
        """
        Create a Git tree containing the supplied files.

        files format:

            {
                "Binary Search/33_Search in Rotated Sorted Array/"
                "Search_in_Rotated_Sorted_Array.java":
                    "...content...",
            }

        Returns the new tree SHA.
        """

        tree_entries = []

        for path, content in files.items():

            blob_sha = await self.create_blob(
                repo=repo,
                content=content,
            )

            tree_entries.append(
                {
                    "path": path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_sha,
                }
            )

        if not tree_entries:

            raise ValueError(
                "No files were supplied to create_tree."
            )

        url = (
            f"{self.BASE_URL}/repos/"
            f"{self.owner}/{repo}/git/trees"
        )

        payload = {
            "base_tree": base_tree_sha,
            "tree": tree_entries,
        }

        async with httpx.AsyncClient() as client:

            response = await client.post(
                url,
                headers=self.headers,
                json=payload,
            )

        response.raise_for_status()

        data = response.json()

        tree_sha = data.get(
            "sha"
        )

        if not tree_sha:

            raise ValueError(
                "GitHub did not return a tree SHA."
            )

        return tree_sha

    # =========================================================
    # WRITE: Create Commit
    # =========================================================

    async def create_commit(
        self,
        repo: str,
        message: str,
        tree_sha: str,
        parent_sha: str,
    ) -> str:
        """
        Create a Git commit.

        Returns the new commit SHA.
        """

        url = (
            f"{self.BASE_URL}/repos/"
            f"{self.owner}/{repo}/git/commits"
        )

        payload = {
            "message": message,
            "tree": tree_sha,
            "parents": [
                parent_sha
            ],
        }

        async with httpx.AsyncClient() as client:

            response = await client.post(
                url,
                headers=self.headers,
                json=payload,
            )

        response.raise_for_status()

        data = response.json()

        commit_sha = data.get(
            "sha"
        )

        if not commit_sha:

            raise ValueError(
                "GitHub did not return a commit SHA."
            )

        return commit_sha

    # =========================================================
    # WRITE: Update Branch
    # =========================================================

    async def update_branch_reference(
        self,
        repo: str,
        branch: str,
        commit_sha: str,
    ):
        """
        Move the branch reference to the new commit.
        """

        url = (
            f"{self.BASE_URL}/repos/"
            f"{self.owner}/{repo}/git/refs/heads/{branch}"
        )

        payload = {
            "sha": commit_sha,
            "force": False,
        }

        async with httpx.AsyncClient() as client:

            response = await client.patch(
                url,
                headers=self.headers,
                json=payload,
            )

        response.raise_for_status()

        return response.json()

    # =========================================================
    # WRITE: Add Files + Commit
    # =========================================================

    async def write_files_to_repository(
        self,
        repo: str,
        files: dict[str, str],
        commit_message: str,
        branch: str = "main",
    ) -> dict:
        """
        Add new files to a GitHub repository and create
        one commit containing all newly added files.

        IMPORTANT:
        - Existing files are NOT overwritten.
        - Existing files are skipped.
        - New folders are created automatically through
          the file paths.
        - All new files are committed together.
        """

        if not files:

            raise ValueError(
                "No files supplied for GitHub write."
            )

        # -----------------------------------------------------
        # 1. Check which files already exist.
        # -----------------------------------------------------

        new_files = {}
        skipped_files = []

        for path, content in files.items():

            exists = await self.file_exists(
                repo=repo,
                path=path,
                branch=branch,
            )

            if exists:

                skipped_files.append(path)

            else:

                new_files[path] = content

        # -----------------------------------------------------
        # 2. Nothing new to write.
        # -----------------------------------------------------

        if not new_files:

            return {
                "written": False,
                "message": (
                    "All supplied files already exist. "
                    "Nothing was written."
                ),
                "repository": repo,
                "branch": branch,
                "created_files": [],
                "skipped_files": skipped_files,
                "commit_sha": None,
            }

        # -----------------------------------------------------
        # 3. Get current branch state.
        # -----------------------------------------------------

        branch_reference = (
            await self.get_branch_reference(
                repo=repo,
                branch=branch,
            )
        )

        parent_sha = branch_reference[
            "commit_sha"
        ]

        base_tree_sha = branch_reference[
            "tree_sha"
        ]

        # -----------------------------------------------------
        # 4. Create new Git tree.
        # -----------------------------------------------------

        new_tree_sha = await self.create_tree(
            repo=repo,
            base_tree_sha=base_tree_sha,
            files=new_files,
        )

        # -----------------------------------------------------
        # 5. Create commit.
        # -----------------------------------------------------

        commit_sha = await self.create_commit(
            repo=repo,
            message=commit_message,
            tree_sha=new_tree_sha,
            parent_sha=parent_sha,
        )

        # -----------------------------------------------------
        # 6. Update branch.
        # -----------------------------------------------------

        await self.update_branch_reference(
            repo=repo,
            branch=branch,
            commit_sha=commit_sha,
        )

        return {
            "written": True,
            "message": (
                "Files written to GitHub successfully."
            ),
            "repository": repo,
            "branch": branch,
            "created_files": list(
                new_files.keys()
            ),
            "skipped_files": skipped_files,
            "commit_sha": commit_sha,
        }