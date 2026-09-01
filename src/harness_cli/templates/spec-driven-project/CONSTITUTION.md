# Project Constitution

This file defines the immutable rules, principles, and guidelines for this project. All AI agents and human developers MUST adhere to these rules.

## 1. Core Principles
- **Clarity over Cleverness:** Code should be readable and maintainable.
- **Spec-Driven:** Never write code before the `SPECIFICATION.md` and `TASKS.md` are updated. The spec is the source of truth.
- **Incremental Commits:** Commit small, verifiable chunks of work.
- **Security First (No Secrets):** NEVER commit secrets, credentials, tokens, passwords, or API keys. For the local development stage, it IS permitted and recommended to use local configuration files (e.g. `.env`, `secrets.json`, etc.) according to the stack's best practices, but always ensure these files are excluded in `.gitignore` BEFORE creating and populating them.
- **Pushback Protocol (Evidence over Compliance):** If a user instruction or architectural premise is technically flawed, logically false, or impossible to implement cleanly, you MUST state it with evidence instead of forcing a broken implementation. Blind compliance propagates errors. If something cannot be done safely, say no with evidence.
- **Testing Strategy:** Evaluate the need for tests according to the feature's complexity. Apply the testing pyramid (Unit, Integration, E2E) pragmatically and **only when necessary**. It is not mandatory to follow the entire pyramid in all cases; prioritize common sense and smart coverage over dogma.
- **Mandatory Visual Validation:** Do not rely solely on code or API tests. Whenever there are changes that affect the interface, you must run the project locally and perform (or explicitly instruct) a visual validation of the frontend. The goal is to catch UI/UX errors yourself before delivering the work to the user for detailed review.

## 2. Technology Stack
- [Specify Primary Language, e.g., TypeScript / Python]
- [Specify Frameworks]
- [Specify Testing Tools]

## 3. Formatting & Style
- **English First:** All code (variables, functions, classes, comments) and ALL project documentation (`.md` files, manuals, requirements) MUST be written strictly in English.
- Use standard linting (e.g., Prettier / Ruff).
- Variables should be descriptive.
- No "magic numbers" in code; extract to constants.
- **Git Commits (Commit BEFORE Verification):** Commits MUST be highly granular and atomic to enable easy rollbacks. Commit your work as soon as the code is ready, BEFORE running long test suites or verifications. A commit is reversible; work lost to a crashed test suite is not. Do not wait until the end of a session to make a massive commit. Commit by component or logical layer (e.g., commit Database changes first, then commit Service logic, then commit UI changes). Never mix unrelated changes in a single commit. Commit messages must be detailed and readable (in English). Clearly explain *what* is included and *why*.

## 4. Security & OWASP Guidelines
- **Authentication & Authorization:** Force server-side authentication; never trust the client. Hash all passwords using strong algorithms (e.g., bcrypt, Argon2). Enforce Row Level Security (RLS) and restrict record access to authorized owners only. Limit login attempts (Rate Limiting) and implement bot protection.
- **Data Protection & Cryptography:** Encrypt sensitive data at rest and in transit. Force HTTPS for all traffic. Protect session cookies (must be HttpOnly, Secure, and SameSite). Use public/anon keys for clients; NEVER expose service/admin keys. Hide all API keys in environment variables and ensure `.env` is in `.gitignore` (No secrets in Git).
- **Documentation Privacy:** The `/docs/` folder (used for initial requirements, prototypes, and sensitive analysis) MUST be strictly added to `.gitignore`. This ensures private business ideas and prototypes remain local and are never pushed to the remote repository.
- **Input Validation & Output Encoding:** Validate and sanitize all inputs strictly on the server-side. Escape all user-generated content to prevent XSS. Block mass assignment / field manipulation (e.g., don't let users update their `is_admin` field). Strictly restrict file uploads (validate MIME type, size, and prevent execution).
- **Application Security (OWASP):** Limit API responses (do not leak internal stack traces or excessive object data). Add HTTP security headers (CSP, HSTS, X-Frame-Options). Regularly scan dependencies for known vulnerabilities. Strictly configure CORS (no `*` in production). Adhere to the OWASP Top 10 guidelines in all architectural decisions.
- **Principle of Least Privilege & Auditing:** Give services, database users, and containers only the absolute minimum permissions required. Log critical actions (e.g., user deletion, permission changes) but *never* log sensitive data (like passwords or session tokens) in plain text.

> **Final Instruction to AI:** The rules in this Constitution are ABSOLUTE and CONTINUOUS. They apply to every single iteration, commit, and line of code you write during the entire lifespan of this session. You must never bypass them or drift into casual/unconstrained programming. Always cross-reference these rules before executing code.
