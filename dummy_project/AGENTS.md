# Agent Instructions (The Harness)

Hello AI Agent. You are operating within an **Open Spec Project Harness**. 

## Your Directives
1. **Source of Truth:** You must prioritize reading `CONSTITUTION.md` and `SPECIFICATION.md` before making any assumptions about the project.
2. **Task Tracking:** You will find your current assignments in `TASKS.md`. When you start a task, update it to `[/]`. When you finish, update it to `[x]`.
3. **No Guessing:** If a requirement in the `SPECIFICATION.md` is ambiguous, STOP and ask the human user for clarification. Do not "vibe code".
4. **Tool Usage:** If the environment provides MCP (Model Context Protocol) tools, use them to query databases or read files before writing new logic.

> **Note to AI:** Reply with "Harness loaded and acknowledged" if you read this file at the start of a session.
