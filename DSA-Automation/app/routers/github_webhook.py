import webbrowser
import asyncio
import hashlib
import hmac
import os
import re
from pathlib import PurePosixPath
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.database import SessionLocal
from app.models.draft import Draft
from app.services.ai_generation_service import AIGenerationService
from app.services.dsa_classifier_service import DSAClassifierService
from app.services.github_service import GitHubService
from app.services.leetcode_service import LeetCodeService
from app.services.desktop_notification_service import notify_draft_ready

load_dotenv()

router = APIRouter(prefix="/webhooks")


SUPPORTED_EXTENSIONS = {
    ".java": "Java",
    ".py": "Python",
}


# =========================================================
# Helper: Verify GitHub webhook signature
# =========================================================

def verify_github_signature(
    payload: bytes,
    signature: str | None,
) -> bool:
    """
    Verify that the webhook request came from GitHub.
    """

    secret = os.getenv("GITHUB_WEBHOOK_SECRET")

    if not secret:
        return False

    if not signature:
        return False

    expected_signature = (
        "sha256="
        + hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(
        expected_signature,
        signature,
    )


# =========================================================
# Helper: Detect source language
# =========================================================

def get_source_language(
    file_path: str,
) -> str | None:
    """
    Identify whether the submitted solution is Java or Python.
    """

    extension = PurePosixPath(file_path).suffix.lower()

    return SUPPORTED_EXTENSIONS.get(extension)


# =========================================================
# Helper: Extract problem number + slug
# =========================================================

def extract_problem_info(
    file_path: str,
) -> dict:
    """
    Extract the LeetCode problem number and slug.

    Example:

        0033-search-in-rotated-sorted-array/
        0033-search-in-rotated-sorted-array.java
    """

    path = PurePosixPath(file_path)

    for part in path.parts:

        match = re.match(
            r"^0*(\d+)-(.+)$",
            part,
        )

        if match:

            return {
                "problem_number": int(match.group(1)),
                "problem_slug": match.group(2),
                "leetcode_folder": part,
            }

    return {
        "problem_number": None,
        "problem_slug": None,
        "leetcode_folder": None,
    }


# =========================================================
# Helper: Normalize names for matching
# =========================================================

def normalize_for_match(
    value: str,
) -> str:
    """
    Normalize names for comparison.

    Example:

        Sqrt(x) -> sqrtx
        sqrtx   -> sqrtx
    """

    return re.sub(
        r"[^a-z0-9]",
        "",
        value.lower(),
    )


# =========================================================
# Helper: Find existing DSA problem folder
# =========================================================

def find_existing_problem_folder(
    folders: list[str],
    problem_number: int,
    problem_slug: str,
    problem_title: str,
) -> dict:
    """
    Find an existing DSA problem folder.

    Expected format:

        33_Search in Rotated Sorted Array
        69_Sqrt(x)
        283_Move Zeroes
    """

    expected_prefix = f"{problem_number}_"

    slug_normalized = normalize_for_match(
        problem_slug
    )

    title_normalized = normalize_for_match(
        problem_title
    )

    exact_matches = []
    number_matches = []

    for folder in folders:

        folder_name = PurePosixPath(
            folder
        ).name

        if not folder_name.startswith(
            expected_prefix
        ):
            continue

        number_matches.append(folder)

        problem_name = folder_name[
            len(expected_prefix):
        ]

        problem_name_normalized = normalize_for_match(
            problem_name
        )

        if (
            problem_name_normalized == title_normalized
            or problem_name_normalized == slug_normalized
        ):
            exact_matches.append(folder)

    if exact_matches:

        return {
            "found": True,
            "path": exact_matches[0],
            "matches": exact_matches,
            "number_matches": number_matches,
        }

    return {
        "found": False,
        "path": None,
        "matches": [],
        "number_matches": number_matches,
    }


# =========================================================
# Helper: Inspect files inside a DSA problem folder
# =========================================================

def inspect_problem_files(
    tree: list,
    problem_folder: str,
) -> dict:
    """
    Check which learning files already exist
    directly inside the problem folder.

    Existing files are preserved.
    """

    java_file = None
    python_file = None
    readme_file = None
    other_files = []

    folder_prefix = (
        problem_folder.rstrip("/")
        + "/"
    )

    for item in tree:

        if item.get("type") != "blob":
            continue

        file_path = item.get(
            "path",
            "",
        )

        if not file_path.startswith(
            folder_prefix
        ):
            continue

        relative_path = file_path[
            len(folder_prefix):
        ]

        # Only inspect files directly inside
        # the problem folder.
        if "/" in relative_path:
            continue

        extension = PurePosixPath(
            file_path
        ).suffix.lower()

        file_name = PurePosixPath(
            file_path
        ).name

        if extension == ".java":

            java_file = file_path

        elif extension == ".py":

            python_file = file_path

        elif file_name.lower() == "readme.md":

            readme_file = file_path

        else:

            other_files.append(
                file_path
            )

    return {
        "java_exists": java_file is not None,
        "python_exists": python_file is not None,
        "readme_exists": readme_file is not None,
        "java_file": java_file,
        "python_file": python_file,
        "readme_file": readme_file,
        "other_files": other_files,
    }


# =========================================================
# Helper: Determine missing files
# =========================================================

def determine_missing_files(
    file_status: dict,
) -> list[str]:
    """
    Determine exactly which learning files are missing.

    Existing files are never regenerated automatically.
    """

    missing_files = []

    if not file_status.get("java_exists"):
        missing_files.append("Java")

    if not file_status.get("python_exists"):
        missing_files.append("Python")

    if not file_status.get("readme_exists"):
        missing_files.append("README.md")

    return missing_files


# =========================================================
# Helper: Save AI draft to PostgreSQL
# =========================================================

def save_draft_to_database(
    *,
    problem_number: int,
    problem_title: str,
    topic: str,
    pattern: str | None,
    destination: str | None,
    submitted_language: str,
    source_file: str,
    source_code: str,
    missing_files: list[str],
    java_content: str | None,
    python_content: str | None,
    readme_content: str | None,
) -> int:
    """
    Save generated content as a draft.

    IMPORTANT:
    This function does NOT write anything to GitHub.
    """

    db = SessionLocal()

    try:

        draft = Draft(
            problem_number=problem_number,
            problem_title=problem_title,
            topic=topic,
            pattern=pattern,
            destination=destination,
            submitted_language=submitted_language,
            source_file=source_file,
            source_code=source_code,
            missing_files=missing_files,
            java_content=java_content,
            python_content=python_content,
            readme_content=readme_content,
            feedback=None,
            status="draft",
        )

        db.add(draft)
        db.commit()
        db.refresh(draft)

        return draft.id

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# =========================================================
# Helper: Generate + save one draft
# =========================================================

async def generate_and_save_draft(
    *,
    problem: dict,
    classification: dict,
    destination: str | None,
    submitted_language: str,
    source_file: str,
    source_code: str,
    missing_files: list[str],
) -> dict:
    """
    Generate only missing files and save the result in PostgreSQL.

    No GitHub write happens here.
    """

    if not missing_files:
        return {
            "draft_created": False,
            "draft_id": None,
            "message": "All required files already exist.",
            "generated_files": {
                "java": False,
                "python": False,
                "readme": False,
            },
        }

    selected_topic = classification.get(
        "selected_topic"
    )

    selected_pattern = classification.get(
        "selected_pattern"
    )

    if not selected_topic:
        return {
            "draft_created": False,
            "draft_id": None,
            "message": "Topic classification is incomplete.",
            "generated_files": {
                "java": False,
                "python": False,
                "readme": False,
            },
        }

    ai = AIGenerationService()

    generated = await ai.generate_missing_files(
        problem_number=problem["problem_number"],
        problem_title=problem["title"],
        topic=selected_topic,
        pattern=selected_pattern,
        submitted_language=submitted_language,
        submitted_source=source_code,
        missing_files=missing_files,
    )

    draft_id = save_draft_to_database(
        problem_number=problem["problem_number"],
        problem_title=problem["title"],
        topic=selected_topic,
        pattern=selected_pattern,
        destination=destination,
        submitted_language=submitted_language,
        source_file=source_file,
        source_code=source_code,
        missing_files=missing_files,
        java_content=generated.java,
        python_content=generated.python,
        readme_content=generated.readme,
    )

    return {
        "draft_created": True,
        "draft_id": draft_id,
        "message": "AI draft generated and saved successfully.",
        "generated_files": {
            "java": generated.java is not None,
            "python": generated.python is not None,
            "readme": generated.readme is not None,
        },
    }


# =========================================================
# MAIN GITHUB WEBHOOK
# =========================================================

# Delivery IDs already being processed or completed in this
# running FastAPI process. This prevents repeated redeliveries
# from creating duplicate drafts.
_ACTIVE_DELIVERIES = set()
_PROCESSED_DELIVERIES = set()
MAX_TRACKED_DELIVERIES = 1000


def remember_processed_delivery(
    delivery_id: str,
) -> None:
    """
    Remember a completed GitHub delivery.

    Keep the in-memory set bounded for long-running local use.
    """

    _PROCESSED_DELIVERIES.add(
        delivery_id
    )

    if len(_PROCESSED_DELIVERIES) > MAX_TRACKED_DELIVERIES:

        oldest = next(
            iter(_PROCESSED_DELIVERIES)
        )

        _PROCESSED_DELIVERIES.discard(
            oldest
        )


async def process_github_push(
    data: dict,
    delivery_id: str,
) -> None:
    """
    Run the complete DSA automation pipeline in the background.

    GitHub gets a fast HTTP 200 from the webhook endpoint while
    the slower GitHub/LeetCode/Gemini/PostgreSQL work continues here.
    """

    success = False

    try:

        # =========================================================
        # 4. Repository information
        # =========================================================

        repository = data.get(
            "repository",
            {},
        )

        repository_name = repository.get(
            "name"
        )

        repository_owner = (
            repository.get(
                "owner",
                {},
            ).get("login")
        )

        if not repository_name:

            raise HTTPException(
                status_code=400,
                detail="Repository name missing",
            )

        expected_leetcode_repo = os.getenv(
            "LEETCODE_REPO"
        )

        # Process only the configured LeetCode repo.
        if (
            expected_leetcode_repo
            and repository_name != expected_leetcode_repo
        ):

            return {
                "message": "Repository ignored",
                "repository": repository_name,
                "expected_repository": expected_leetcode_repo,
            }

        # =========================================================
        # 5. Detect Java/Python solution files
        # =========================================================

        github = GitHubService()

        submissions = []

        seen_files = set()

        for commit in data.get(
            "commits",
            [],
        ):

            commit_sha = commit.get(
                "id"
            )

            if not commit_sha:
                continue

            changed_files = (
                commit.get("added", [])
                + commit.get("modified", [])
            )

            for file_path in changed_files:

                language = get_source_language(
                    file_path
                )

                # Ignore README, stats.json,
                # images and other metadata.
                if not language:
                    continue

                problem_info = extract_problem_info(
                    file_path
                )

                if problem_info[
                    "problem_number"
                ] is None:
                    continue

                # Avoid duplicate processing if
                # the same file appears twice.
                unique_key = (
                    commit_sha,
                    file_path,
                )

                if unique_key in seen_files:
                    continue

                seen_files.add(unique_key)

                # =================================================
                # 6. Retrieve submitted source
                # =================================================

                try:

                    source_code = await github.get_file_text(
                        repo=repository_name,
                        path=file_path,
                        ref=commit_sha,
                    )

                except Exception as error:

                    print()
                    print(
                        f"❌ Failed to retrieve {file_path}"
                    )
                    print(
                        f"Error: {error}"
                    )
                    print()

                    continue

                submissions.append(
                    {
                        "problem_number": (
                            problem_info["problem_number"]
                        ),
                        "problem_slug": (
                            problem_info["problem_slug"]
                        ),
                        "leetcode_folder": (
                            problem_info["leetcode_folder"]
                        ),
                        "language": language,
                        "source_file": file_path,
                        "commit_sha": commit_sha,
                        "source_code": source_code,
                    }
                )

        # =========================================================
        # 7. No solution found
        # =========================================================

        if not submissions:

            print()
            print("=" * 75)
            print("❌ NO LEETCODE SOLUTION FOUND")
            print("=" * 75)

            for commit in data.get(
                "commits",
                [],
            ):

                print(
                    f"Commit : {commit.get('id')}"
                )

                print(
                    f"Message: {commit.get('message')}"
                )

                changed_files = (
                    commit.get("added", [])
                    + commit.get("modified", [])
                )

                for file_path in changed_files:

                    print(
                        f"  - {file_path}"
                    )

            print("=" * 75)
            print()

            return {
                "message": (
                    "No Java or Python LeetCode "
                    "solution found in this push"
                ),
                "repository": repository_name,
            }

        # =========================================================
        # 8. DSA repository
        # =========================================================

        dsa_repo = os.getenv(
            "DSA_REPO"
        )

        if not dsa_repo:

            raise HTTPException(
                status_code=500,
                detail="DSA_REPO is missing in .env",
            )

        try:

            dsa_tree_data = (
                await github.get_repository_tree(
                    repo=dsa_repo,
                    branch="main",
                )
            )

        except Exception as error:

            raise HTTPException(
                status_code=502,
                detail=(
                    f"Could not retrieve DSA repository: {error}"
                ),
            )

        if dsa_tree_data.get(
            "truncated",
            False,
        ):

            raise HTTPException(
                status_code=500,
                detail=(
                    "DSA repository tree is too large "
                    "for recursive inspection"
                ),
            )

        dsa_tree = dsa_tree_data.get(
            "tree",
            [],
        )

        # =========================================================
        # 9. Get metadata + classify
        # =========================================================

        leetcode = LeetCodeService()

        for submission in submissions:

            try:

                problem = await leetcode.get_problem_metadata(
                    submission["problem_slug"]
                )

            except Exception as error:

                submission[
                    "metadata_error"
                ] = str(error)

                submission[
                    "classification_status"
                ] = "leetcode_metadata_error"

                continue

            submission[
                "problem_title"
            ] = problem["title"]

            submission[
                "topic_tags"
            ] = problem["topic_tags"]

            # Trust official LeetCode number.
            submission[
                "problem_number"
            ] = problem["problem_number"]

            # -----------------------------------------------------
            # Classify using the user's actual DSA structure.
            # -----------------------------------------------------

            classification = (
                DSAClassifierService.classify(
                    tree=dsa_tree,
                    topic_tags=problem["topic_tags"],
                    title=problem["title"],
                )
            )

            submission[
                "classification"
            ] = classification

            selected_topic = classification.get(
                "selected_topic"
            )

            selected_pattern = classification.get(
                "selected_pattern"
            )

            # -----------------------------------------------------
            # Exact DSA problem folder name.
            # -----------------------------------------------------

            problem_folder_name = (
                f"{problem['problem_number']}_"
                f"{problem['title']}"
            )

            submission[
                "problem_folder_name"
            ] = problem_folder_name

            # -----------------------------------------------------
            # Build destination.
            # -----------------------------------------------------

            classification_status = classification.get(
                "classification_status"
            )

            # Store the classifier status on the submission.
            # Later pipeline stages read this value from the submission.
            submission[
                "classification_status"
            ] = classification_status

            if classification_status == "topic_and_pattern":

                submission[
                    "destination"
                ] = DSAClassifierService.build_destination(
                    topic=selected_topic,
                    pattern=selected_pattern,
                    problem_folder_name=problem_folder_name,
                )

            elif classification_status == "topic_only":

                submission[
                    "destination"
                ] = DSAClassifierService.build_destination(
                    topic=selected_topic,
                    pattern=None,
                    problem_folder_name=problem_folder_name,
                )

            else:

                submission[
                    "destination"
                ] = None

        # =========================================================
        # 10. Inspect existing DSA folders/files
        # =========================================================

        dsa_folders = [
            item["path"]
            for item in dsa_tree
            if item.get("type") == "tree"
        ]

        for submission in submissions:

            classification_status = submission.get(
                "classification_status"
            )

            if classification_status in {
                "leetcode_metadata_error",
                "topic_not_found",
                "pattern_needs_ai",
            }:

                submission[
                    "dsa_problem_folder_found"
                ] = False

                submission[
                    "dsa_problem_folder"
                ] = None

                submission[
                    "files"
                ] = {
                    "java_exists": False,
                    "python_exists": False,
                    "readme_exists": False,
                    "java_file": None,
                    "python_file": None,
                    "readme_file": None,
                    "other_files": [],
                }

                submission[
                    "missing_files"
                ] = []

                continue

            problem_folder_result = (
                find_existing_problem_folder(
                    folders=dsa_folders,
                    problem_number=submission[
                        "problem_number"
                    ],
                    problem_slug=submission[
                        "problem_slug"
                    ],
                    problem_title=submission[
                        "problem_title"
                    ],
                )
            )

            submission[
                "dsa_problem_folder_found"
            ] = problem_folder_result["found"]

            submission[
                "dsa_problem_folder"
            ] = problem_folder_result["path"]

            if problem_folder_result["found"]:

                file_status = inspect_problem_files(
                    tree=dsa_tree,
                    problem_folder=problem_folder_result["path"],
                )

            else:

                file_status = {
                    "java_exists": False,
                    "python_exists": False,
                    "readme_exists": False,
                    "java_file": None,
                    "python_file": None,
                    "readme_file": None,
                    "other_files": [],
                }

            submission[
                "files"
            ] = file_status

            submission[
                "missing_files"
            ] = determine_missing_files(
                file_status
            )

        # =========================================================
        # 11. Generate AI drafts + save to PostgreSQL
        # =========================================================

        for submission in submissions:

            classification_status = submission.get(
                "classification_status"
            )

            # Do not generate until we have
            # enough classification information.
            if classification_status not in {
                "topic_and_pattern",
                "topic_only",
            }:

                submission[
                    "draft_result"
                ] = {
                    "draft_created": False,
                    "draft_id": None,
                    "message": (
                        "Draft not generated because "
                        "classification is incomplete."
                    ),
                }

                continue

            missing_files = submission.get(
                "missing_files",
                [],
            )

            if not missing_files:

                submission[
                    "draft_result"
                ] = {
                    "draft_created": False,
                    "draft_id": None,
                    "message": (
                        "All required files already exist. "
                        "No AI generation required."
                    ),
                }

                continue

            try:

                draft_result = await generate_and_save_draft(
                    problem={
                        "problem_number": submission[
                            "problem_number"
                        ],
                        "title": submission[
                            "problem_title"
                        ],
                    },
                    classification=submission[
                        "classification"
                    ],
                    destination=submission.get(
                        "destination"
                    ),
                    submitted_language=submission[
                        "language"
                    ],
                    source_file=submission[
                        "source_file"
                    ],
                    source_code=submission[
                        "source_code"
                    ],
                    missing_files=missing_files,
                )

                submission[
                    "draft_result"
                ] = draft_result

            except Exception as error:

                print()
                print("=" * 75)
                print("❌ AI DRAFT GENERATION FAILED")
                print("=" * 75)
                print(
                    f"Problem : "
                    f"{submission.get('problem_number')}_"
                    f"{submission.get('problem_title')}"
                )
                print(
                    f"Error   : {error}"
                )
                print("=" * 75)
                print()

                submission[
                    "draft_result"
                ] = {
                    "draft_created": False,
                    "draft_id": None,
                    "message": "AI generation failed.",
                    "error": str(error),
                }

        # =========================================================
        # 12. Print complete pipeline result
        # =========================================================

        print()
        print("=" * 80)
        print("🚀 DSA AUTOMATION PIPELINE")
        print("=" * 80)

        for submission in submissions:

            print()
            print(
                f"Problem Number : "
                f"{submission.get('problem_number')}"
            )

            print(
                f"Problem Title  : "
                f"{submission.get('problem_title', 'Unknown')}"
            )

            print(
                f"Source Language: "
                f"{submission.get('language')}"
            )

            print(
                f"Source File    : "
                f"{submission.get('source_file')}"
            )

            print(
                f"Classification : "
                f"{submission.get('classification_status')}"
            )

            if submission.get("topic_tags"):

                print(
                    f"LeetCode Tags  : "
                    f"{', '.join(submission['topic_tags'])}"
                )

            classification = submission.get(
                "classification"
            )

            if classification:

                print(
                    f"Topic          : "
                    f"{classification.get('selected_topic')}"
                )

                print(
                    f"Pattern        : "
                    f"{classification.get('selected_pattern')}"
                )

                print(
                    f"Patterns Exist : "
                    f"{classification.get('patterns_exist')}"
                )

            print(
                f"Problem Folder : "
                f"{submission.get('problem_folder_name')}"
            )

            print(
                f"Destination    : "
                f"{submission.get('destination')}"
            )

            print()

            if submission.get(
                "dsa_problem_folder_found"
            ):

                print(
                    "✅ Existing DSA problem folder:"
                )

                print(
                    f"   "
                    f"{submission.get('dsa_problem_folder')}"
                )

            else:

                print(
                    "📁 DSA problem folder does not exist yet."
                )

            files = submission.get(
                "files",
                {},
            )

            print()
            print("Existing Files:")

            print(
                f"   Java   : "
                f"{'✅' if files.get('java_exists') else '❌'}"
            )

            print(
                f"   Python : "
                f"{'✅' if files.get('python_exists') else '❌'}"
            )

            print(
                f"   README : "
                f"{'✅' if files.get('readme_exists') else '❌'}"
            )

            missing_files = submission.get(
                "missing_files",
                [],
            )

            print()
            print("Missing Files:")

            if missing_files:

                for file_name in missing_files:

                    print(
                        f"   → {file_name}"
                    )

            else:

                print(
                    "   → None"
                )

            draft_result = submission.get(
                "draft_result",
                {},
            )

            print()
            print("AI Draft:")

            if draft_result.get(
                "draft_created"
            ):

                print(
                    "   ✅ Draft generated"
                )

                print(
                    f"   Draft ID      : "
                    f"{draft_result.get('draft_id')}"
                )

                print(
                    "   PostgreSQL    : ✅ Saved"
                )

                print(
                    "   GitHub write  : ❌ Not performed"
                )

            else:

                print(
                    f"   ℹ️ {draft_result.get('message')}"
                )

        print()
        print("=" * 80)
        print()

        # =========================================================
        # 13. Return safe API response
        # =========================================================

        response_submissions = []

        for submission in submissions:

            # Never expose submitted source code
            # in the webhook API response.
            safe_submission = {
                key: value
                for key, value in submission.items()
                if key != "source_code"
            }

            response_submissions.append(
                safe_submission
            )

        success = True

        return {
            "message": (
                "LeetCode submission processed "
                "through DSA automation pipeline"
            ),
            "repository": repository_name,
            "owner": repository_owner,
            "dsa_repository": dsa_repo,
            "submissions": response_submissions,
            "github_write_performed": False,
        }


    # =========================================================


    except Exception as error:

        print()
        print("=" * 80)
        print("❌ BACKGROUND WEBHOOK PROCESSING FAILED")
        print("=" * 80)
        print(
            f"Delivery ID : {delivery_id}"
        )
        print(
            f"Error       : {error}"
        )
        print("=" * 80)
        print()

    finally:

        _ACTIVE_DELIVERIES.discard(
            delivery_id
        )

        if success:

            remember_processed_delivery(
                delivery_id
            )


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(
        default=None
    ),
    x_github_event: str | None = Header(
        default=None
    ),
    x_github_delivery: str | None = Header(
        default=None
    ),
):
    """
    Receive GitHub webhook requests quickly.

    The request is validated first, then the complete DSA
    pipeline is scheduled as a background task so GitHub
    does not have to wait for Gemini generation.

    No GitHub DSA write happens in this webhook worker.
    """

    payload = await request.body()

    # =========================================================
    # 1. Verify webhook signature
    # =========================================================

    if not verify_github_signature(
        payload,
        x_hub_signature_256,
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid GitHub webhook signature",
        )

    # =========================================================
    # 2. Parse payload
    # =========================================================

    try:

        data = await request.json()

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Invalid JSON payload",
        )

    # =========================================================
    # 3. Only process push events
    # =========================================================

    if x_github_event != "push":

        return {
            "message": "Event ignored",
            "event": x_github_event,
        }

    # =========================================================
    # 4. Get GitHub delivery ID
    # =========================================================

    if not x_github_delivery:

        x_github_delivery = hashlib.sha256(
            payload
        ).hexdigest()

    # =========================================================
    # 5. Prevent duplicate deliveries
    # =========================================================

    if (
        x_github_delivery in _ACTIVE_DELIVERIES
        or
        x_github_delivery in _PROCESSED_DELIVERIES
    ):

        print()
        print(
            "ℹ️ Duplicate GitHub delivery ignored:"
        )
        print(
            f"   {x_github_delivery}"
        )
        print()

        return {
            "message": "Duplicate delivery ignored",
            "delivery_id": x_github_delivery,
        }

    _ACTIVE_DELIVERIES.add(
        x_github_delivery
    )

    # =========================================================
    # 6. Schedule background processing
    # =========================================================

    background_tasks.add_task(
        process_github_push,
        data,
        x_github_delivery,
    )

    print()
    print("=" * 80)
    print("✅ GITHUB WEBHOOK ACCEPTED")
    print("=" * 80)
    print(
        f"Delivery ID : {x_github_delivery}"
    )
    print(
        "Processing  : BACKGROUND"
    )
    print(
        "Response    : HTTP 200"
    )
    print("=" * 80)
    print()

    # Return immediately.
    return {
        "message": (
            "GitHub webhook accepted; "
            "DSA automation running in background"
        ),
        "delivery_id": x_github_delivery,
        "processing": "background",
        "github_write_performed": False,
    }


