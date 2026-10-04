import os
import re
from collections import defaultdict

from app.services.github_service import GitHubService


class StyleReferenceService:
    """
    Reads real Java and README files from the user's DSA repository
    and prepares the strongest examples as style references for Gemini.

    IMPORTANT:
    - Does NOT modify GitHub.
    - Does NOT create files.
    - Does NOT decide topic/pattern.
    - Uses Java + README references.
    - Python references are not required.
    - Prefers references that demonstrate Brute Force,
      Better, Optimal, and inline dry-run style.
    """

    MAX_CANDIDATES_TO_INSPECT = 50
    MAX_REFERENCE_PROBLEMS = 3

    MAX_JAVA_CHARS = 12000
    MAX_README_CHARS = 12000
    MAX_TOTAL_CHARS = 30000

    def __init__(self):
        self.github = GitHubService()

    # =========================================================
    # FIND COMPLETE PROBLEM FOLDERS
    # =========================================================

    @staticmethod
    def find_complete_problem_folders(
        tree: list[dict],
    ) -> list[dict]:
        """
        Find problem folders containing:
        - at least one Java file
        - README.md
        """

        java_files_by_folder = defaultdict(list)
        readme_files_by_folder = defaultdict(list)

        for item in tree:

            if item.get("type") != "blob":
                continue

            path = item.get("path", "")

            if not path:
                continue

            path = path.replace("\\", "/")

            parts = path.split("/")

            if len(parts) < 2:
                continue

            folder = "/".join(parts[:-1])
            filename = parts[-1]

            if filename.lower().endswith(".java"):
                java_files_by_folder[folder].append(path)

            elif filename.lower() == "readme.md":
                readme_files_by_folder[folder].append(path)

        folders = []

        common_folders = (
            set(java_files_by_folder)
            & set(readme_files_by_folder)
        )

        for folder in common_folders:

            java_files = sorted(
                java_files_by_folder[folder]
            )

            readme_files = sorted(
                readme_files_by_folder[folder]
            )

            if not java_files or not readme_files:
                continue

            folders.append(
                {
                    "folder": folder,
                    "java_file": java_files[0],
                    "readme_file": readme_files[0],
                }
            )

        return sorted(
            folders,
            key=lambda item: item["folder"].lower(),
        )

    # =========================================================
    # SCORE REFERENCE
    # =========================================================

    @staticmethod
    def score_reference(
        java_content: str,
        readme_content: str,
    ) -> dict:
        """
        Score a reference according to how useful it is for
        learning the user's actual DSA style.
        """

        java_lower = java_content.lower()
        readme_lower = readme_content.lower()

        score = 0

        # -----------------------------------------------------
        # Approach structure
        # -----------------------------------------------------

        has_brute = (
            "brute force" in java_lower
            or "brute force" in readme_lower
        )

        has_better = (
            "better" in java_lower
            or "better" in readme_lower
        )

        has_optimal = (
            "optimal" in java_lower
            or "optimal" in readme_lower
        )

        if has_brute:
            score += 30

        if has_better:
            score += 30

        if has_optimal:
            score += 30

        # -----------------------------------------------------
        # Three-approach reference gets extra priority
        # -----------------------------------------------------

        if has_brute and has_better and has_optimal:
            score += 60

        # -----------------------------------------------------
        # Inline dry-run indicators
        # -----------------------------------------------------

        dry_run_patterns = [
            r"//.*=.*",
            r"//.*true",
            r"//.*false",
            r"//.*->",
            r"//.*add",
            r"//.*move",
            r"//.*stop",
            r"//.*found",
        ]

        dry_run_count = 0

        for pattern in dry_run_patterns:

            matches = re.findall(
                pattern,
                java_lower,
            )

            dry_run_count += len(matches)

        # More inline comments = stronger learning reference.
        score += min(
            dry_run_count * 2,
            40,
        )

        # -----------------------------------------------------
        # README structure
        # -----------------------------------------------------

        if "problem statement" in readme_lower:
            score += 10

        if "approach 1" in readme_lower:
            score += 10

        if "approach 2" in readme_lower:
            score += 10

        if "comparison of approaches" in readme_lower:
            score += 10

        if "concepts used" in readme_lower:
            score += 5

        if "sample input" in readme_lower:
            score += 5

        if "sample output" in readme_lower:
            score += 5

        return {
            "score": score,
            "has_brute": has_brute,
            "has_better": has_better,
            "has_optimal": has_optimal,
            "dry_run_count": dry_run_count,
        }

    # =========================================================
    # TRIM CONTENT
    # =========================================================

    @staticmethod
    def trim_content(
        content: str,
        max_chars: int,
    ) -> str:
        """
        Prevent very large references from making the Gemini
        prompt unnecessarily large.
        """

        if len(content) <= max_chars:
            return content

        return (
            content[:max_chars]
            + "\n\n"
            + "[REFERENCE TRUNCATED]"
        )

    # =========================================================
    # BUILD STYLE REFERENCE
    # =========================================================

    async def get_style_reference(
        self,
        repo: str | None = None,
        branch: str = "main",
    ) -> str:
        """
        Find strong real Java + README references from the
        user's DSA repository.
        """

        dsa_repo = repo or os.getenv(
            "DSA_REPO"
        )

        if not dsa_repo:
            raise ValueError(
                "DSA_REPO is missing in .env"
            )

        # -----------------------------------------------------
        # 1. Get repository tree
        # -----------------------------------------------------

        tree_data = await self.github.get_repository_tree(
            repo=dsa_repo,
            branch=branch,
        )

        tree = tree_data.get(
            "tree",
            [],
        )

        # -----------------------------------------------------
        # 2. Find complete problem folders
        # -----------------------------------------------------

        complete_folders = (
            self.find_complete_problem_folders(
                tree
            )
        )

        if not complete_folders:
            return (
                "NO REAL STYLE REFERENCES FOUND.\n"
                "Use the explicit style instructions in the prompt."
            )

        # -----------------------------------------------------
        # 3. Inspect a reasonable number of candidates
        # -----------------------------------------------------

        candidates = complete_folders[
            : self.MAX_CANDIDATES_TO_INSPECT
        ]

        scored_references = []

        print()
        print(
            "📚 Inspecting DSA style reference candidates..."
        )

        for candidate in candidates:

            try:

                java_content = await self.github.get_file_text(
                    repo=dsa_repo,
                    path=candidate["java_file"],
                    ref=branch,
                )

                readme_content = await self.github.get_file_text(
                    repo=dsa_repo,
                    path=candidate["readme_file"],
                    ref=branch,
                )

            except Exception as error:

                print(
                    "⚠️ Could not inspect reference:"
                )

                print(
                    f"   {candidate['folder']}"
                )

                print(
                    f"   {error}"
                )

                continue

            score_data = self.score_reference(
                java_content=java_content,
                readme_content=readme_content,
            )

            scored_references.append(
                {
                    **candidate,
                    "java_content": java_content,
                    "readme_content": readme_content,
                    "score": score_data["score"],
                    "has_brute": score_data[
                        "has_brute"
                    ],
                    "has_better": score_data[
                        "has_better"
                    ],
                    "has_optimal": score_data[
                        "has_optimal"
                    ],
                    "dry_run_count": score_data[
                        "dry_run_count"
                    ],
                }
            )

        if not scored_references:

            return (
                "NO REAL STYLE REFERENCES COULD BE READ.\n"
                "Use the explicit style instructions in the prompt."
            )

        # -----------------------------------------------------
        # 4. Sort strongest references first
        # -----------------------------------------------------

        scored_references.sort(
            key=lambda item: (
                item["score"],
                item["dry_run_count"],
            ),
            reverse=True,
        )

        selected = scored_references[
            : self.MAX_REFERENCE_PROBLEMS
        ]

        print()
        print(
            "✅ Selected DSA style references:"
        )

        for index, reference in enumerate(
            selected,
            start=1,
        ):

            print(
                f"   {index}. {reference['folder']}"
            )

            print(
                f"      Score   : {reference['score']}"
            )

            print(
                f"      Brute   : "
                f"{'✅' if reference['has_brute'] else '❌'}"
            )

            print(
                f"      Better  : "
                f"{'✅' if reference['has_better'] else '❌'}"
            )

            print(
                f"      Optimal : "
                f"{'✅' if reference['has_optimal'] else '❌'}"
            )

            print(
                f"      Dry run : "
                f"{reference['dry_run_count']}"
            )

        # -----------------------------------------------------
        # 5. Build final prompt reference
        # -----------------------------------------------------

        header = """
=========================================================
USER'S ACTUAL DSA REPOSITORY STYLE REFERENCES
=========================================================

The following are REAL files already written by the user.

They are the SOURCE OF TRUTH for the user's personal
DSA learning style.

PRIORITY:

1. Brute Force structure
2. Better approach structure
3. Optimal approach structure
4. Inline dry-run comments
5. Variable/value tracking
6. Pointer/index tracking
7. README organization

IMPORTANT:

The generated solution should follow the same learning
structure as these references.

When a problem genuinely supports Brute Force,
Better, and Optimal approaches, include them in this order:

Brute Force
Better
Optimal

Each must contain REAL executable code.

Do not replace the user's style with generic professional
or LeetCode-editor code.

The Java references are the primary code-style examples.

There are no Python reference files in the repository.

Therefore Python must mirror the same:

- approach structure
- reasoning
- learning flow
- example style
- comment style
- inline dry-run density
- variable tracking
- pointer/index tracking

while using correct Python syntax.

The references determine STYLE ONLY.

The backend determines:

- Topic
- Pattern
- Destination
- Problem classification
- Missing files
=========================================================
"""

        sections = []

        total_chars = 0

        # -----------------------------------------------------
        # 6. Add selected references
        # -----------------------------------------------------

        for index, reference in enumerate(
            selected,
            start=1,
        ):

            java_content = self.trim_content(
                reference["java_content"],
                self.MAX_JAVA_CHARS,
            )

            readme_content = self.trim_content(
                reference["readme_content"],
                self.MAX_README_CHARS,
            )

            section = f"""
==================================================
REAL DSA STYLE REFERENCE {index}
==================================================

Problem Folder:
{reference["folder"]}

Reference Score:
{reference["score"]}

Approach Signals:
Brute Force: {
    "YES" if reference["has_brute"] else "NO"
}
Better: {
    "YES" if reference["has_better"] else "NO"
}
Optimal: {
    "YES" if reference["has_optimal"] else "NO"
}

--------------------------------------------------
JAVA REFERENCE
--------------------------------------------------

File:
{reference["java_file"]}

{java_content}

--------------------------------------------------
README REFERENCE
--------------------------------------------------

File:
{reference["readme_file"]}

{readme_content}

==================================================
END REFERENCE {index}
==================================================
"""

            if (
                total_chars + len(section)
                > self.MAX_TOTAL_CHARS
            ):
                break

            sections.append(section)

            total_chars += len(section)

        if not sections:
            return (
                "NO REAL STYLE REFERENCES COULD BE INCLUDED.\n"
                "Use the explicit style instructions in the prompt."
            )

        return (
            header
            + "\n".join(sections)
        )