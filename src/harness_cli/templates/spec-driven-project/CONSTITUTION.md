# Project Constitution

This file defines the immutable rules, principles, and guidelines for this project. All AI agents and human developers MUST adhere to these rules.

## 1. Core Principles
- **Clarity over Cleverness:** Code should be readable and maintainable.
- **Spec-Driven:** Never write code before the `SPECIFICATION.md` and `TASKS.md` are updated. The spec is the source of truth.
- **Incremental Commits:** Commit small, verifiable chunks of work.
- **Security First (No Secrets):** NEVER commit secrets, credentials, tokens, passwords, or API keys. For the local development stage, it IS permitted and recommended to use local configuration files (e.g. `.env`, `secrets.json`, etc.) according to the stack's best practices, but always ensure these files are excluded in `.gitignore` BEFORE creating and populating them.
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
- **Git Commits:** Commits MUST be atomic. Never mix unrelated changes in a single commit (e.g., do not mix a feature update with a harness update or a bug fix). Commit messages must be detailed and readable (in English to maintain consistency). Avoid terse messages. Clearly explain *what* is included and *why*.

> **AI Instruction:** When generating code, always cross-reference these rules. Do not suggest or implement patterns that violate this constitution.
