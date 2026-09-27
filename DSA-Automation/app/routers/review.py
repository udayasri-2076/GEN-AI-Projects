import base64
import html
import json
import os
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.draft import Draft
from app.services.ai_generation_service import AIGenerationService
from app.services.github_service import GitHubService


router = APIRouter(
    prefix="/review",
    tags=["Draft Review"],
)


# =========================================================
# DATABASE
# =========================================================

def get_db():
    """
    Provide a database session.
    """

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# =========================================================
# TEMPORARY REFERENCE IMAGE STORAGE
# =========================================================

def save_reference_images(
    draft_id: int,
    reference_images_data: list[str],
) -> list[str]:
    """
    Save screenshots pasted directly from the clipboard.

    The browser sends each pasted image as a data URL.
    These files are temporary and are NOT stored in PostgreSQL.

    Gemini image understanding will use these files in the
    next AI-integration step.
    """

    if not reference_images_data:
        return []

    base_dir = (
        Path("temp")
        / "reference_images"
        / f"draft_{draft_id}"
    )

    base_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    allowed_types = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }

    max_images = 10
    max_size = 5 * 1024 * 1024
    saved_paths = []

    for index, data_url in enumerate(
        reference_images_data[:max_images],
        start=1,
    ):

        if not data_url or "," not in data_url:
            continue

        header, encoded = data_url.split(",", 1)

        match = re.match(
            r"data:(image/[^;]+);base64",
            header,
            flags=re.IGNORECASE,
        )

        if not match:
            raise HTTPException(
                status_code=400,
                detail="Reference image data is invalid.",
            )

        content_type = match.group(1).lower()

        if content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported reference image type: {content_type}. "
                    "Use PNG, JPEG, WEBP, or GIF."
                ),
            )

        try:
            image_bytes = base64.b64decode(
                encoded,
                validate=True,
            )
        except Exception as error:
            raise HTTPException(
                status_code=400,
                detail="Reference image could not be decoded.",
            ) from error

        if len(image_bytes) > max_size:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Reference image {index} is larger than 5 MB."
                ),
            )

        file_path = (
            base_dir
            / f"reference_{index}{allowed_types[content_type]}"
        )

        file_path.write_bytes(
            image_bytes
        )

        saved_paths.append(
            str(file_path)
        )

    return saved_paths


# =========================================================
# HELPER: FILE NAME
# =========================================================

def make_file_name(
    title: str,
    extension: str,
) -> str:
    """
    Convert the official problem title into the user's
    underscore-style file name.

    Example:
        Search in Rotated Sorted Array
        -> Search_in_Rotated_Sorted_Array.java
    """

    safe_title = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        title,
    ).strip("_")

    return f"{safe_title}.{extension}"


# =========================================================
# REVIEW PAGE
# =========================================================

# =========================================================
# REVIEW DASHBOARD
# =========================================================

