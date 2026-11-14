#!/bin/zsh
# Independent full-history privacy scan (second check next to `sepsiscope privacy-audit`).
# Prints counts only, never the matched values. Usage: zsh scripts/independent_scan.sh .
set -u
cd "$1"
user=$(id -un); host=$(hostname -s); home="$HOME"
all=$(git rev-list --all)
blobs() { git grep -I -c -i -F -e "$1" $all -- 2>/dev/null | wc -l | tr -d ' '; }
msgs()  { git log --all --format='%B%n%an%n%ae%n%cn%n%ce' | grep -c -i -F -e "$1"; }
f=$(git grep -I -h -o -E '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' $all -- 2>/dev/null | grep -v -E '^222482936\+kabir-sinha@users\.noreply\.github\.com$|@example\.(com|org)$|^noreply@github\.com$|^[^@]+@users\.noreply\.github\.com$' | sort -u | wc -l | tr -d ' ')
sec=$(git grep -I -c -E '(ghp_|gho_|github_pat_|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY)' $all -- 2>/dev/null | wc -l | tr -d ' ')
dat=$(git log --all --name-only --format= | grep -c -E '\.(psv|parquet|csv\.gz|zip|db|sqlite|journal)$|^data/|^mlruns/|^models/')
ids=$(git grep -I -c -E '\bp[0-9]{6}\b' HEAD -- reports web/src src/sepsiscope/api 2>/dev/null | wc -l | tr -d ' ')
off=$(git log --all --format='%ai|%ci' | grep -v -c -E '^\S+ \S+ \+0000\|\S+ \S+ \+0000$')
echo "user $(blobs $user)/$(msgs $user) home $(blobs $home)/$(msgs $home) host $(blobs $host)/$(msgs $host) emails $f secrets $sec data-paths $dat patient-IDs $ids non-UTC $off"
echo "identities: $(git log --all --format='%ae|%ce' | sort -u | sed 's/^[0-9]*+/…+/' | tr '\n' ' ')"