# =========================================================
# BACKFILL: SCAN EXISTING LEETCODE PROBLEMS
# =========================================================


# =========================================================
# BACKFILL: GENERATE READY PROBLEMS
# =========================================================

@router.post("/backfill/generate")

async def backfill_generate(
    limit: int = 25,
    max_workers: int = 2,
    problem_numbers: str | None = None,
):

    """
    Generate AI drafts for already-classified backfill problems.

    IMPORTANT:
        - Uses the existing backfill scan as the source of truth.
        - Processes only problems whose action is ready_for_backfill.
        - Generates ONLY the files reported as missing.
        - Existing files are preserved.
        - Saves each generated result to PostgreSQL.
        - Does NOT write anything to GitHub.

    limit=25 processes up to 25 ready problems.
    max_workers=2 keeps Gemini generation reasonably fast
    without launching a large burst of requests.
    """

    if limit < 1:
        raise HTTPException(
            status_code=400,
            detail="limit must be at least 1.",
        )

    if max_workers < 1 or max_workers > 3:
        raise HTTPException(
            status_code=400,
            detail="max_workers must be between 1 and 3.",
        )

    # Reuse the already-tested scan logic.
    scan_result = await backfill_scan(limit=0)
    
    ready = [
        item
        for item in scan_result.get("problems", [])
        if item.get("action") == "ready_for_backfill"
]

    if problem_numbers:
        requested_numbers = {
            int(number.strip())
            for number in problem_numbers.split(",")
            if number.strip()
    }
    ready = [
        item for item in ready
        if item.get("problem_number") in requested_numbers
    ]

    ready = ready[:limit]



    
    


    if not ready:
        return {
            "message": "No ready backfill problems found.",
            "selected": 0,
            "generated": 0,
            "skipped_existing_draft": 0,
            "failed": 0,
            "github_write_performed": False,
            "postgresql_draft_created": False,
            "results": [],
        }


    github = GitHubService()

    # Retrieve all source files first. One source file is enough
    # because the AI service generates the missing Java/Python/README
    # set from the submitted solution.
    source_jobs = []

    for item in ready:
        source_files = item.get("source_files") or []
        if not source_files:
            source_jobs.append((item, None, None))
            continue

        java_paths = [
            path
            for path in source_files
            if get_source_language(path) == "Java"
        ]

        source_path = (
            java_paths[0]
            if java_paths
            else source_files[0]
        )

        source_jobs.append(
            (
                item,
                source_path,
                get_source_language(source_path),
            )
        )

    async def fetch_source(job):
        item, source_path, language = job

        if not source_path or not language:
            return item, source_path, language, None, "Source file unavailable."

        try:
            source_code = await github.get_file_text(
                repo=os.getenv("LEETCODE_REPO"),
                path=source_path,
            )
            return item, source_path, language, source_code, None
        except Exception as error:
            return item, source_path, language, None, str(error)

    fetched = await asyncio.gather(
        *(fetch_source(job) for job in source_jobs)
    )

    # Prepare only valid generation jobs.
    generation_jobs = []
    results = []

    for item, source_path, language, source_code, source_error in fetched:
        base_result = {
            "problem_number": item.get("problem_number"),
            "problem_title": item.get("problem_title"),
            "topic": item.get("topic"),
            "pattern": item.get("pattern"),
            "destination": item.get("destination"),
            "missing_files": item.get("missing_files", []),
            "source_file": source_path,
            "source_language": language,
        }

        if source_error:
            base_result.update({
                "status": "failed",
                "message": "Could not retrieve LeetCode source.",
                "error": source_error,
            })
            results.append(base_result)
            continue

        generation_jobs.append(
            (
                item,
                source_path,
                language,
                source_code,
            )
        )

    def run_one_generation(job):
        item, source_path, language, source_code = job

        problem_number = item["problem_number"]

        # Avoid creating duplicate drafts when this endpoint is run again.
        db = SessionLocal()
        try:
            existing_draft = (
                db.query(Draft)
                .filter(Draft.problem_number == problem_number)
                .order_by(Draft.id.desc())
                .first()
            )
        finally:
            db.close()

        if existing_draft and existing_draft.status in {
            "draft",
            "approved",
            "committed",
        }:
            return {
                "problem_number": problem_number,
                "problem_title": item["problem_title"],
                "topic": item["topic"],
                "pattern": item["pattern"],
                "destination": item["destination"],
                "missing_files": item.get("missing_files", []),
                "source_file": source_path,
                "source_language": language,
                "status": "skipped_existing_draft",
                "draft_id": existing_draft.id,
            }

        try:
            draft_result = asyncio.run(
                generate_and_save_draft(
                    problem={
                        "problem_number": problem_number,
                        "title": item["problem_title"],
                    },
                    classification={
                        "selected_topic": item["topic"],
                        "selected_pattern": item["pattern"],
                        "classification_status": item.get(
                            "classification_status"
                        ),
                    },
                    destination=item["destination"],
                    submitted_language=language,
                    source_file=source_path,
                    source_code=source_code,
                    missing_files=item.get("missing_files", []),
                )
            )

            return {
                "problem_number": problem_number,
                "problem_title": item["problem_title"],
                "topic": item["topic"],
                "pattern": item["pattern"],
                "destination": item["destination"],
                "missing_files": item.get("missing_files", []),
                "source_file": source_path,
                "source_language": language,
                "status": (
                    "generated"
                    if draft_result.get("draft_created")
                    else "skipped"
                ),
                "draft_id": draft_result.get("draft_id"),
                "generated_files": draft_result.get(
                    "generated_files"
                ),
                "message": draft_result.get("message"),
            }
        except Exception as error:
            return {
                "problem_number": problem_number,
                "problem_title": item["problem_title"],
                "topic": item["topic"],
                "pattern": item["pattern"],
                "destination": item["destination"],
                "missing_files": item.get("missing_files", []),
                "source_file": source_path,
                "source_language": language,
                "status": "failed",
                "error": str(error),
            }

    # Gemini generation is blocking inside AIGenerationService, so
    # run a small number of jobs in worker threads to reduce total time.
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(run_one_generation, job)
            for job in generation_jobs
        ]

        for future in as_completed(futures):
            results.append(future.result())

    generated_count = sum(
        1
        for item in results
        if item.get("status") == "generated"
    )

    skipped_count = sum(
        1
        for item in results
        if item.get("status") in {
            "skipped_existing_draft",
            "skipped",
        }
    )

    failed_count = sum(
        1
        for item in results
        if item.get("status") == "failed"
    )

    results.sort(
        key=lambda item: item.get("problem_number", 0)
    )

    print()
    print("=" * 80)
    print("🚀 DSA BACKFILL GENERATION")
    print("=" * 80)
    print(f"Selected problems : {len(ready)}")
    print(f"Generated drafts  : {generated_count}")
    print(f"Skipped           : {skipped_count}")
    print(f"Failed            : {failed_count}")
    print("PostgreSQL        : ✅")
    print("GitHub write      : ❌ NO")
    print("=" * 80)
    print()

    return {
        "message": "Backfill AI generation completed.",
        "selected": len(ready),
        "generated": generated_count,
        "skipped_existing_draft": skipped_count,
        "failed": failed_count,
        "github_write_performed": False,
        "postgresql_draft_created": generated_count > 0,
        "results": results,
    }

