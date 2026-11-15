#!/bin/zsh
# One full pass of the 11-item privacy scan (the pre-push gate). Counts and repository-
# relative paths only; personal values are read at run time from the gitignored
# `.privacy-denylist.local` and masked in the output. Each scanner writes its log first, so
# every rc below is the scanner's own exit code (never a pipe's). Exit 1 if any scanner
# fails. Usage, from the repository's top folder: zsh scripts/privacy_pass.sh
set -u
set -o pipefail
export TZ=UTC
cd "${0:A:h:h}" || exit 2
DENY=.privacy-denylist.local
[[ -f $DENY ]] || { echo "ERROR: $DENY missing (the scan needs the local denylist)" >&2; exit 2; }
L=$(mktemp -d "${TMPDIR:-/tmp}/privacy_pass.XXXXXX")
fails=0
run() {  # run NAME CMD...: log to $L/NAME.log, record a failing exit code
  local name=$1; shift
  "$@" >$L/$name.log 2>&1; local rc=$?
  (( rc != 0 )) && fails=$((fails + 1))
  return $rc
}
# Masking: the handle (from the allowed noreply address) and every denylist value.
HANDLE=$(uv run python -c "from sepsiscope.audit.denylist import ALLOWED_EMAIL as e; print(e.split('+', 1)[1].split('@')[0])")
MASK=$(uv run python -I - "$DENY" "$HANDLE" <<'PY'
import re, sys
vals = [l.split("#", 1)[0].strip() for l in open(sys.argv[1], encoding="utf-8")]
vals = [v.split(":", 1)[1].strip() if v.lower().startswith("allow-author-name:") else v for v in vals]
vals = sorted({v for v in vals + [sys.argv[2]] if v}, key=len, reverse=True)
print(";".join(f"s/{re.escape(v)}/<masked>/gI" for v in vals))
PY
)
mask() { sed -E "$MASK" | sed -E 's#/'Users'/[^/ ]+#/'Users'/****#g; s/[0-9]{6,}\+/<id>+/g'; }
H='/''Users/'; OFF='+05''30'

run audit uv run sepsiscope privacy-audit; rc=$?; echo "[1/2] privacy-audit rc=$rc $(tail -n 1 $L/audit.log)"
run indep zsh scripts/independent_scan.sh .; rc=$?; echo "[1/2] independent_scan rc=$rc $(head -n 1 $L/indep.log)"
# Every count of the independent scan must be zero ("0" or "0/0"); any other value fails.
nonzero=$(head -n 1 $L/indep.log | awk '{for (i = 2; i <= NF; i += 2) if ($i != "0" && $i != "0/0") n++} END {print n + 0}')
(( nonzero > 0 )) && { echo "    independent_scan: $nonzero non-zero counts"; fails=$((fails + 1)); }
for r in --all origin/main..HEAD; do
  run gitleaks gitleaks git --no-banner --redact --log-opts="$r" .; rc=$?
  echo "[2] gitleaks $r rc=$rc $(tail -n 1 $L/gitleaks.log | sed -E 's/\x1b\[[0-9;]*m//g; s/^.* INF //')"
done
run deep uv run python -I scripts/deep_scan.py . $DENY; rc=$?; echo "[1] deep_scan rc=$rc"
sed -E 's/^(  [^:]+): ([0-9]+) paths: (.*)/  \1 [\2]: \3/' $L/deep.log | mask

uv run python -I - "$DENY" "$HANDLE" > $L/names.log <<'PY'
import re, subprocess, sys
vals = [l.split("#", 1)[0].strip() for l in open(sys.argv[1], encoding="utf-8")]
names = [v for v in vals if v and not v.lower().startswith("allow-author-name:")]
allow = [v.split(":", 1)[1].strip() for v in vals if v.lower().startswith("allow-author-name:")]
handle = sys.argv[2].lower()
# ADR 0025: the exact "Built by <first name>" text is allowed in web/src/App.tsx only.
attr = [re.compile(r"(?<!\w)" + re.escape("Built by " + a.split()[0]) + r"(?![\w-])(?![ \t]+\w)") for a in allow if a]
def strip(line):
    if line.split(":", 2)[0] != "HEAD" or line.split(":", 3)[1] != "web/src/App.tsx":
        return line
    for p in attr:
        line = p.sub(" ", line)
    return line
def grep(pattern_args):
    r = subprocess.run(["git", "grep", "-n", "-I", "-i", *pattern_args, "HEAD", "--"], capture_output=True, text=True)
    if r.returncode > 1:
        sys.exit("git grep failed")
    return r.stdout.splitlines()
lines = grep([a for v in names for a in ("-e", v)]) if names else []
outside = [l for l in lines if any(v.lower() in strip(l).lower().replace(handle, "") for v in names)]
handle_lines = grep(["-F", "-e", handle])
allowed = (f"github.com/{handle}/sepsiscope", f"+{handle}@users.noreply.github.com", f"\\+{handle}@users\\.noreply")
bad_handle = [l for l in handle_lines if not any(a in l.lower() for a in allowed)]
print(f"[1] denylist values in tracked files at HEAD (outside the handle): {len(outside)}")
print(f"[1] handle at HEAD outside the clone URL / noreply address: {len(bad_handle)}")
for l in outside + bad_handle:
    print("    " + l.split(":", 2)[0] + ":" + l.split(":", 2)[1])
