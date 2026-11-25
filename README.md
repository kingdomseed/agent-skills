# agent-skills

Reusable skills for coding agents (Antigravity, Factory Droid, Claude Code, Codex, Cursor).

## Install

```bash
npx skills add kingdomseed/agent-skills
```

Or copy any folder under `skills/` into `~/.agents/skills/` (or your repository's `.agents/skills/`).

## Skills

| Skill | Purpose |
| --- | --- |
| [`skills/pr-audit`](skills/pr-audit/SKILL.md) | Audit a diff or PR for necessity, silent failures, scope leaks, migrations, races, paired-PR breaks, and proof quality |
| [`skills/review-triage`](skills/review-triage/SKILL.md) | Adjudicate noisy, overbroad, or conflicting review findings and flag structural refactors before editing |
| [`skills/pr-review-walkthrough`](skills/pr-review-walkthrough/SKILL.md) | Plain-English PR walkthrough and live review-thread audit |
| [`skills/architecture-diagram`](skills/architecture-diagram/SKILL.md) | Generate a self-contained interactive HTML layer-band architecture diagram and markdown twin |
| [`skills/write-for-smart-readers`](skills/write-for-smart-readers/SKILL.md) | Draft and tighten evidence-led technical prose without AI filler |
| [`skills/unblock-yourself`](skills/unblock-yourself/SKILL.md) | Route-escalation, visual-decision, and verification discipline before asking or reporting blocked |

## Attribution

- `architecture-diagram`, `pr-review-walkthrough`, and `write-for-smart-readers` are local versions adapted or collected during workflow iteration whose original upstream authors were not recorded. If you recognize an upstream source that should be credited, please open an issue or PR and I will gladly add attribution.
