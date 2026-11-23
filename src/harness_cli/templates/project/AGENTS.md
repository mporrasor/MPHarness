<!-- mpharness:begin (managed by MPHarness __HARNESS_REF__ — 'harness update' refreshes this block; write your own notes below the end marker) -->
# Working agreement for AI agents

This project is protected by **MPHarness**. The rules in `governance.yaml` are enforced by code
(agent guard hooks, git hooks and GitHub checks), not only by these instructions.

## 1. Talk to the user
- Reply in the language the user writes in (Spanish → Spanish, English → English).
- Write all code, comments, commit messages and project documentation in English.
- Many users are not technical: explain in plain words, avoid jargon, keep answers short.
- After each change, tell the user how to try it (what to open, click or run, and what they should see).

## 2. When MPHarness blocks or asks
- A message starting with `[MPHarness]` means a guardrail triggered. Explain to the user, in simple terms,
  what was stopped and why, then propose the safe alternative the message suggests.
- Never try to get around a guardrail: no alternative commands that do the same thing, no `--no-verify`,
  and never edit `governance.yaml`, hook settings or workflows just to unblock yourself.
- Only the user approves plans (`harness approve`) and changes the rules.

## 3. How to work
1. **Understand** the request. If something important is unclear (data, users, money, security, scope),
   ask first. For small, reversible choices, pick a sensible default and say which one you chose.
2. **Plan** before writing code for anything beyond a small fix:
__PLANNER_SECTION__
3. **Branch**: never work on `main`. Create a branch such as `feat/<short-name>` or `fix/<short-name>`.
4. **Small commits**: one logical change per commit, with a clear English message (what and why).
   Commit as soon as a piece works, before long test runs.
5. **Verify**: run the tests and the app. If the change affects the UI, open it and check it yourself.
6. **Deliver** through a Pull Request. The MPHarness check must pass before merging.
7. **Push back with evidence**: if a request is unsafe, impossible or contradicts earlier decisions,
   say so and explain why instead of building something broken.

## 4. Secure by default
- **Secrets**: never put keys, tokens or passwords in code, docs or commits. Use a `.env` file (git-ignored)
  and commit a `.env.example` with placeholder values. If a secret was exposed, tell the user to rotate it.
- **Input**: validate and sanitize every input on the server. Never trust prices, roles or totals sent by the client.
  Use parameterized queries (no string-built SQL). Escape output to prevent XSS. Limit upload type and size.
- **Auth**: hash passwords with Argon2 or bcrypt. Use secure session cookies (HttpOnly, Secure, SameSite).
  Rate-limit login and password reset. Use generic errors ("if the email exists, we sent a link").
  Check permissions on the server for every request, and only show users their own data.
- **Web**: HTTPS only; set security headers (CSP, HSTS, X-Frame-Options); use CSRF protection for forms;
  never use `*` in CORS for production; do not leak stack traces to users.
- **Integrations**: verify webhook signatures (payments, etc.). Give services and database users the
  minimum permissions they need. Rate-limit expensive endpoints (AI calls, emails, heavy queries).
- **AI features**: treat user text sent to an LLM as untrusted (prompt injection); sanitize LLM output
  before showing it; never put secrets in prompts.
- **Logs**: log important actions, never passwords, tokens or personal data in plain text.

## 5. Dependencies
- Add a dependency only when it clearly saves work; prefer popular, maintained packages, and say why.
- Use `harness audit` to check for known vulnerabilities. Before upgrading, show the user a table
  (package, current → target, reason, risk) and update only what they approve. Run the tests afterwards.

## 6. Keep it simple
- Do not create extra files, reports or abstractions nobody asked for.
- Keep the README's "how to run" section correct when setup steps change.
<!-- mpharness:end -->

## Project notes

<!-- Add anything specific to this project below: stack, conventions, decisions. MPHarness never changes this part. -->
