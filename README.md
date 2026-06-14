> **Language**: English · [中文](README.zh.md)

# Yoke

**The AI development pipeline whose docs tell you when they go stale.**

Yoke splits development across a set of specialized agents, enforces a hard separation between *doing* and *reviewing*, and ships with a three-layer living-documentation system. Its defining feature: every doc is anchored to the real code it describes — change the code, and the stale doc flags itself in red, so nobody has to remember to go check. 100% local, zero dependencies.

[Landing page](https://dashsoap.github.io/yoke/) · [GitHub](https://github.com/Dashsoap/yoke) · Three platforms: Claude Code · Cursor · Codex

---

## The killer feature in 30 seconds: change code → docs turn red

The real problem with living documentation isn't that it's written badly — it's that it silently rots after you write it, and you have no idea which sentence has gone wrong. Yoke uses content hashing to pin every doc to the exact span of code it describes (a function or class). The moment the code changes, the anchor's hash changes, and the corresponding doc flips to `stale` — at the instant the code moves, not whenever some agent later happens to notice the doc is wrong.

No install, no touching your repo — see it for yourself with one command (runs in an isolated temp dir, pure `python3`, zero deps):

```bash
bash scripts/anchor-demo.sh
```

It walks the full loop:

```
$ anchor add ... --symbol-name make_token      # anchor a learning to a function → FRESH
$ anchor scan                                  # insert 3 comment lines at the top → still FRESH (symbol mode resists line drift)
$ anchor report                                # change token from 8 to 12 chars → STALE! the doc raises its own alarm
$ anchor verify --anchor-id A-xxxx             # re-baseline after fixing the doc → back to FRESH
```

Key design: **symbol mode beats line mode.** Anchoring re-locates the symbol by name and then hashes its body, so inserting unrelated code above it never false-triggers `stale` — only a real change to the anchored function's content does. This is what keeps the "doc health dashboard" from drowning in false positives, and therefore what makes it trustworthy.

Enable it in your own project:

```bash
python3 scripts/anchor.py add --doc-kind learning --doc-ref <key> --code-file <f> --symbol-name <fn>
python3 scripts/anchor.py report                       # staleness report for humans/agents
python3 scripts/anchor.py dashboard                    # generate a single-file HTML health dashboard
```

> Why this is the differentiator: code-graph tools are precise but don't understand design intent; LLM-doc tools are readable but hallucinate and silently rot. Yoke does both — and makes "stale" machine-checkable for the first time: the audit stage docks points for unaddressed stale docs, turning freshness into a hard gate.

---

## How it works

Requirements in, production-grade code + living docs out. Product managers use `/propose`, developers use `/trace` — both entry points share the same pipeline.

```
propose (PM) ──┐
               ├──→ _trace-persist → pipeline → architect → qa + coder → audit → update-map → ship
trace   (Dev) ─┘                        │                      │           │
                                      guard                  learn ←─── learn
                                  (scope protection)   (experience capture + anchor staleness)
```

Once confirmed, `/pipeline` adaptively schedules the downstream stages by complexity: generate type contracts, write tests, implement code, run a quality audit, update docs, open a PR — fully autonomous.

## Install

### Claude Code

```bash
# 1. Add the marketplace (run in your terminal)
claude plugin marketplace add https://github.com/Dashsoap/yoke.git

# 2. Install (globally, available in all projects)
claude plugin install yoke

# Or install for the current project only
claude plugin install yoke --scope project
```

Restart your Claude Code session for it to take effect.

### Cursor

```bash
# 1. Clone the repo
git clone https://github.com/Dashsoap/yoke.git ~/.cursor/yoke

# 2. Copy skills into your project
mkdir -p .cursor/skills
cp -r ~/.cursor/yoke/skills .cursor/skills/yoke
```

### Codex

```bash
# 1. Clone the repo
git clone https://github.com/Dashsoap/yoke.git ~/.codex/yoke

# 2. Symlink the skills
mkdir -p ~/.agents/skills
ln -s ~/.codex/yoke/skills ~/.agents/skills/yoke

# 3. Restart Codex
```

## Skills

### Intake — requirement entry points

| Skill | User | Responsibility |
|-------|------|----------------|
| `/propose` | Product manager | Premise-challenging + requirements in product language, outputs a product brief with alternatives |
| `/trace` | Developer | Technical impact analysis, component-level assessment, dual-source governance/compliance, full trace |
| `_trace-persist` | Internal | Persistence engine (ID generation, file writes, CSV indexing), called by propose/trace |

### Core — development pipeline

| Skill | Trigger | Responsibility |
|-------|---------|----------------|
| `/pipeline` | After trace is confirmed | Adaptively schedule downstream stages by complexity |
| `/architect` | Scheduled by pipeline | OpenSpec type contracts, invariants, FSM, failure journeys |
| `/qa` | Contract ready | TDD test suite + API mocks, before implementation |
| `/coder` | Tests RED | Self-healing loop + test baseline + adaptive escalation + root-cause analysis |
| `/audit` | Tests pass | Confidence scoring + evidence-chain audit, invariant violation = hard veto |
| `/update-map` | Audit passed | Update MAP.md, requirement traceability, product handbook, tech debt |
| `/ship` | After update-map | Create PR/MR, generate changelog, review-readiness board |

### Safety — guardrails and experience

| Skill | Responsibility |
|-------|----------------|
| `/guard` | Edit-scope limits + dangerous-command interception, auto-activated in pipeline worktree mode |
| `/learn` | Cross-session experience capture (patterns/pitfalls/preferences), auto-contributed by /audit and /coder |
| `/anchor` | **Killer feature**: anchor docs to code + content-hash staleness detection. /coder scans at finish, /audit docks points, /update-map does localized review |

### Docs — documentation management

| Skill | Responsibility |
|-------|----------------|
| `/init` | **New-project scaffolding** (running origin in an empty dir fails → use init: asks 2 questions, writes a minimal PRODUCT-MAP + 5 CSVs) |
| `/origin` | Bootstrap the living-docs system (Genesis), calibrate existing docs (Reconcile) |
| `/migrate` | Product-doc migration (--docs), index migration (--index) |
| `/digest` | Fold fragmented traces into product module files, prune stale, merge duplicates |
| `/explore` | Quickly understand the project's overall structure, architecture, and feature modules |

## Quick start

```bash
# PM raises a requirement
/propose Users want to see real-time notifications on the homepage

# Developer raises a requirement (with technical analysis)
/trace Users want to see real-time notifications on the homepage

# After confirming the requirement, start the pipeline
/pipeline

# When the pipeline finishes, create a PR
/ship

# Inspect the project's experience library
/learn

# Check living-doc health (which docs went stale because code changed)
python3 scripts/anchor.py report

# Or just explore the project
/explore
```

## Update

```bash
# Claude Code
claude plugin update yoke

# Codex
cd ~/.codex/yoke && git pull
```