@router.get(
    "",
    response_class=HTMLResponse,
)
async def review_dashboard(
    db: Session = Depends(get_db),
):
    """
    Show all AI drafts in one dashboard.

    The user can open any draft for detailed review and approval.
    """

    drafts = (
        db.query(Draft)
        .order_by(Draft.id.desc())
        .all()
    )

    def escape(value):
        return html.escape(
            str(value or "")
        )

    total = len(drafts)
    committed = sum(
        1
        for draft in drafts
        if draft.status == "committed"
    )
    pending = sum(
        1
        for draft in drafts
        if draft.status != "committed"
    )

    rows = []

    for draft in drafts:

        status_class = (
            "status-committed"
            if draft.status == "committed"
            else "status-pending"
        )

        rows.append(
            f"""
            <tr>
                <td>{draft.id}</td>
                <td>
                    <strong>
                        {draft.problem_number}. {escape(draft.problem_title)}
                    </strong>
                </td>
                <td>{escape(draft.topic)}</td>
                <td>{escape(draft.pattern or "None")}</td>
                <td>
                    <span class="status {status_class}">
                        {escape(draft.status)}
                    </span>
                </td>
                <td>
                    <a
                        class="review-button"
                        href="/review/{draft.id}"
                    >
                        Review →
                    </a>
                </td>
            </tr>
            """
        )

    table_rows = "".join(rows)

    if not table_rows:
        table_rows = """
        <tr>
            <td colspan="6" class="empty">
                No drafts found.
            </td>
        </tr>
        """

    page = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>DSA Draft Review Dashboard</title>

        <style>
            * {{
                box-sizing: border-box;
            }}

            body {{
                font-family: Arial, sans-serif;
                background: #f4f4f4;
                margin: 0;
                padding: 30px;
                color: #111;
            }}

            .container {{
                max-width: 1500px;
                margin: auto;
            }}

            h1 {{
                margin-bottom: 8px;
            }}

            .subtitle {{
                color: #666;
                margin-bottom: 25px;
            }}

            .stats {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 16px;
                margin-bottom: 24px;
            }}

            .stat-card {{
                background: white;
                padding: 20px;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            }}

            .stat-number {{
                font-size: 30px;
                font-weight: bold;
            }}

            .stat-label {{
                margin-top: 6px;
                color: #666;
            }}

            .card {{
                background: white;
                padding: 24px;
                border-radius: 12px;
                overflow-x: auto;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                min-width: 850px;
            }}

            th,
            td {{
                padding: 14px 12px;
                border-bottom: 1px solid #e5e5e5;
                text-align: left;
                vertical-align: middle;
            }}

            th {{
                background: #fafafa;
            }}

            .status {{
                display: inline-block;
                padding: 6px 10px;
                border-radius: 999px;
                font-size: 13px;
                font-weight: bold;
            }}

            .status-committed {{
                background: #d1e7dd;
                color: #0f5132;
            }}

            .status-pending {{
                background: #fff3cd;
                color: #664d03;
            }}

            .review-button {{
                display: inline-block;
                padding: 9px 14px;
                border-radius: 8px;
                background: #111;
                color: white;
                text-decoration: none;
            }}

            .review-button:hover {{
                background: #333;
            }}

            .empty {{
                text-align: center;
                color: #666;
                padding: 35px;
            }}

            @media (max-width: 700px) {{
                body {{
                    padding: 15px;
                }}

                .stats {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>

    <body>
        <div class="container">

            <h1>📝 DSA Draft Review Dashboard</h1>

            <div class="subtitle">
                Review generated DSA files before committing them to GitHub.
            </div>

            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{total}</div>
                    <div class="stat-label">Total Drafts</div>
                </div>

                <div class="stat-card">
                    <div class="stat-number">{pending}</div>
                    <div class="stat-label">Pending Review</div>
                </div>

                <div class="stat-card">
                    <div class="stat-number">{committed}</div>
                    <div class="stat-label">Committed</div>
                </div>
            </div>

            <div class="card">
                <table>
                    <thead>
                        <tr>
                            <th>Draft ID</th>
                            <th>Problem</th>
                            <th>Topic</th>
                            <th>Pattern</th>
                            <th>Status</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
            </div>

        </div>
    </body>
    </html>
    """

    return HTMLResponse(
        content=page
    )


@router.get(
    "/{draft_id}",
    response_class=HTMLResponse,
)
async def review_draft(
    draft_id: int,
    db: Session = Depends(get_db),
):
    """
    Display an AI draft for user review.

    The user can:
    - read Java/Python/README
    - paste screenshots directly with Ctrl+V
    - write feedback
    - select specific files to regenerate
    - approve the final draft
    """

    draft = db.get(
        Draft,
        draft_id,
    )

    if not draft:
        raise HTTPException(
            status_code=404,
            detail="Draft not found",
        )

    def escape(value):
        return html.escape(
            value or ""
        )

    java = escape(
        draft.java_content
    )

    python = escape(
        draft.python_content
    )

    readme = escape(
        draft.readme_content
    )

    title = escape(
        draft.problem_title
    )

    topic = escape(
        draft.topic
    )

    pattern = escape(
        draft.pattern or "None"
    )

    destination = escape(
        draft.destination or "Pending"
    )

    status = escape(
        draft.status
    )

    if draft.status == "committed":

        github_message = """
            <div class="approved">
                <strong>✅ Draft committed to GitHub.</strong>
                <br>
                The approved files were written to the DSA repository.
            </div>
        """

        approve_section = """
            <div class="card">
                <h2>✅ GitHub Commit Complete</h2>
                <p>
                    This draft has already been committed to the DSA repository.
                </p>
            </div>
        """

    else:

        github_message = """
            <div class="warning">
                <strong>⚠️ GitHub is not modified until approval.</strong>
                <br>
                Review the generated files before approving.
            </div>
        """

        approve_section = f"""
            <div class="card approve-card">
                <h2>✅ Approve Draft</h2>

                <p>
                    Approval will write the generated files to the DSA GitHub repository.
                </p>

                <form
                    method="post"
                    action="/review/{draft.id}/approve"
                >
                    <button class="approve-button" type="submit">
                        ✅ Approve &amp; Commit to GitHub
                    </button>
                </form>
            </div>
        """

    page = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">

        <title>DSA Draft Review</title>

        <style>
            * {{
                box-sizing: border-box;
            }}

            body {{
                font-family: Arial, sans-serif;
                background: #f4f4f4;
                margin: 0;
                padding: 30px;
                color: #111;
            }}

            .container {{
                max-width: 1500px;
                margin: auto;
            }}

            .card {{
                background: white;
                padding: 24px;
                margin-bottom: 24px;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            }}

            h1, h2, h3 {{
                margin-top: 0;
            }}

            .meta {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
                gap: 10px 24px;
            }}

            .meta p {{
                margin: 8px 0;
            }}

            .warning {{
                background: #fff3cd;
                padding: 15px;
                border-radius: 8px;
                margin-top: 20px;
            }}

            .approved {{
                background: #d1e7dd;
                padding: 15px;
                border-radius: 8px;
                margin-top: 20px;
            }}

            .code-title {{
                display: flex;
                align-items: center;
                gap: 10px;
            }}

            pre {{
                background: #111;
                color: #eee;
                padding: 20px;
                border-radius: 8px;
                overflow-x: auto;
                white-space: pre-wrap;
                line-height: 1.5;
                font-family: Consolas, monospace;
                font-size: 14px;
            }}

            .paste-area {{
                border: 2px dashed #777;
                border-radius: 12px;
                padding: 24px;
                min-height: 150px;
                background: #fafafa;
                cursor: text;
                transition: border-color 0.2s, background 0.2s;
            }}

            .paste-area:focus {{
                outline: none;
                border-color: #222;
                background: #fff;
            }}

            .paste-area.drag-active {{
                border-color: #111;
                background: #f0f0f0;
            }}

            .paste-placeholder {{
                color: #555;
                text-align: center;
                padding: 25px 10px;
                user-select: none;
            }}

            .preview-area {{
                display: flex;
                flex-wrap: wrap;
                gap: 14px;
                margin-top: 16px;
            }}

            .preview-item {{
                width: 240px;
                background: white;
                border: 1px solid #ccc;
                border-radius: 10px;
                padding: 8px;
            }}

            .preview-item img {{
                width: 100%;
                max-height: 220px;
                object-fit: contain;
                display: block;
                border-radius: 6px;
                background: #eee;
            }}

            .remove-button {{
                width: 100%;
                margin-top: 8px;
                padding: 8px;
                cursor: pointer;
                border: 1px solid #bbb;
                border-radius: 6px;
                background: #fff;
            }}

            .file-choice {{
                display: block;
                margin: 10px 0;
                font-size: 16px;
            }}

            textarea {{
                width: 100%;
                min-height: 150px;
                padding: 12px;
                border: 1px solid #bbb;
                border-radius: 8px;
                font-size: 15px;
                resize: vertical;
                margin-top: 8px;
            }}

            button {{
                padding: 12px 20px;
                margin-top: 15px;
                cursor: pointer;
                border: 0;
                border-radius: 8px;
                font-size: 15px;
            }}

            .regenerate-button {{
                background: #222;
                color: white;
            }}

            .approve-button {{
                background: #146c43;
                color: white;
                font-size: 16px;
                padding: 14px 24px;
            }}

            .hint {{
                color: #555;
                font-size: 14px;
                margin-top: 8px;
            }}

            .selected-count {{
                font-weight: bold;
                margin-top: 10px;
            }}
        </style>
    </head>

    <body>

    <div class="container">

        <div class="card">
            <h1>🤖 DSA Draft Review</h1>

            <div class="meta">
                <p>
                    <strong>Problem:</strong>
                    {draft.problem_number}_{title}
                </p>

                <p>
                    <strong>Topic:</strong>
                    {topic}
                </p>

                <p>
                    <strong>Pattern:</strong>
                    {pattern}
                </p>

                <p>
                    <strong>Destination:</strong>
                    {destination}
                </p>

                <p>
                    <strong>Status:</strong>
                    {status}
                </p>
            </div>

            {github_message}
        </div>


        <div class="card">
            <div class="code-title">
                <h2>☕ Java</h2>
            </div>
            <pre>{java or "Not generated"}</pre>
        </div>


        <div class="card">
            <div class="code-title">
                <h2>🐍 Python</h2>
            </div>
            <pre>{python or "Not generated"}</pre>
        </div>


        <div class="card">
            <div class="code-title">
                <h2>📖 README.md</h2>
            </div>
            <pre>{readme or "Not generated"}</pre>
        </div>


        <div class="card">
            <h2>🔄 Request Changes</h2>

            <form
                id="regenerate-form"
                method="post"
                action="/review/{draft_id}/regenerate"
                enctype="application/x-www-form-urlencoded"
            >

                <h3>📸 Reference Screenshots</h3>

                <p>
                    Use this exactly like ChatGPT:
                    <strong>copy a screenshot → click the box → Ctrl + V</strong>.
                </p>

                <div
                    id="paste-area"
                    class="paste-area"
                    tabindex="0"
                    contenteditable="true"
                    role="textbox"
                    aria-label="Paste reference screenshots here"
                >
                    <div id="paste-placeholder" class="paste-placeholder">
                        📋 Click here and press <strong>Ctrl + V</strong><br>
                        Paste one or multiple screenshots here
                    </div>
                    <div id="preview-area" class="preview-area"></div>
                </div>

                <p class="hint">
                    You do not need to choose a file. Paste screenshots directly.
                    Up to 10 images, 5 MB each.
                </p>

                <input
                    type="hidden"
                    name="reference_images_data"
                    id="reference_images_data"
                    value=""
                >

                <h3>🛠 Files to Regenerate</h3>

                <label class="file-choice">
                    <input
                        type="checkbox"
                        name="files"
                        value="Java"
                    >
                    Regenerate Java
                </label>

                <label class="file-choice">
                    <input
                        type="checkbox"
                        name="files"
                        value="Python"
                    >
                    Regenerate Python
                </label>

                <label class="file-choice">
                    <input
                        type="checkbox"
                        name="files"
                        value="README.md"
                    >
                    Regenerate README
                </label>

                <div id="selected-count" class="selected-count">
                    Selected files: 0
                </div>

                <h3>Your feedback</h3>

                <textarea
                    name="feedback"
                    placeholder="Example: The comments are not like my reference. Keep the actual code once and put the concrete dry-run values beside the same code lines."
                    required
                ></textarea>

                <br>

                <button
                    class="regenerate-button"
                    type="submit"
                >
                    🔄 Regenerate Selected Files
                </button>

            </form>
        </div>


        {approve_section}

    </div>


    <script>
        const pasteArea = document.getElementById("paste-area");
        const previewArea = document.getElementById("preview-area");
        const placeholder = document.getElementById("paste-placeholder");
        const referenceInput = document.getElementById("reference_images_data");
        const selectedCount = document.getElementById("selected-count");
        const regenerateForm = document.getElementById("regenerate-form");

        const pastedImages = [];
        const MAX_IMAGES = 10;
        const MAX_BYTES = 5 * 1024 * 1024;

        function updateReferenceInput() {{
            referenceInput.value = JSON.stringify(pastedImages);
            placeholder.style.display = pastedImages.length ? "none" : "block";
        }}

        function updateSelectedCount() {{
            const checked = regenerateForm.querySelectorAll(
                'input[name="files"]:checked'
            );
            selectedCount.textContent =
                "Selected files: " + checked.length;
        }}

        function addPreview(dataUrl) {{
            const wrapper = document.createElement("div");
            wrapper.className = "preview-item";

            const img = document.createElement("img");
            img.src = dataUrl;
            img.alt = "Reference screenshot";

            const removeButton = document.createElement("button");
            removeButton.type = "button";
            removeButton.className = "remove-button";
            removeButton.textContent = "Remove screenshot";

            removeButton.addEventListener("click", () => {{
                const index = pastedImages.indexOf(dataUrl);

                if (index !== -1) {{
                    pastedImages.splice(index, 1);
                }}

                wrapper.remove();
                updateReferenceInput();
            }});

            wrapper.appendChild(img);
            wrapper.appendChild(removeButton);
            previewArea.appendChild(wrapper);
        }}

        function addImageFile(file) {{
            if (!file) return;

            if (!file.type.startsWith("image/")) return;

            if (pastedImages.length >= MAX_IMAGES) {{
                alert("You can paste up to 10 reference screenshots.");
                return;
            }}

            if (file.size > MAX_BYTES) {{
                alert("Each reference screenshot must be 5 MB or smaller.");
                return;
            }}

            const reader = new FileReader();

            reader.onload = () => {{
                const dataUrl = reader.result;
                pastedImages.push(dataUrl);
                addPreview(dataUrl);
                updateReferenceInput();
            }};

            reader.readAsDataURL(file);
        }}

        pasteArea.addEventListener("paste", (event) => {{
            const items = Array.from(
                event.clipboardData.items
            );

            const imageItems = items.filter(
                item => item.type.startsWith("image/")
            );

            if (!imageItems.length) {{
                return;
            }}

            event.preventDefault();

            imageItems.forEach(item => {{
                addImageFile(item.getAsFile());
            }});
        }});

        pasteArea.addEventListener("dragover", (event) => {{
            event.preventDefault();
            pasteArea.classList.add("drag-active");
        }});

        pasteArea.addEventListener("dragleave", () => {{
            pasteArea.classList.remove("drag-active");
        }});

        pasteArea.addEventListener("drop", (event) => {{
            event.preventDefault();
            pasteArea.classList.remove("drag-active");

            Array.from(event.dataTransfer.files).forEach(
                file => addImageFile(file)
            );
        }});

        regenerateForm.querySelectorAll(
            'input[name="files"]'
        ).forEach(checkbox => {{
            checkbox.addEventListener("change", updateSelectedCount);
        }});

        regenerateForm.addEventListener("submit", (event) => {{
            const selected = regenerateForm.querySelectorAll(
                'input[name="files"]:checked'
            );

            const feedback = regenerateForm.querySelector(
                'textarea[name="feedback"]'
            );

            if (!selected.length) {{
                event.preventDefault();
                alert("Select at least one file to regenerate.");
                return;
            }}

            if (!feedback.value.trim()) {{
                event.preventDefault();
                alert("Please enter feedback.");
                return;
            }}

            updateReferenceInput();
        }});

        updateReferenceInput();
        updateSelectedCount();

        pasteArea.addEventListener("click", () => {{
            pasteArea.focus();
        }});
    </script>

    </body>
    </html>
    """

    return HTMLResponse(
        content=page
    )


# =========================================================
# REGENERATE
# =========================================================

@router.post(
    "/{draft_id}/regenerate"
)
async def regenerate_draft(
    draft_id: int,
    files: list[str] = Form(default=[]),
    feedback: str = Form(default=""),
    reference_images_data: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """
    Regenerate only files selected by the user.

    Reference screenshots are saved temporarily so the AI
    service can use them once multimodal regeneration is connected.
    """

    draft = db.get(
        Draft,
        draft_id,
    )

    if not draft:
        raise HTTPException(
            status_code=404,
            detail="Draft not found",
        )

    allowed_files = {
        "Java",
        "Python",
        "README.md",
    }

    invalid_files = [
        file_name
        for file_name in files
        if file_name not in allowed_files
    ]

    if invalid_files:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid regeneration file selection: "
                + ", ".join(invalid_files)
            ),
        )

    if not files:
        raise HTTPException(
            status_code=400,
            detail="Select at least one file.",
        )

    if not feedback.strip():
        raise HTTPException(
            status_code=400,
            detail="Feedback is required.",
        )

    try:
        reference_images = (
            json.loads(reference_images_data)
            if reference_images_data.strip()
            else []
        )
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=400,
            detail="Reference image data is invalid JSON.",
        ) from error

    if not isinstance(reference_images, list):
        raise HTTPException(
            status_code=400,
            detail="Reference image data must be a list.",
        )

    saved_reference_images = save_reference_images(
        draft_id=draft.id,
        reference_images_data=reference_images,
    )

    if saved_reference_images:
        print()
        print("📸 Reference screenshots saved temporarily:")
        for image_path in saved_reference_images:
            print(f"   → {image_path}")
        print()

    # NOTE:
    # The current AIGenerationService regeneration method still accepts
    # text feedback only. The saved reference images will be connected
    # to Gemini in the next AI-service step.

    ai = AIGenerationService()

    regenerated = await ai.regenerate_files(
        problem_number=draft.problem_number,
        problem_title=draft.problem_title,
        topic=draft.topic,
        pattern=draft.pattern,
        submitted_language=draft.submitted_language,
        submitted_source=draft.source_code,
        feedback=feedback,
        selected_files=files,
        current_java=draft.java_content,
        current_python=draft.python_content,
        current_readme=draft.readme_content,
    )

    if "Java" in files and regenerated.java:
        draft.java_content = regenerated.java

    if "Python" in files and regenerated.python:
        draft.python_content = regenerated.python

    if "README.md" in files and regenerated.readme:
        draft.readme_content = regenerated.readme

    draft.feedback = feedback
    draft.status = "draft"
    draft.updated_at = datetime.utcnow()

    db.commit()

    return RedirectResponse(
        url=f"/review/{draft.id}",
        status_code=303,
    )


# =========================================================
# APPROVE + COMMIT TO GITHUB
# =========================================================

@router.post(
    "/{draft_id}/approve"
)
async def approve_draft(
    draft_id: int,
    db: Session = Depends(get_db),
):
    """
    Approve a draft and commit its generated files to GitHub.

    Existing files are preserved by GitHubService.
    """

    draft = db.get(
        Draft,
        draft_id,
    )

    if not draft:
        raise HTTPException(
            status_code=404,
            detail="Draft not found",
        )

    if draft.status == "committed":
        return RedirectResponse(
            url=f"/review/{draft.id}",
            status_code=303,
        )

    if not draft.destination:
        raise HTTPException(
            status_code=400,
            detail="Draft does not have a valid DSA destination.",
        )

    dsa_repo = os.getenv("DSA_REPO")

    if not dsa_repo:
        raise HTTPException(
            status_code=500,
            detail="DSA_REPO is missing in .env",
        )

    files_to_commit = {}

    if draft.java_content:
        java_name = make_file_name(
            draft.problem_title,
            "java",
        )

        files_to_commit[
            f"{draft.destination}/{java_name}"
        ] = draft.java_content

    if draft.python_content:
        python_name = make_file_name(
            draft.problem_title,
            "py",
        )

        files_to_commit[
            f"{draft.destination}/{python_name}"
        ] = draft.python_content

    if draft.readme_content:
        files_to_commit[
            f"{draft.destination}/README.md"
        ] = draft.readme_content

    if not files_to_commit:
        raise HTTPException(
            status_code=400,
            detail="Draft contains no generated files to commit.",
        )

    github = GitHubService()

    commit_message = (
        f"feat(dsa): add {draft.problem_number} "
        f"{draft.problem_title}"
    )

    try:
        result = await github.write_files_to_repository(
            repo=dsa_repo,
            files=files_to_commit,
            commit_message=commit_message,
            branch="main",
        )
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"GitHub commit failed: {error}",
        ) from error

    if result.get("written"):

        draft.status = "committed"
        draft.updated_at = datetime.utcnow()
        db.commit()

        created_files = result.get(
            "created_files",
            [],
        )

        skipped_files = result.get(
            "skipped_files",
            [],
        )

        created_html = "".join(
            f"<li>{html.escape(path)}</li>"
            for path in created_files
        ) or "<li>None</li>"

        skipped_html = "".join(
            f"<li>{html.escape(path)}</li>"
            for path in skipped_files
        ) or "<li>None</li>"

        page = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>GitHub Commit Complete</title>
        </head>

        <body
            style="
                font-family: Arial;
                padding: 40px;
            "
        >

            <h1>
                ✅ Draft Approved &amp; Committed
            </h1>

            <p>
                Draft #{draft.id} has been written to the DSA repository.
            </p>

            <p>
                <strong>Repository:</strong>
                {html.escape(dsa_repo)}
            </p>

            <p>
                <strong>Destination:</strong>
                {html.escape(draft.destination)}
            </p>

            <p>
                <strong>Commit SHA:</strong>
                {html.escape(result.get("commit_sha") or "Unknown")}
            </p>

            <h3>Created Files</h3>
            <ul>
                {created_html}
            </ul>

            <h3>Skipped Existing Files</h3>
            <ul>
                {skipped_html}
            </ul>

            <p>
                <a href="/review/{draft.id}">
                    ← Back to review
                </a>
            </p>

        </body>
        </html>
        """

        return HTMLResponse(
            content=page
        )

    draft.status = "approved"
    draft.updated_at = datetime.utcnow()
    db.commit()

    page = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Draft Approved</title>
    </head>

    <body
        style="
            font-family: Arial;
            padding: 40px;
        "
    >

        <h1>✅ Draft Approved</h1>

        <p>
            Draft #{draft.id} was approved.
        </p>

        <p>
            GitHub reported that all supplied files already exist,
            so no new commit was created.
        </p>

        <p>
            <a href="/review/{draft.id}">
                ← Back to review
            </a>
        </p>

    </body>
    </html>
    """

    return HTMLResponse(
        content=page
    )