PY
rc=$?; (( rc != 0 )) && fails=$((fails + 1)); echo "names rc=$rc" >> $L/names.log; mask < $L/names.log
grep -q -E '(HEAD|address): [1-9]' $L/names.log && fails=$((fails + 1))

FULL=$(grep -v -E '^\s*(#|$)|^allow-author-name:' $DENY | head -n 1 | cut -d'#' -f1 | xargs)
U=(${(f)"$(git rev-list origin/main..HEAD)"})
if (( ${#U} > 0 )); then
  echo "[2] unpushed: offset-literal $(git grep -F -c -e "$OFF" $U -- | wc -l | tr -d ' ') full-name-blobs $(git grep -F -i -c -e "$FULL" $U -- | wc -l | tr -d ' ') full-name-meta $(git log origin/main..HEAD --format='%an%n%cn%n%B' | grep -c -i -F -e "$FULL")"
  echo "[3] unpushed ${#U}: $(git log origin/main..HEAD --format='%an|%cn|%ae|%ce|%ai|%ci' | sed -E 's/^[^|]+\|[^|]+/<n>|<n>/; s/[0-9]+\+[^@]+@/<id>@/g; s/\|20[0-9: -]+ (\+[0-9]{4})/|\1/g' | sort | uniq -c | tr -s ' ')"
  echo "[3] distinct author+committer names: $(git log origin/main..HEAD --format='%an%n%cn' | sort -u | wc -l | tr -d ' ') (expect 1, the allowed name)"
else
  echo "[2]/[3] no unpushed commits"
fi
echo "[4] refs: $(git for-each-ref --format='%(refname)' | tr '\n' ' ') notes: $(git notes list 2>/dev/null | wc -l | tr -d ' ')"
echo "[5] npm hosts: $(grep -o '"resolved": "https\?://[^/]*' web/package-lock.json | sort -u | sed 's#.*//##' | tr '\n' ' ') auth: $(grep -c -i -E '_auth|authToken' web/package-lock.json); uv.lock local paths: $(grep -c -E "file://|$H|/home/" uv.lock)"
echo "[6] CI changed vs GitHub: $(git diff --stat origin/main..HEAD -- .github/workflows | wc -l | tr -d ' ') lines; permissions: $(grep -A1 '^permissions:' .github/workflows/ci.yml | tail -n 1 | xargs); unpinned actions: $(grep -E 'uses:' .github/workflows/ci.yml | grep -v -c -E '@[0-9a-f]{40}'); secrets refs: $(grep -c 'secrets\.' .github/workflows/ci.yml)"
if [[ -d web/dist/assets ]]; then
  echo "[7] web/dist: maps $(find web/dist -name '*.map' | wc -l | tr -d ' ') sourceMappingURL $(grep -l sourceMappingURL web/dist/assets/* | wc -l | tr -d ' ') patient-IDs $(grep -o -E '\bp[01][0-9]{5}\b' web/dist/assets/* | wc -l | tr -d ' ') home-paths $(cat web/dist/assets/* | grep -c -E "$H|/home/")"
else
  echo "[7] web/dist not built"; fails=$((fails + 1))
fi
ign=""; for p in mlruns/mlflow.db mlruns/tuning/lgbm_A2B.journal data/demo/demo_B2A.json models/lgbm_B2A/model.txt data/processed/deferral/deferral_A2B.parquet; do git check-ignore -q $p && ign+=y || ign+=N; done
guard=$(uv run python -c "
from sepsiscope.audit.rules import check_path
print(''.join('y' if check_path(p) else 'N' for p in ['mlruns/mlflow.db','mlruns/tuning/lgbm_A2B.journal','data/demo/demo_B2A.json','models/lgbm_B2A/model.txt','data/processed/deferral/deferral_A2B.parquet']))")
echo "[8] ignored: $ign (expect yyyyy) guard blocks: $guard (expect yyyyy) reports/: patient-IDs $(git grep -c -E '\bp[01][0-9]{5}\b' HEAD -- reports | wc -l | tr -d ' ') home-paths $(git grep -c -e "$H" -e '/home/' HEAD -- reports | wc -l | tr -d ' ')"
[[ $ign == yyyyy && $guard == yyyyy ]] || fails=$((fails + 1))
run probe uv run python scripts/api_probe.py; rc=$?; echo "$(grep '^\[9\]' $L/probe.log) rc=$rc"
echo "[10] device / OS / plan / wifi / location hits (deep_scan, all sections): $(grep -c -E '^  (device|os-version|plan-names|wifi|location/tz):' $L/deep.log)"
grep -q -E '^  (device|os-version|plan-names|wifi|location/tz):' $L/deep.log && fails=$((fails + 1))
echo "[11] $(for f in CLAUDE.local.md .claude/settings.local.json .privacy-denylist.local .env .env.local; do printf '%s tracked=%s ignored=%s history=%s; ' $f $(git ls-files -- $f | wc -l | tr -d ' ') $(git check-ignore -q $f && echo y || echo n) $(git log --all --oneline -- $f | wc -l | tr -d ' '); done)"
echo "=== failing checks: $fails"
rm -f $L/*.log && rmdir $L
exit $(( fails > 0 ))
