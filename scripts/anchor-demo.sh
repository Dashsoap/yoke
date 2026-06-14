#!/usr/bin/env bash
# Yoke Anchor — 30-second self-contained demo.
#
# Proves the core promise in one run: a living doc pinned to code auto-flips to
# STALE the moment the code changes, and self-heals when reverted. No deps but
# python3. Runs in an isolated temp dir; touches nothing in your repo.
#
#   bash scripts/anchor-demo.sh
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANCHOR="$HERE/anchor.py"
DEMO="$(mktemp -d)"
trap 'rm -rf "$DEMO"' EXIT

say(){ printf "\n\033[1m%s\033[0m\n" "$*"; }
run(){ printf "\033[2m$ %s\033[0m\n" "$*"; eval "$*"; }

# --- a tiny sample project -------------------------------------------------
mkdir -p "$DEMO/src" "$DEMO/docs/traces"
cat > "$DEMO/src/auth.py" <<'PY'
def make_token(user_id):
    # NOTE: token = sha256 of user_id, first 8 hex chars
    import hashlib
    return hashlib.sha256(str(user_id).encode()).hexdigest()[:8]
PY

say "1) 我们有一段代码，和一条描述它的 learning（文档）。"
run "cat '$DEMO/src/auth.py'"
echo '   learning: "token 是 user_id 的 sha256 前 8 位"'

# --- anchor the doc to the function ----------------------------------------
say "2) 把这条 learning 锚定到 make_token 函数上（符号模式）。"
run "python3 '$ANCHOR' -p '$DEMO' add --doc-kind learning \
  --doc-ref token-is-sha256-first-8 \
  --code-file src/auth.py --symbol-name make_token"

say "3) 现在文档是新鲜的。"
run "python3 '$ANCHOR' -p '$DEMO' report"

# --- harmless edit: insert lines ABOVE the symbol --------------------------
say "4) 先做个无关改动：在文件顶部插入 3 行注释（行号全位移）。"
printf '# file header\n# (c) 2026\n\n%s' "$(cat "$DEMO/src/auth.py")" > "$DEMO/src/auth.py.tmp"
mv "$DEMO/src/auth.py.tmp" "$DEMO/src/auth.py"
run "python3 '$ANCHOR' -p '$DEMO' scan"
echo "   → 仍 FRESH。符号模式按名字重新定位，不被行号位移骗到（旧的行号模式这里会误报）。"

# --- real change: 8 -> 12 hex ----------------------------------------------
say "5) 现在做个真正的改动：token 从 8 位改成 12 位。文档就过时了。"
sed -i.bak 's/hexdigest()\[:8\]/hexdigest()[:12]/' "$DEMO/src/auth.py" && rm -f "$DEMO/src/auth.py.bak"
run "python3 '$ANCHOR' -p '$DEMO' report"
echo "   → STALE！代码一改，描述它的文档立刻报警——不靠人记得去看。"

# --- fix doc + re-baseline -------------------------------------------------
say "6) 更新文档后重定基线，状态回到同步。"
echo '   (假设你已把 learning 改成 "...前 12 位")'
AID="$(python3 "$ANCHOR" -p "$DEMO" --json list 2>/dev/null | python3 -c 'import sys,json;print(json.load(sys.stdin)["anchors"][0]["anchor_id"])')"
run "python3 '$ANCHOR' -p '$DEMO' verify --anchor-id $AID"
run "python3 '$ANCHOR' -p '$DEMO' report"

say "完成。这就是 Yoke Anchor：会自己说自己过时的活文档。"
echo "在你自己的项目里：python3 scripts/anchor.py add --doc-kind learning --doc-ref <key> --code-file <f> --symbol-name <fn>"
