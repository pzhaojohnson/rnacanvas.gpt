#!/usr/bin/env python3

import os
import requests
from pathlib import Path

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

HEADERS = {"Accept": "application/vnd.github+json"}

if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

REPOSITORY_PREFIX = "pzhaojohnson/rnacanvas."

IGNORED_REPOSITORIES = {
    "pzhaojohnson/rnacanvas",
}

OUTPUT_ROOT = Path("rnacanvas-repositories")
KNOWLEDGE_FILE = Path("rnacanvas-knowledge.md")


def github_get_json(url, params=None):
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    return response.json()


def github_get_text(url):
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.text


def repository_matches(full_name):
    return full_name.startswith(REPOSITORY_PREFIX)


def search_rnacanvas_repositories():
    url = "https://api.github.com/search/repositories"
    query = "rnacanvas in:name archived:false"

    repos = []
    page = 1

    while True:
        data = github_get_json(url, params={
            "q": query,
            "per_page": 100,
            "page": page,
        })

        items = data.get("items", [])
        if not items:
            break

        for item in items:
            full_name = item["full_name"]

            if not repository_matches(full_name):
                continue

            if full_name in IGNORED_REPOSITORIES:
                print(f"Ignoring repository: {full_name}")
                continue

            repos.append(full_name)

        page += 1

    return sorted(set(repos))


def get_default_branch(repo_full_name):
    repo = github_get_json(f"https://api.github.com/repos/{repo_full_name}")
    return repo["default_branch"]


def get_recursive_tree(repo_full_name, branch):
    tree = github_get_json(
        f"https://api.github.com/repos/{repo_full_name}/git/trees/{branch}",
        params={"recursive": "1"},
    )

    if tree.get("truncated"):
        print(f"Warning: tree for {repo_full_name} was truncated")

    return tree["tree"]


def is_wanted_file(path):
    lower = path.lower()

    is_readme = lower == "readme.md"

    is_typescript_src_file = (
        path.startswith("src/")
        and (path.endswith(".ts") or path.endswith(".tsx"))
        and not path.endswith(".d.ts")
    )

    is_javascript_test_file = path.endswith("test.js")

    return is_readme or is_typescript_src_file or is_javascript_test_file


def raw_github_url(repo_full_name, branch, path):
    return f"https://raw.githubusercontent.com/{repo_full_name}/{branch}/{path}"


def download_file(repo_full_name, branch, path):
    url = raw_github_url(repo_full_name, branch, path)
    text = github_get_text(url)

    output_path = OUTPUT_ROOT / repo_full_name / path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")

    return {
        "repo": repo_full_name,
        "branch": branch,
        "path": path,
        "text": text,
        "local_path": output_path,
    }


def download_repository_files(repo_full_name):
    print(f"\nRepository: {repo_full_name}")

    branch = get_default_branch(repo_full_name)
    tree = get_recursive_tree(repo_full_name, branch)

    wanted_paths = [
        item["path"]
        for item in tree
        if item.get("type") == "blob" and is_wanted_file(item["path"])
    ]

    print(f"Found {len(wanted_paths)} wanted files")

    downloaded = []

    for path in sorted(wanted_paths):
        record = download_file(repo_full_name, branch, path)
        downloaded.append(record)
        print(f"  Downloaded: {path}")

    return downloaded


def markdown_language_for(path):
    if path.endswith(".tsx"):
        return "tsx"
    if path.endswith(".ts"):
        return "ts"
    if path.endswith(".js"):
        return "js"
    if path.lower().endswith(".md"):
        return "md"

    return ""


def fence_for_content(text):
    return "````" if "```" in text else "```"


def compile_knowledge_file(records):
    lines = []

    lines.append("# RNAcanvas Source Code Knowledge")
    lines.append("")
    lines.append(
        "This file contains README files, TypeScript source files, "
        "and JavaScript test files from non-archived GitHub repositories "
        "whose full repository names begin with `pzhaojohnson/rnacanvas.`."
    )
    lines.append("")

    repos = sorted(set(record["repo"] for record in records))

    lines.append("## Included repositories")
    lines.append("")

    for repo in repos:
        lines.append(f"- `{repo}`")

    lines.append("")
    lines.append("---")
    lines.append("")

    for repo in repos:
        repo_records = [record for record in records if record["repo"] == repo]

        lines.append(f"# Repository: `{repo}`")
        lines.append("")

        for record in sorted(repo_records, key=lambda r: r["path"]):
            path = record["path"]
            text = record["text"]

            language = markdown_language_for(path)
            fence = fence_for_content(text)

            lines.append(f"## File: `{path}`")
            lines.append("")
            lines.append(f"Repository: `{record['repo']}`")
            lines.append(f"Branch: `{record['branch']}`")
            lines.append(f"Path: `{path}`")
            lines.append("")
            lines.append(f"{fence}{language}")
            lines.append(text.rstrip())
            lines.append(fence)
            lines.append("")
            lines.append("---")
            lines.append("")

    KNOWLEDGE_FILE.write_text("\n".join(lines), encoding="utf-8")


def main():
    repos = search_rnacanvas_repositories()

    print(f"Found {len(repos)} matching repositories:")

    for repo in repos:
        print(f"  {repo}")

    all_records = []

    for repo in repos:
        records = download_repository_files(repo)
        all_records.extend(records)

    compile_knowledge_file(all_records)

    print(f"\nDownloaded {len(all_records)} files total.")
    print(f"Downloaded files saved to: {OUTPUT_ROOT.resolve()}")
    print(f"Compiled Knowledge file saved to: {KNOWLEDGE_FILE.resolve()}")


if __name__ == "__main__":
    main()
