"""
Utility for fetching code from CodeSandbox.
"""
import re
import httpx
from typing import Dict, Optional


async def extract_sandbox_id(sandbox_url: str) -> Optional[str]:
    """
    Extract the sandbox ID from a CodeSandbox URL.

    Supports formats:
    - https://codesandbox.io/s/abc123
    - https://codesandbox.io/p/sandbox/abc123
    - https://abc123.csb.app
    """
    if not sandbox_url:
        return None

    # Pattern for /s/ or /p/sandbox/ URLs
    match = re.search(r'codesandbox\.io/(?:s|p/sandbox)/([a-zA-Z0-9-]+)', sandbox_url)
    if match:
        return match.group(1)

    # Pattern for .csb.app URLs
    match = re.search(r'([a-zA-Z0-9-]+)\.csb\.app', sandbox_url)
    if match:
        return match.group(1)

    # If URL is just the ID
    if re.match(r'^[a-zA-Z0-9-]+$', sandbox_url):
        return sandbox_url

    return None


async def fetch_sandbox_files(sandbox_url: str) -> Optional[Dict[str, str]]:
    """
    Fetch code files from a CodeSandbox sandbox.

    Args:
        sandbox_url: The CodeSandbox URL or sandbox ID

    Returns:
        Dict mapping file paths to file contents, or None if fetch fails
    """
    sandbox_id = await extract_sandbox_id(sandbox_url)
    if not sandbox_id:
        return None

    # CodeSandbox API endpoint
    api_url = f"https://codesandbox.io/api/v1/sandboxes/{sandbox_id}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(api_url)

            if response.status_code != 200:
                print(f"Failed to fetch sandbox {sandbox_id}: {response.status_code}")
                return None

            data = response.json()

            # Extract files from the response
            files = {}
            modules = data.get("data", {}).get("modules", [])
            directories = data.get("data", {}).get("directories", [])

            # Build directory path mapping
            dir_map = {d.get("shortid"): d.get("title", "") for d in directories}

            for module in modules:
                # Get file path
                title = module.get("title", "")
                directory_shortid = module.get("directory_shortid")

                # Build full path
                if directory_shortid and directory_shortid in dir_map:
                    dir_name = dir_map[directory_shortid]
                    file_path = f"/{dir_name}/{title}" if dir_name else f"/{title}"
                else:
                    file_path = f"/{title}"

                # Get file content
                code = module.get("code", "")
                files[file_path] = code

            return files if files else None

    except Exception as e:
        print(f"Error fetching sandbox {sandbox_id}: {e}")
        return None


def format_code_files_for_prompt(files: Dict[str, str]) -> str:
    """
    Format code files for inclusion in LLM prompt.

    Args:
        files: Dict mapping file paths to file contents

    Returns:
        Formatted string representation of all files
    """
    if not files:
        return "No files provided."

    formatted_parts = []

    for file_path, content in files.items():
        # Determine language for syntax highlighting hint
        ext = file_path.split(".")[-1] if "." in file_path else ""
        lang_map = {
            "js": "javascript",
            "jsx": "javascript",
            "ts": "typescript",
            "tsx": "typescript",
            "py": "python",
            "json": "json",
            "html": "html",
            "css": "css",
            "md": "markdown",
        }
        lang = lang_map.get(ext, "")

        formatted_parts.append(f"### File: {file_path}\n```{lang}\n{content}\n```")

    return "\n\n".join(formatted_parts)