@router.get("/backfill/scan")
async def backfill_scan(
    limit: int = 10,
):
    """
    Scan old Java/Python LeetCode solutions already present
    in the Leetcode repository.

    IMPORTANT:
        - No AI generation.
        - No PostgreSQL draft creation.
        - No GitHub write.
        - Only inspection/classification is performed.

    Use limit=0 to scan all discovered problems.
    """

    leetcode_repo = os.getenv("LEETCODE_REPO")
    dsa_repo = os.getenv("DSA_REPO")

    if not leetcode_repo:
        raise HTTPException(
            status_code=500,
            detail="LEETCODE_REPO is missing in .env",
        )

    if not dsa_repo:
        raise HTTPException(
            status_code=500,
            detail="DSA_REPO is missing in .env",
        )

    if limit < 0:
        raise HTTPException(
            status_code=400,
            detail="limit must be 0 or a positive integer.",
        )

    github = GitHubService()
    leetcode = LeetCodeService()

    # =========================================================
    # 1. Read LeetCode repository tree.
    # =========================================================

    try:
        leetcode_tree_data = await github.get_repository_tree(
            repo=leetcode_repo,
            branch="main",
        )
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Could not retrieve LeetCode repository: {error}"
            ),
        ) from error

    if leetcode_tree_data.get("truncated", False):
        raise HTTPException(
            status_code=500,
            detail=(
                "LeetCode repository tree is truncated. "
                "Backfill scan cannot safely inspect all problems."
            ),
        )

    leetcode_tree = leetcode_tree_data.get(
        "tree",
        [],
    )

    # =========================================================
    # 2. Read DSA repository tree once.
    # =========================================================

    try:
        dsa_tree_data = await github.get_repository_tree(
            repo=dsa_repo,
            branch="main",
        )
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Could not retrieve DSA repository: {error}"
            ),
        ) from error

    if dsa_tree_data.get("truncated", False):
        raise HTTPException(
            status_code=500,
            detail=(
                "DSA repository tree is truncated. "
                "Backfill scan cannot safely inspect all problems."
            ),
        )

    dsa_tree = dsa_tree_data.get(
        "tree",
        [],
    )

    dsa_folders = [
        item.get("path")
        for item in dsa_tree
        if item.get("type") == "tree"
        and item.get("path")
    ]

    # =========================================================
    # 3. Discover unique old LeetCode problems.
    # =========================================================

    discovered = {}

    for item in leetcode_tree:

        if item.get("type") != "blob":
            continue

        file_path = item.get("path", "")
        language = get_source_language(file_path)

        if not language:
            continue

        problem_info = extract_problem_info(file_path)

        if problem_info["problem_number"] is None:
            continue

        key = (
            problem_info["problem_number"],
            problem_info["problem_slug"],
        )

        if key not in discovered:
            discovered[key] = {
                "problem_number": problem_info[
                    "problem_number"
                ],
                "problem_slug": problem_info[
                    "problem_slug"
                ],
                "leetcode_folder": problem_info[
                    "leetcode_folder"
                ],
                "source_files": [],
                "source_languages": [],
            }

        discovered[key]["source_files"].append(
            file_path
        )

        if language not in discovered[key]["source_languages"]:
            discovered[key]["source_languages"].append(
                language
            )

    discovered_problems = sorted(
        discovered.values(),
        key=lambda item: item["problem_number"],
    )

    total_discovered = len(discovered_problems)

    if limit > 0:
        problems_to_scan = discovered_problems[:limit]
    else:
        problems_to_scan = discovered_problems

    # =========================================================
    # 4. Inspect + classify each old problem.
    # =========================================================

    results = []

    for item in problems_to_scan:

        result = {
            "problem_number": item["problem_number"],
            "problem_slug": item["problem_slug"],
            "leetcode_folder": item["leetcode_folder"],
            "source_files": sorted(item["source_files"]),
            "source_languages": sorted(item["source_languages"]),
            "problem_title": None,
            "topic_tags": [],
            "classification_status": None,
            "topic": None,
            "pattern": None,
            "destination": None,
            "dsa_problem_folder_found": False,
            "dsa_problem_folder": None,
            "existing_files": {
                "java_exists": False,
                "python_exists": False,
                "readme_exists": False,
            },
            "missing_files": [
                "Java",
                "Python",
                "README.md",
            ],
            "action": None,
        }

        # -----------------------------------------------------
        # LeetCode metadata.
        # -----------------------------------------------------

        try:
            problem = await leetcode.get_problem_metadata(
                item["problem_slug"]
            )
        except Exception as error:
            result["classification_status"] = (
                "leetcode_metadata_error"
            )
            result["action"] = "metadata_error"
            result["error"] = str(error)
            results.append(result)
            continue

        result["problem_title"] = problem["title"]
        result["topic_tags"] = problem["topic_tags"]

        # -----------------------------------------------------
        # Classify from the user's real DSA hierarchy.
        # -----------------------------------------------------

        classification = DSAClassifierService.classify(
            tree=dsa_tree,
            topic_tags=problem["topic_tags"],
            title=problem["title"],
        )

        result["classification_status"] = classification.get(
            "classification_status"
        )
        result["topic"] = classification.get(
            "selected_topic"
        )
        result["pattern"] = classification.get(
            "selected_pattern"
        )

        if result["topic"]:
            problem_folder_name = (
                f"{problem['problem_number']}_"
                f"{problem['title']}"
            )

            result["destination"] = (
                DSAClassifierService.build_destination(
                    topic=result["topic"],
                    pattern=result["pattern"]
                    if result["classification_status"]
                    == "topic_and_pattern"
                    else None,
                    problem_folder_name=problem_folder_name,
                )
            )

        # -----------------------------------------------------
        # Find existing DSA problem folder.
        # -----------------------------------------------------

        if result["classification_status"] in {
            "topic_and_pattern",
            "topic_only",
        }:

            existing_folder = find_existing_problem_folder(
                folders=dsa_folders,
                problem_number=problem["problem_number"],
                problem_slug=problem["title_slug"],
                problem_title=problem["title"],
            )

            result["dsa_problem_folder_found"] = (
                existing_folder["found"]
            )
            result["dsa_problem_folder"] = (
                existing_folder["path"]
            )

            if existing_folder["found"]:
                file_status = inspect_problem_files(
                    tree=dsa_tree,
                    problem_folder=existing_folder["path"],
                )
                result["existing_files"] = {
                    "java_exists": file_status[
                        "java_exists"
                    ],
                    "python_exists": file_status[
                        "python_exists"
                    ],
                    "readme_exists": file_status[
                        "readme_exists"
                    ],
                }
                result["missing_files"] = (
                    determine_missing_files(file_status)
                )

            if not result["missing_files"]:
                result["action"] = "complete"
            else:
                result["action"] = "ready_for_backfill"

        else:
            result["action"] = "needs_classification"
            result["missing_files"] = []

        results.append(result)

    # =========================================================
    # 5. Summary.
    # =========================================================

    complete_count = sum(
        1
        for item in results
        if item["action"] == "complete"
    )

    ready_count = sum(
        1
        for item in results
        if item["action"] == "ready_for_backfill"
    )

    unresolved_count = sum(
        1
        for item in results
        if item["action"] == "needs_classification"
    )

    metadata_error_count = sum(
        1
        for item in results
        if item["action"] == "metadata_error"
    )

    print()
    print("=" * 80)
    print("🔎 DSA BACKFILL SCAN")
    print("=" * 80)
    print(
        f"LeetCode problems discovered : {total_discovered}"
    )
    print(
        f"Problems scanned              : "
        f"{len(problems_to_scan)}"
    )
    print(
        f"Already complete              : {complete_count}"
    )
    print(
        f"Ready for backfill            : {ready_count}"
    )
    print(
        f"Needs classification          : {unresolved_count}"
    )
    print(
        f"Metadata errors               : {metadata_error_count}"
    )
    print("GitHub write                  : ❌ NO")
    print("AI generation                : ❌ NO")
    print("PostgreSQL drafts             : ❌ NO")
    print("=" * 80)
    print()

    for item in results:
        print(
            f"{item['problem_number']}. "
            f"{item['problem_title'] or item['problem_slug']} "
            f"→ {item['action']}"
        )
        if item["topic"]:
            print(
                f"   Topic={item['topic']} | "
                f"Pattern={item['pattern']}"
            )
        if item["destination"]:
            print(
                f"   Destination={item['destination']}"
            )
        print(
            f"   Missing={item['missing_files']}"
        )

    return {
        "message": "Backfill scan completed successfully",
        "leetcode_repository": leetcode_repo,
        "dsa_repository": dsa_repo,
        "total_discovered": total_discovered,
        "scanned": len(problems_to_scan),
        "limit": limit,
        "summary": {
            "complete": complete_count,
            "ready_for_backfill": ready_count,
            "needs_classification": unresolved_count,
            "metadata_errors": metadata_error_count,
        },
        "github_write_performed": False,
        "ai_generation_performed": False,
        "postgresql_draft_created": False,
        "problems": results,
    }
