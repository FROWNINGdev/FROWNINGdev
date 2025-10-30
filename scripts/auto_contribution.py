#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime

import requests


def load_dotenv_if_present() -> None:
    """Load .env file (KEY=VALUE per line) without extra dependencies.
    Existing environment variables are not overridden.
    """
    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and (key not in os.environ):
                    os.environ[key] = val
    except Exception:
        # Silent fallback: rely on real env
        pass


def run_command(command: list[str], cwd: str | None = None, check: bool = True) -> str:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, command, result.stdout, result.stderr)
    return (result.stdout or "").strip()


def get_default_branch(repo_path: str) -> str:
    try:
        out = run_command(["git", "remote", "show", "origin"], cwd=repo_path)
        for line in out.splitlines():
            if "HEAD branch:" in line:
                return line.split("HEAD branch:", 1)[1].strip()
    except Exception:
        pass
    return run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)


def get_repo_owner_name(repo_path: str) -> str | None:
    remote_url = run_command(["git", "config", "--get", "remote.origin.url"], cwd=repo_path, check=False)
    if "github.com" in remote_url:
        parts = remote_url.rstrip(".git").split("/")
        owner = parts[-2]
        name = parts[-1]
        return f"{owner}/{name}"
    return None


def create_pull_request(repo_full_name: str, token: str, base: str, head: str, title: str, body: str) -> dict:
    url = f"https://api.github.com/repos/{repo_full_name}/pulls"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    data = {"title": title, "body": body, "head": head, "base": base}
    r = requests.post(url, headers=headers, data=json.dumps(data))
    r.raise_for_status()
    return r.json()


def merge_pull_request(repo_full_name: str, token: str, pr_number: int) -> dict:
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/merge"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    data = {"commit_title": "chore: auto-merge for Pull Shark", "merge_method": "squash"}
    r = requests.put(url, headers=headers, data=json.dumps(data))
    r.raise_for_status()
    return r.json()


def main() -> None:
    load_dotenv_if_present()

    parser = argparse.ArgumentParser(description="Automate PRs for Pull Shark badge")
    parser.add_argument("--repos", type=str, help="Comma-separated list like owner/repo1,owner/repo2. Defaults to current repo.")
    parser.add_argument("--base", type=str, default=None, help="Base branch (defaults to repo default)")
    parser.add_argument("--auto-merge", action="store_true", help="Auto-merge created PRs")
    args = parser.parse_args()

    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        print("Error: set GH_TOKEN in .env or environment.")
        return

    if args.repos:
        repos_to_process = [r.strip() for r in args.repos.split(",") if r.strip()]
    else:
        current_repo = get_repo_owner_name(".")
        if not current_repo:
            print("Error: cannot determine current repository; pass --repos owner/name")
            return
        repos_to_process = [current_repo]

    for repo_full_name in repos_to_process:
        print(f"\n--- Processing {repo_full_name} ---")
        is_current = get_repo_owner_name(".") == repo_full_name
        cwd = "." if is_current else repo_full_name.split("/")[-1]

        if not is_current:
            if os.path.isdir(cwd):
                run_command(["git", "pull"], cwd=cwd, check=False)
            else:
                run_command(["git", "clone", f"https://github.com/{repo_full_name}.git", cwd])

        base_branch = args.base or get_default_branch(cwd)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        branch_name = f"feat/pull-shark-{timestamp}"
        commit_message = f"chore(pull-shark): automated change {timestamp}"
        pr_title = f"Automated PR for Pull Shark: {timestamp}"
        pr_body = "Automated housekeeping change to increment Pull Shark badge."

        run_command(["git", "checkout", base_branch], cwd=cwd)
        run_command(["git", "checkout", "-b", branch_name], cwd=cwd)

        dummy_dir = os.path.join(cwd, ".github")
        os.makedirs(dummy_dir, exist_ok=True)
        dummy_file = os.path.join(dummy_dir, f"pull_shark_{timestamp}.md")
        with open(dummy_file, "w", encoding="utf-8") as f:
            f.write(f"Pull Shark tick: {timestamp}\n")

        run_command(["git", "add", dummy_file], cwd=cwd)
        run_command(["git", "commit", "-m", commit_message], cwd=cwd)
        run_command(["git", "push", "origin", branch_name], cwd=cwd)

        try:
            pr = create_pull_request(repo_full_name, token, base_branch, branch_name, pr_title, pr_body)
            pr_number = pr["number"]
            print(f"Created PR #{pr_number}: {pr.get('html_url')}")
            if args.auto_merge:
                merged = merge_pull_request(repo_full_name, token, pr_number)
                print(f"Merged: {merged.get('merged')}")
        except requests.HTTPError as e:
            print(f"GitHub API error: {e} - {getattr(e.response, 'text', '')}")
        except Exception as e:
            print(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()


