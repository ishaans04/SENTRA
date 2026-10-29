#!/usr/bin/env bash
# Publishes the current commit to a Hugging Face Space (Docker SDK).
#
# A Space reads its settings from the front matter of its own README.md, and it
# refuses binary files that are not stored with Xet. So the Space gets a
# one-commit snapshot of this repository: the README.md beside this script
# replaces the GitHub one, and the images used only on GitHub are left out.
#
# Usage:  deploy/huggingface/publish.sh <hf-user>/<space-name>
# Git asks for your Hugging Face user name and a write token.

set -euo pipefail

space="${1:?usage: deploy/huggingface/publish.sh <hf-user>/<space-name>}"
root="$(git rev-parse --show-toplevel)"
snap="$(mktemp -d)"
trap 'rm -rf "$snap"' EXIT

git -C "$root" archive HEAD | tar -x -C "$snap"
cp "$root/deploy/huggingface/README.md" "$snap/README.md"
rm -rf "$snap/docs/media" "$snap/apps/console/public/social-preview.png"

cd "$snap"
git init -q -b main
git add -A
git -c user.name="$(git -C "$root" config user.name)" \
    -c user.email="$(git -C "$root" config user.email)" \
    commit -q -m "SENTRA $(git -C "$root" rev-parse --short HEAD)"
git push --force "https://huggingface.co/spaces/$space" main
