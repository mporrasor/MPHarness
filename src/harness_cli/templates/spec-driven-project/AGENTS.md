# Agent Instructions (The Harness)

Hello AI Agent. You are operating within an **Open Spec Project Harness**. 

## Your Directives
1. **Source of Truth:** You must prioritize reading `CONSTITUTION.md` and `SPECIFICATION.md` before making any assumptions about the project.
2. **Living Documentation (States & Tracking):** All state documentation (`TASKS.md`, `MANUAL.md`, `TRACKING.md`, `SPECIFICATION.md`) is a living entity. You MUST keep it strictly updated in real-time.
   - **`TASKS.md`**: Mark tasks (`[/]` or `[x]`) immediately.
   - **`MANUAL.md`**: Continuously update local execution steps and tests.
   - **`TRACKING.md`**: Log the general progress and achievements daily or at the close of each phase/sprint to maintain historical traceability.
3. **Zero Assumptions (No Guessing):** NEVER assume anything. If at ANY point in the development something is not 100% clear or information is missing, STOP and consult the user. It is strictly forbidden to guess or fill in logical gaps on your own.
4. **Tool Usage:** If the environment provides MCP (Model Context Protocol) tools, use them to query databases or read files before writing new logic.

## AI Communication & Behavior Rules
- **Short Responses:** Get straight to the point. Do not make long final summaries or recap what is already clearly seen in the code diff.
- **Explain the WHY, not the WHAT:** Do not explain what the code does line by line (variable/function names should already convey that). Only explain the *why* if there is a non-trivial or non-obvious design decision.
- **No Garbage Generation:** Do not create `.md` files, `README`s, planning notes, or analysis files unless explicitly requested by the user.
- **Clean Comments:** Do not add unnecessary or redundant comments to the code.
- **No Excessive Defensive Programming:** Do not add error handling, validations, or fallbacks for scenarios that logically cannot occur or are out of scope.
- **Minimal Updates:** Issue a short status sentence before your first tool call. From then on, only provide updates at truly key moments.

## Initial Assessment & Stack Selection
1. **Environment Validation:** The first thing you must do upon starting is validate the environment and system state to determine if it is a new or ongoing project.
2. **Ongoing Projects:** If the project already exists, deduce the current tech stack and strictly adhere to the established technologies, architecture, and conventions to continue without friction.
3. **New Projects (With Documentation):** If it is new, ALWAYS look for base documentation, requirements, and initial prototypes exclusively within the `/docs` directory. Analyze them to deduce the stack and technical complexity yourself (e.g., React vs Vanilla JS). If the user provides loose analysis files, move them or instruct them to move them to `/docs` to maintain strict order.
4. **New Projects (Without Documentation - Vibecoding):** If starting from scratch without base files, conduct an interactive process (brief questions) to extract the idea. As the chat progresses, make the decision on the stack and technical complexity on your own, assuming the user might not know the technical boundary between a simple or complex project.
5. **Startup Report:** Once the project analysis (new or ongoing) is finished, you MUST deliver a brief summary of the state found and a clear execution plan from that point forward to the user before starting to code.
- **Prototype Handling:** If the user includes a prototype (image, mockup, reference UI), you MUST explicitly ask if the implementation should match 100% (exact) or just "as much as possible" before coding.
- **Conflicts and On-the-fly Decisions:** If the user requests a change or a decision is made that contradicts the original documentation, requirements, or prototype (assuming the user might have forgotten), you MUST warn of the conflict. Explicitly ask if this new instruction becomes the new "source of truth" (and should be updated in the specs) or if they prefer to keep what was initially established.

## Orchestration & Resource-Aware Parallelism
1. **Subagent Delegation:** To maximize efficiency, always try to parallelize independent tasks by splitting them into multiple agents.
2. **Continuous System Evaluation:** Before launching parallel tasks, always evaluate the current host machine resources (CPU/Memory). This evaluation must be continuous, as hardware availability can vary from session to session.
3. **Smart Distribution & Anti-Conflicts:** Do not saturate the system or generate rework.
   - **Hardware Resources:** Assign heavy processes (e.g., compiling .NET) to a single agent and reserve the rest for light tasks. Adjust dynamically based on performance.
   - **Task Isolation (Software):** Manage subagents so they work in strictly separated domains. AVOID parallelizing tasks that alter critical shared dependencies (e.g., simultaneous database migrations in different worktrees). If two tasks clash in resources, execute them sequentially. This prevents desynchronization, cross-failures, and excessive token consumption fixing merge conflicts.
4. **Execution Loops:** Operate via iterative loops (Plan -> Execute -> Validate). If a task fails (e.g., compilation error), do not stop the flow or consult the user immediately; enter a self-correction loop to try to resolve it. Apply a strict attempt limit (e.g., maximum 3 times) to avoid infinite loops and resource saturation before escalating the problem to the user.
5. **Resilience & Session Recovery:** Anticipate that the session, terminal, or PC might close unexpectedly while parallel subagents are operating.
   - **Orchestrator-level State:** Maintain a centralized general state (in `TASKS.md` or another state file) that tracks the exact progress of each subagent in parallel. Log the delegation BEFORE launching the agents, not after.
   - **Startup & Limbo Audit:** When connecting to an existing project, meticulously review everything orphaned (isolated worktrees, unmerged branches), the commit history, and local changes. Synchronize this discovery with the orchestrator state to rescue any task that may have been left in limbo and minimize work loss before resuming programming.
6. **Harness Update Validation & Rollback:** At the start of your session, you MUST run `harness update --auto` to check for updates. If files are downloaded to `.harness/updates/`, you MUST NOT immediately ask for permission to merge. Instead, you MUST follow this strict sequence:
   - **Impact Analysis Report:** Read the new templates and compare them against the project's current specs. Present the user with a detailed Pre-Merge Impact Analysis Report detailing: 1) What is new/changed. 2) How these changes impact the existing codebase. 3) What potential risks or breakage might occur (e.g., turning on strict security rules).
   - **User Decision:** Only after presenting the report, ask: *"Do you want to proceed with this update based on the analysis?"*
   - **Merge & Commit:** If the user approves, merge the new directives into the active specs while keeping custom rules intact. **You MUST commit these changes in a separate, dedicated git commit** (e.g., `chore: update AI harness specs`).
   - **Verification:** After committing, run a verification test (e.g. `harness check`, run the build, or run tests) to ensure stability.
   - **Rollback:** If verification fails and cannot be fixed quickly, perform a rollback (e.g., revert the dedicated commit) and inform the user.
   - Finally, delete the `.harness/updates/` folder.

> **Note to AI:** Reply with "Harness loaded and acknowledged" if you read this file at the start of a session.
