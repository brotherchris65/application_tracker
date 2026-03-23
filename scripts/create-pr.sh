#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 \"PR title\" [--base main] [--body \"text\"] [--fill]"
}

if ! command -v gh >/dev/null 2>&1; then
  echo "Error: gh is not installed."
  exit 1
fi

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

title="$1"
shift

base="main"
body=""
fill=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)
      base="$2"
      shift 2
      ;;
    --body)
      body="$2"
      shift 2
      ;;
    --fill)
      fill=true
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${GH_TOKEN:-}" && -z "${GITHUB_TOKEN:-}" ]]; then
  if ! gh auth status >/dev/null 2>&1; then
    echo "Error: no GitHub auth detected."
    echo "Run: gh auth login"
    echo "Or set: export GH_TOKEN=<github_pat>"
    exit 1
  fi
fi

branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$branch" == "main" || "$branch" == "master" ]]; then
  echo "Error: current branch is '$branch'. Create a feature branch first."
  exit 1
fi

cmd=(gh pr create --base "$base" --head "$branch" --title "$title")
if [[ -n "$body" ]]; then
  cmd+=(--body "$body")
elif [[ "$fill" == true ]]; then
  cmd+=(--fill)
else
  cmd+=(--body "")
fi

"${cmd[@]}"
