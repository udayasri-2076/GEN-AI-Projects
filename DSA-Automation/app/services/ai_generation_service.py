import asyncio
import json
import os
import random
import re

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel

load_dotenv()


class GeneratedFiles(BaseModel):
    """
    AI-generated DSA files.

    Any file that was not requested should be None.
    """

    java: str | None = None
    python: str | None = None
    readme: str | None = None


class AIGenerationService:
    """
    Generates DSA file drafts.

    IMPORTANT:
    - Does NOT write to GitHub.
    - Does NOT overwrite existing files.
    - Generates only requested missing files.
    - Supports regeneration using user feedback.
    - Retries temporary Gemini failures.
    """

    MAX_RETRIES = 4
    BASE_DELAY = 3

    def __init__(self):
        api_key = os.getenv(
            "GEMINI_API_KEY"
        )

        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is missing in .env"
            )

        self.model = os.getenv(
            "GEMINI_MODEL",
            "gemini-3.5-flash-lite",
        )

        self.client = genai.Client(
            api_key=api_key
        )

    # =========================================================
    # NORMAL GENERATION PROMPT
    # =========================================================

    def build_prompt(
        self,
        problem_number: int,
        problem_title: str,
        topic: str,
        pattern: str | None,
        submitted_language: str,
        submitted_source: str,
        missing_files: list[str],
    ) -> str:
        """
        Build the prompt for first-time generation.
        """

        pattern_text = (
            pattern
            if pattern
            else "None"
        )

        missing_text = ", ".join(
            missing_files
        )

        return f"""
You are generating personal DSA study files for my
DSA repository.

Generate ONLY these missing files:

{missing_text}

Do NOT generate any file that is not requested.

==================================================
PROBLEM
==================================================

Problem Number:
{problem_number}

Problem Title:
{problem_title}

Topic:
{topic}

Pattern:
{pattern_text}

Submitted Language:
{submitted_language}

==================================================
SUBMITTED LEETCODE SOLUTION
==================================================

This is the solution I submitted to LeetCode.

Use it as the source of my actual algorithmic reasoning.

Do not blindly translate syntax.

Preserve the actual reasoning and approach.

----- SOURCE START -----

{submitted_source}

----- SOURCE END -----

==================================================
USER'S REFERENCE STYLE
==================================================

You MUST follow the user's existing DSA reference style.

Do not replace it with your own generic coding style.

The user's Java and Python solutions should follow
the same reasoning and learning structure.

The generated code should resemble the user's existing
DSA files.

IMPORTANT:

The user writes code together with the explanation.

The dry run is performed directly beside the code.

Do not move the complete dry run into a separate
paragraph.

Do not replace the detailed dry-run style with
short generic comments.

Use the user's reference as the source of truth.

==================================================
APPROACH STRUCTURE
==================================================

Use the following approach order when genuinely applicable:

1. Brute Force
2. Better
3. Optimal

Do NOT invent an unnecessary Better approach.

If only two meaningful approaches exist, use only two.

If only one meaningful approach exists, do not force
extra approaches.

For every approach provide:

- Approach
- Algorithm
- Time Complexity
- Space Complexity

==================================================
CODE COMMENT STYLE
==================================================

The code must contain detailed learning comments
similar to the user's reference.

The comments should explain what is happening during
the actual example/dry run.

Follow the reference style for:

- variable values
- index values
- pointer movement
- loop iterations
- condition evaluation
- result updates
- changes to sums/counters/maps/etc.

Comments should appear beside the relevant code.

Example:

left = 0       # Example: left starts at index 0

The important requirement is:

DO NOT just explain what the code does.

SHOW THE DRY RUN THROUGH THE CODE.

For loops, show how the values change.

For conditions, show how the condition evaluates.

For pointer movement, show the new pointer values.

For result updates, show the new result value.

The comments should be concrete and based on a real
small example.

==================================================
JAVA
==================================================

Generate normal executable Java code.

Preserve the user's reasoning and detailed comment style.

Do not produce a bare LeetCode solution.

==================================================
PYTHON
==================================================

Generate executable Python code.

The Python solution must preserve the SAME:

- reasoning
- approaches
- dry-run logic
- examples
- learning style
- detailed comments

as the Java solution.

Only the programming-language syntax should change.

Do NOT make Python a shorter or simplified version
of Java.

==================================================
README
==================================================

Follow the user's existing README organization.

Use:

# Problem Title - LeetCode Number

## Problem Statement

## Approach 1: Brute Force
### Approach
### Algorithm
### Time Complexity
### Space Complexity

## Approach 2: ...
### Approach
### Algorithm
### Time Complexity
### Space Complexity

## Comparison of Approaches

## Concepts Used

## Sample Input

## Sample Output

Use the official problem title.

Mention the relevant Topic and Pattern where applicable.

Keep the README detailed and learning-oriented.

Do not make it look like a generic AI-generated README.

==================================================
IMPORTANT RULES
==================================================

1. Generate ONLY requested files.

2. Do not generate files that already exist.

3. Do not overwrite existing files.

4. Preserve the user's original submitted source
   as the basis for reasoning.

5. Do not invent fake algorithms.

6. Do not remove useful details just to make the answer shorter.

7. Follow the user's reference style rather than
   inventing a new style.

8. Use concrete examples for dry runs.

9. The code should remain executable.

==================================================
OUTPUT
==================================================

Return ONE JSON object only:

{{
  "java": null,
  "python": null,
  "readme": null
}}

Rules:

- If Java is requested, put the complete Java file
  content inside "java".

- If Python is requested, put the complete Python file
  content inside "python".

- If README.md is requested, put the complete README
  content inside "readme".

- Any file NOT requested MUST be null.

- Do not use markdown fences.

- Do not add explanation outside the JSON.
"""

    # =========================================================
    # CLEAN JSON
    # =========================================================

    @staticmethod
    def clean_json_response(
        text: str,
    ) -> str:
        """
        Remove accidental markdown fences from
        the model response.
        """

        text = text.strip()

        text = re.sub(
            r"^```json\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\s*```$",
            "",
            text,
        )

        return text.strip()

    # =========================================================
    # RETRYABLE ERRORS
    # =========================================================

    @staticmethod
    def is_retryable_error(
        error: Exception,
    ) -> bool:
        """
        Check whether a Gemini error is temporary
        and reasonable to retry.
        """

        error_text = str(
            error
        ).lower()

        retryable_markers = [
            "503",
            "unavailable",
            "service unavailable",
            "500",
            "internal server error",
            "429",
            "rate limit",
            "resource exhausted",
            "temporarily unavailable",
            "overloaded",
        ]

        return any(
            marker in error_text
            for marker in retryable_markers
        )

    # =========================================================
    # NORMAL GENERATION
    # =========================================================

    async def generate_missing_files(
        self,
        problem_number: int,
        problem_title: str,
        topic: str,
        pattern: str | None,
        submitted_language: str,
        submitted_source: str,
        missing_files: list[str],
    ) -> GeneratedFiles:
        """
        Generate the requested missing files.

        Does NOT write anything to GitHub.
        """

        if not missing_files:

            return GeneratedFiles()

        prompt = self.build_prompt(
            problem_number=problem_number,
            problem_title=problem_title,
            topic=topic,
            pattern=pattern,
            submitted_language=submitted_language,
            submitted_source=submitted_source,
            missing_files=missing_files,
        )

        last_error = None

        for attempt in range(
            1,
            self.MAX_RETRIES + 1,
        ):

            try:

                print(
                    f"🤖 Gemini generation attempt "
                    f"{attempt}/{self.MAX_RETRIES}"
                )

                response = (
                    self.client
                    .models
                    .generate_content(
                        model=self.model,
                        contents=prompt,
                        config={
                            "response_mime_type": (
                                "application/json"
                            ),
                            # Force Gemini to follow the exact Pydantic
                            # output structure instead of relying only on
                            # prompt instructions for valid JSON.
                            "response_schema": GeneratedFiles,
                        },
                    )
                )

                # Google GenAI can return a parsed Pydantic object when
                # response_schema is supplied. Prefer that path because
                # it avoids fragile manual JSON parsing.
                parsed = getattr(
                    response,
                    "parsed",
                    None,
                )

                if isinstance(parsed, GeneratedFiles):
                    result = parsed

                elif parsed is not None:
                    result = GeneratedFiles.model_validate(
                        parsed
                    )

                else:

                    if not response.text:

                        raise RuntimeError(
                            "Gemini returned an empty response."
                        )

                    cleaned_response = (
                        self.clean_json_response(
                            response.text
                        )
                    )

                    try:

                        result = GeneratedFiles.model_validate_json(
                            cleaned_response
                        )

                    except Exception as error:

                        raise RuntimeError(
                            "Gemini returned invalid structured JSON.\n"
                            f"Raw response:\n"
                            f"{response.text}"
                        ) from error

                # -------------------------------------------------
                # Safety:
                # Never return files that were not requested.
                # -------------------------------------------------

                requested = {
                    value.lower()
                    for value in missing_files
                }

                if "java" not in requested:

                    result.java = None

                if "python" not in requested:

                    result.python = None

                if "readme.md" not in requested:

                    result.readme = None

                print(
                    "✅ Gemini generation succeeded."
                )

                return result

            except Exception as error:

                last_error = error

                print(
                    f"❌ Gemini attempt "
                    f"{attempt} failed:"
                )

                print(
                    f"   {error}"
                )

                # -------------------------------------------------
                # Permanent error -> stop immediately.
                # -------------------------------------------------

                if not self.is_retryable_error(
                    error
                ):

                    raise RuntimeError(
                        f"Gemini generation failed: "
                        f"{error}"
                    ) from error

                # -------------------------------------------------
                # No more attempts.
                # -------------------------------------------------

                if attempt >= self.MAX_RETRIES:

                    break

                delay = (
                    self.BASE_DELAY
                    * (2 ** (attempt - 1))
                )

                jitter = random.uniform(
                    0,
                    1.5,
                )

                total_delay = (
                    delay
                    + jitter
                )

                print(
                    "⏳ Temporary Gemini error."
                )

                print(
                    f"   Retrying in "
                    f"{total_delay:.1f} seconds..."
                )

                await asyncio.sleep(
                    total_delay
                )

        raise RuntimeError(
            "Gemini generation failed after "
            f"{self.MAX_RETRIES} attempts: "
            f"{last_error}"
        )

    # =========================================================
    # REGENERATION PROMPT
    # =========================================================

    def build_regeneration_prompt(
        self,
        problem_number: int,
        problem_title: str,
        topic: str,
        pattern: str | None,
        submitted_language: str,
        submitted_source: str,
        feedback: str,
        selected_files: list[str],
        current_java: str | None,
        current_python: str | None,
        current_readme: str | None,
    ) -> str:
        """
        Build the prompt used after the user reviews
        a draft and asks for changes.
        """

        pattern_text = (
            pattern
            if pattern
            else "None"
        )

        selected_files_text = ", ".join(
            selected_files
        )

        return f"""
You are revising DSA learning files for my personal
DSA repository.

The user has already reviewed an earlier draft.

You MUST regenerate ONLY the files selected by the user.

==================================================
PROBLEM
==================================================

Problem Number:
{problem_number}

Problem Title:
{problem_title}

Topic:
{topic}

Pattern:
{pattern_text}

Submitted Language:
{submitted_language}

==================================================
ORIGINAL LEETCODE SOLUTION
==================================================

Use this as the source of the user's actual algorithmic
reasoning.

----- SOURCE START -----

{submitted_source}

----- SOURCE END -----

==================================================
USER FEEDBACK
==================================================

The user says:

{feedback}

You MUST apply this feedback carefully.

==================================================
FILES SELECTED FOR REGENERATION
==================================================

{selected_files_text}

Only these files may change.

Files that are NOT selected must remain unchanged.

==================================================
CURRENT DRAFT
==================================================

JAVA:

----- JAVA START -----

{current_java or "Not available"}

----- JAVA END -----


PYTHON:

----- PYTHON START -----

{current_python or "Not available"}

----- PYTHON END -----


README:

----- README START -----

{current_readme or "Not available"}

----- README END -----

==================================================
USER'S REFERENCE STYLE
==================================================

Follow the user's existing DSA reference exactly.

Do not invent a different style.

The user wants:

- detailed learning-oriented code
- Brute Force when genuinely applicable
- Better when genuinely applicable
- Optimal when genuinely applicable
- detailed comments
- dry-run information beside the code
- concrete example values
- loop iteration tracking
- pointer/index changes
- condition evaluation
- result changes
- time complexity
- space complexity

The Java and Python files must contain the SAME reasoning
and SAME learning structure.

Python must not become a simplified version of Java.

The README must follow the user's reference organization.

==================================================
VERY IMPORTANT COMMENTING RULE
==================================================

Do not merely add a few comments.

The user's reference uses the code itself to teach the
algorithm.

Comments should track the example as the code executes.

Show variable changes beside relevant statements.

Show loop progression.

Show condition evaluation.

Show pointer movement.

Show result updates.

Follow the user's reference rather than creating
generic AI comments.

==================================================
REGENERATION RULES
==================================================

1. Change ONLY selected files.

2. Do NOT modify unselected files.

3. Do NOT remove useful information from the previous draft
   unless the user's feedback requires it.

4. Do NOT invent unnecessary approaches.

5. Preserve correct parts of the current draft.

6. Apply the user's feedback directly.

7. Return complete file contents for selected files.

==================================================
OUTPUT
==================================================

Return ONE JSON object only:

{{
  "java": null,
  "python": null,
  "readme": null
}}

Rules:

- Selected Java -> complete Java content in "java".
- Selected Python -> complete Python content in "python".
- Selected README.md -> complete README content in "readme".

Any file NOT selected MUST be null.

Do not use markdown fences.

Do not add explanation outside the JSON.
"""

    # =========================================================
    # REGENERATION
    # =========================================================

    async def regenerate_files(
        self,
        problem_number: int,
        problem_title: str,
        topic: str,
        pattern: str | None,
        submitted_language: str,
        submitted_source: str,
        feedback: str,
        selected_files: list[str],
        current_java: str | None,
        current_python: str | None,
        current_readme: str | None,
    ) -> GeneratedFiles:
        """
        Regenerate only the files selected by the user.

        Does NOT write anything to GitHub.
        """

        if not selected_files:

            raise ValueError(
                "No files selected for regeneration."
            )

        if not feedback.strip():

            raise ValueError(
                "Feedback cannot be empty."
            )

        prompt = (
            self.build_regeneration_prompt(
                problem_number=problem_number,
                problem_title=problem_title,
                topic=topic,
                pattern=pattern,
                submitted_language=submitted_language,
                submitted_source=submitted_source,
                feedback=feedback,
                selected_files=selected_files,
                current_java=current_java,
                current_python=current_python,
                current_readme=current_readme,
            )
        )

        last_error = None

        for attempt in range(
            1,
            self.MAX_RETRIES + 1,
        ):

            try:

                print(
                    f"🤖 Gemini regeneration attempt "
                    f"{attempt}/{self.MAX_RETRIES}"
                )

                response = (
                    self.client
                    .models
                    .generate_content(
                        model=self.model,
                        contents=prompt,
                        config={
                            "response_mime_type": (
                                "application/json"
                            ),
                            # Force Gemini to follow the exact Pydantic
                            # output structure instead of relying only on
                            # prompt instructions for valid JSON.
                            "response_schema": GeneratedFiles,
                        },
                    )
                )

                # Google GenAI can return a parsed Pydantic object when
                # response_schema is supplied. Prefer that path because
                # it avoids fragile manual JSON parsing.
                parsed = getattr(
                    response,
                    "parsed",
                    None,
                )

                if isinstance(parsed, GeneratedFiles):
                    result = parsed

                elif parsed is not None:
                    result = GeneratedFiles.model_validate(
                        parsed
                    )

                else:

                    if not response.text:

                        raise RuntimeError(
                            "Gemini returned an empty response."
                        )

                    cleaned_response = (
                        self.clean_json_response(
                            response.text
                        )
                    )

                    try:

                        result = GeneratedFiles.model_validate_json(
                            cleaned_response
                        )

                    except Exception as error:

                        raise RuntimeError(
                            "Gemini returned invalid structured JSON.\n"
                            f"Raw response:\n"
                            f"{response.text}"
                        ) from error

                # -------------------------------------------------
                # Safety:
                # Only selected files can be returned.
                # -------------------------------------------------

                selected = {
                    file_name.lower()
                    for file_name in selected_files
                }

                if "java" not in selected:

                    result.java = None

                if "python" not in selected:

                    result.python = None

                if "readme.md" not in selected:

                    result.readme = None

                print(
                    "✅ Gemini regeneration succeeded."
                )

                return result

            except Exception as error:

                last_error = error

                print(
                    f"❌ Regeneration attempt "
                    f"{attempt} failed:"
                )

                print(
                    f"   {error}"
                )

                if not self.is_retryable_error(
                    error
                ):

                    raise RuntimeError(
                        f"Gemini regeneration failed: "
                        f"{error}"
                    ) from error

                if attempt >= self.MAX_RETRIES:

                    break

                delay = (
                    self.BASE_DELAY
                    * (2 ** (attempt - 1))
                )

                jitter = random.uniform(
                    0,
                    1.5,
                )

                total_delay = (
                    delay
                    + jitter
                )

                print(
                    "⏳ Temporary Gemini error."
                )

                print(
                    f"   Retrying in "
                    f"{total_delay:.1f} seconds..."
                )

                await asyncio.sleep(
                    total_delay
                )

        raise RuntimeError(
            "Gemini regeneration failed after "
            f"{self.MAX_RETRIES} attempts: "
            f"{last_error}"
        )