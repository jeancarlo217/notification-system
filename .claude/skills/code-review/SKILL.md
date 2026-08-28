---
allowed-tools: Bash(git *), Bash(ls *)
name: code-review
description: Review your own diff against the canon with explicit quality gates, the machine gates first, then three isolated judgement axes (Canon, Spec, Craft) with blocking and advisory findings. Use when reviewing a delivered change, your working branch, or anything before you commit it. Triggers on "/code-review", "review this diff", "review the branch", "is this ready to commit".
---

# Review your own diff

Review the diff between `HEAD` and a fixed point, in **two stages that are not interchangeable**: the
**machine gates**, pass or fail and decided by a script, and the **judgement axes**, decided by reading
and never run before the machine gates are green.

This is the review of work done inside this project's loop: the requirement is known and the canon was in
the author's reading protocol, so a canon violation here is a defect in the delivery, never a gap in the
author's knowledge.

**This skill reports. It does not fix.** And it never claims completeness: say what was examined and
under what criteria, never that the diff is clean.

## Stage 0: pin the diff, and fail early

1. **The fixed point** is whatever the user named: a SHA, `main`, `HEAD~5`, a tag. If they named none,
   ask. Do not guess.
2. `git rev-parse <ref>` resolves, and `git diff <ref>...HEAD` is non-empty. Three dots, so the
   comparison is against the merge base.
3. `git log <ref>..HEAD --oneline` for the commit list.
4. **Find the requirement.** The invariant, foundation section or ADR section the work claims to
   implement, from the conversation, the branch name or the commit messages. If there is genuinely no
   requirement, the Spec axis reports so, and work that traces to nothing should not exist.

## The diff you are reviewing

- Commits since `main`: !`git log main..HEAD --oneline 2>/dev/null | head -20 | grep . || echo "(none: no repository, you are on main, or the branch has no commits yet)"`
- Working tree: !`git status --short 2>&1 | head -20`

---

## Stage 1: the machine gates, and they run first

Never spend a model's attention on what a script already decides. **Run them through `/quality-gate`**,
which knows which checks exist and which have no surface yet; this skill does not restate the list. Run
them yourself: do not read the author's claim that they passed.

**If a machine gate is red the review stops here and reports that.** A judgement review over a red build
is a report about code that does not run.

Prose hygiene is not on this list on purpose: the em dash and double hyphen rule is enforced by
`.claude/hooks/check-prose.sh` at write time.

## Stage 2: three axes, in isolated contexts, never merged

Run the three as **three parallel subagents**, each seeing the diff, the commit list and its own
criteria, and not the reasoning that produced the change. A fresh reader evaluates the result on its own
terms; a shared context lets one axis mask another.

**Do not merge or rerank the three reports.** Present them under their own headings.

The three prompts are in [`references/axis-prompts.md`](references/axis-prompts.md), copied verbatim
rather than composed each time; only three values vary (the diff range, one clause naming the change, the
requirement citation). Three `Agent` calls in one message so they run concurrently,
`subagent_type: general-purpose`. Each prompt ends with two instrumentation lines about the harness; they
cost nothing and keep claims about the harness measured rather than remembered.

### Axis 1: Canon. Blocking.

Does the diff violate something this project decided? Law, not judgement: a finding here blocks. The axis
reads [`references/canon-checks.md`](references/canon-checks.md), which carries what a violation of each
invariant I1 to I7 looks like in code. Cite the rule by identifier and quote the hunk. An invariant
finding is never softened; if the invariant is genuinely wrong, that is a foundation revision decided by
the owner, not a compromise reached inside a review.

### Axis 2: Spec. Blocking for the first and third, advisory for the second.

Against the requirement's acceptance test, quoting it for every finding:

1. **Missing or partial**: the criterion asks for something the diff does not do. Blocking.
2. **Scope creep**: behaviour no requirement asked for. Advisory, reported with the question of whether
   it should be ratified or removed, because unrequested behaviour is untested by construction.
3. **Implemented but wrong**: the criterion looks satisfied and the implementation would not survive its
   own test. Blocking.

Four disqualifiers, each blocking on its own: a schema change with no migration; a change to public
behaviour with no test; a commit message that does not match the diff; a regression, meaning an existing
test weakened, renamed or deleted.

### Axis 3: Craft. Advisory by default.

Judgement calls, labelled as such. A documented decision in this repository always wins over this axis,
and anything the tooling already enforces is skipped. Test quality first (implementation-coupled,
tautological, logic in a test, a name needing "and"), then the smell baseline (Fowler chapter 3, each a
labelled heuristic), then agent navigability (generic names, oversized files, deep nesting, boundaries
with no explicit type, error messages carrying no value), then comments against `CLAUDE.md`.

## Stage 3: the finding format

Every finding carries file and line with the quoted hunk, the rule cited by identifier (or named as a
judgement call), and the concrete failure: inputs or state, and the wrong output or corruption that
results. "This could be a problem" is not a finding.

**On the Craft axis the third element is the replacement, not the failure**, concretely enough to apply.
A Craft finding with no replacement is an opinion, and an opinion goes unstated. Judge the replacement on
the next reader, never on line count: if the shorter form carries a tradeoff, name it or drop the finding.

Report only what you are confident of. When unsure whether something is real, say you are unsure rather
than dropping it or dressing it up.

## Stage 4: the verdict

| Verdict | Meaning |
| --- | --- |
| **BLOCKED** | at least one machine gate is red, or at least one blocking finding stands. Not committed |
| **PASS WITH FINDINGS** | gates green, no blocking finding, advisory findings listed. The owner decides |
| **PASS** | gates green, nothing blocking, nothing advisory worth the owner's time |

Close with per-axis counts and the worst finding within each axis, then the two things the review owes
beyond the findings: **what the canon has to absorb** (a decision taken during the work, which fans out
before the commit, never as a follow-up), and **what was not examined**, and why.
