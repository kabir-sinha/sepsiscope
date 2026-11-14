#!/bin/zsh
# Independent full-history privacy scan (second check next to `sepsiscope privacy-audit`).
# Prints counts only, never the matched values. Usage: zsh scripts/independent_scan.sh .
# Any git error stops the scan with exit code 2: a failed search must never look like "0 hits".
set -eu
set -o pipefail
cd "$1" || { echo "ERROR: cannot enter $1" >&2; exit 2; }
git rev-parse --git-dir >/dev/null 2>&1 || { echo "ERROR: not a git repository" >&2; exit 2; }
user=$(id -un); host=$(hostname -s); home="$HOME"
# One array element per commit. zsh does not split "$(...)" on newlines by itself, so
# ${(f)...} splits it explicitly (without it, git grep got one 114-line argument and failed).
all=(${(f)"$(git rev-list --all)"})
(( ${#all} > 0 )) || { echo "ERROR: no commits" >&2; exit 2; }

# git grep exits 0 (found), 1 (nothing found) or >1 (error). Errors stop the scan.
gg() {
  local out rc
  rc=0; out=$(git grep "$@") || rc=$?
  if (( rc > 1 )); then echo "ERROR: git grep failed (exit $rc)" >&2; exit 2; fi
  [[ -n $out ]] && print -r -- "$out"
  return 0
}
count() { grep -c . || true; }
blobs() { gg -I -c -i -F -e "$1" $all -- | count; }
msgs()  { git log --all --format='%B%n%an%n%ae%n%cn%n%ce' | grep -c -i -F -e "$1" || true; }
f=$(gg -I -h -o -E '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' $all -- | { grep -v -E '^222482936\+kabir-sinha@users\.noreply\.github\.com$|@example\.(com|org)$|^noreply@github\.com$|^[^@]+@users\.noreply\.github\.com$' || true; } | sort -u | count)
sec=$(gg -I -c -E '(ghp_|gho_|github_pat_|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY)' $all -- ':!scripts/independent_scan.sh' | count)  # not its own pattern
dat=$(git log --all --name-only --format= | { grep -E '\.(psv|parquet|csv\.gz|zip|db|sqlite|journal)$|^data/|^mlruns/|^models/' || true; } | count)
ids=$(gg -I -c -E '\bp[0-9]{6}\b' HEAD -- reports web/src src/sepsiscope/api | count)
# Offsets: "YYYY-MM-DD HH:MM:SS +0000" for both author and committer ([^ ] not \S: BSD grep).
off=$(git log --all --format='%ai|%ci' | { grep -v -E '^[^ ]+ [^ ]+ \+0000\|[^ ]+ [^ ]+ \+0000$' || true; } | count)
# Assignments (not arguments of echo), so a failure stops the scan under set -e.
ub=$(blobs $user); um=$(msgs $user); hb=$(blobs $home); hm=$(msgs $home); sb=$(blobs $host); sm=$(msgs $host)
echo "user $ub/$um home $hb/$hm host $sb/$sm emails $f secrets $sec data-paths $dat patient-IDs $ids non-UTC $off"
echo "identities: $(git log --all --format='%ae|%ce' | sort -u | sed 's/^[0-9]*+/…+/' | tr '\n' ' ')"
