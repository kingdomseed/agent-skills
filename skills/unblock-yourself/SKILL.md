---
name: unblock-yourself
description: Load before asking the user a question, reporting a task as blocked, handing the user a manual step, or asking them to log in. Also load before driving a desktop app or signed-in website, asking for a UI or design decision, or reaching another configured machine.
---

# Unblock Yourself

Every unnecessary question and premature "blocked" report stalls work until the user reads it. Exhaust available read-only tools, configured machines, and documented routes before stopping.

## 1. Classify Before Asking or Reporting Blocked

| What it is | What to do |
| --- | --- |
| **A fact** (code behavior, PR/ticket state, version, error log, email, DB/analytics query) | Look it up using available tools (`git`, `gh`, issue tracker, logs, configured CLIs, or another configured machine over SSH). Then continue. |
| **A reversible step already in scope** (pushing to the work branch, opening/updating a draft PR, running tests, filing a follow-up) | Do it, then report what you did. |
| **A missing login, tool, or permission** | Check alternate configured routes, browser profiles, or machines first (Steps 2–3). |
| **A UI, layout, or visual choice** | Render and show the options visually before asking (Step 4). Never ask visual choices in text alone. |
| **A human decision or irreversible external action** (merging, publishing, sending external messages, payments, deleting user data) | Ask clearly with what you found, concrete options, and your recommendation. |

Stop and report a block only after every sanctioned route has been tried, quoting the exact error from each failed route. Never bypass access controls, permission checks, credential prompts, or CAPTCHAs.

Never ask the user to type into a file, click through a local app, or run a test you can execute directly with available CLI or browser/GUI automation tools.

## 2. Check Configured Machines & Environments

- If your local workspace or user instructions define additional machines (e.g., a build Mac, Linux workstation, or cloud dev box), check there when a tool, device, or credential is missing locally.
- Before claiming a remote machine is offline, verify network/tunnel status (e.g., `tailscale status`) and test SSH with an explicit connect timeout (`ssh -o ConnectTimeout=8 <host> true`), allowing time for auto-paused cloud boxes to wake. Report exact command output if unreachable.
- Use configured SSH host aliases rather than asking the user for usernames, IPs, or passwords.

## 3. Escalate Across Documented Routes

- When a task touches external systems (databases, observability, issue trackers, cloud consoles, CI), check your repo or user docs for the ordered list of sanctioned routes (CLI, MCP, read-only API, or signed-in browser profile).
- Try routes in order; move to the next only after the previous fails, and record the exact error.
- For browser/GUI work:
  - Use repeatable headless browser tooling (e.g., Playwright) for local servers, public pages, and automated checks.
  - Use background computer-use tooling in the user's signed-in browser/profile when an authenticated web app or native desktop app is required; target exact window IDs and close only tabs/windows you opened.
  - An account chooser screen is not a credential prompt when the project's account is known. A password, passkey, 2FA challenge, CAPTCHA, or new OAuth permission grant **is** a real block — report it clearly (with a screenshot if helpful) and never print credentials in chat.

## 4. Visual Decisions

Users decide UI from what they can see, not prose descriptions:

1. Render each option (real app screenshot or self-contained HTML comparison) with numbered labels on the visual itself.
2. Open or share the visual for the user.
3. Ask a short question referencing those numbers, keeping detail in the visual rather than a wall of text.
4. Show an "after" screenshot when UI work finishes.

## 5. Delegating Without Losing Context

Subagents do not inherit your session's discoveries. When delegating, include the exact target machine, branch/path, browser profile or account name, and constraints in the handoff prompt.
