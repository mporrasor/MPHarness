# Agent Instructions (The Harness)

Hello AI Agent. You are operating within an **Open Spec Project Harness**. 

## Your Directives
1. **Source of Truth:** You must prioritize reading `CONSTITUTION.md` and `SPECIFICATION.md` before making any assumptions about the project.
   - **Continuous Governance Enforcement:** Do NOT treat these rules as a one-time startup check. You MUST actively re-verify and enforce `CONSTITUTION.md` and `AGENTS.md` continuously throughout the entire session. Before starting any new task, feature, or refactor, explicitly cross-check your plan against the security, formatting, and structural rules defined in the harness to prevent context drift.
2. **Living Documentation (States & Tracking):** All state documentation (`TASKS.md`, `MANUAL.md`, `TRACKING.md`, `SPECIFICATION.md`) is a living entity. You MUST keep it strictly updated in real-time.
   - **`TASKS.md`**: Mark tasks (`[/]` or `[x]`) immediately.
   - **`MANUAL.md`**: Continuously update local execution steps and tests.
   - **`TRACKING.md`**: Log the general progress and achievements daily or at the close of each phase/sprint to maintain historical traceability.
   - **Auto-Maintenance (Scale):** You MUST proactively monitor the size of these documents. If `SPECIFICATION.md` becomes too large, autonomously modularize it by extracting domains into a `/specs/` directory and linking them. Whenever a phase or block of work is fully completed, autonomously archive its planning and tasks into a historical versioned file inside `/archive/` (e.g., `/archive/v1_core_features.md`) to keep the active `SPECIFICATION.md` and `TASKS.md` completely clean and focused exclusively on current work. Do this without waiting for user prompts.
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
5. **Startup Report & Phase Plan:** Once the project analysis is finished, you MUST present a brief "Startup Report" to the user. This report MUST include a clear Execution Plan broken down into logical **Phases** (Fases). You are STRICTLY FORBIDDEN from writing any code until the user explicitly approves this Phase Plan.
- **Prototype Handling:** If the user includes a prototype (image, mockup, reference UI), you MUST explicitly ask if the implementation should match 100% (exact) or just "as much as possible" before coding.
- **Conflicts and On-the-fly Decisions:** If the user requests a change or a decision is made that contradicts the original documentation, requirements, or prototype (assuming the user might have forgotten), you MUST warn of the conflict. Explicitly ask if this new instruction becomes the new "source of truth" (and should be updated in the specs) or if they prefer to keep what was initially established.

## Orchestration & Resource-Aware Parallelism
1. **Harness & Git Alignment:** The AI MUST verify that the harness files (e.g., `CONSTITUTION.md`, `AGENTS.md`) are located in the root of the active Git repository alongside the project code. If you detect that the harness files are outside the Git repository (e.g., in a parent folder), you MUST proactively migrate all harness files and folders into the Git repository and ensure they are committed.
2. **Dynamic Resource Measurement:** The exact host machine resources (Free RAM, CPU cores) MUST be measured at the start of every session. Resources dictate how many parallel agents *can* fit. NEVER inherit resource limits from a past session, as available memory fluctuates dynamically.
3. **Collision Analysis (The True Limit):** While resources dictate how many agents *can* run, collision analysis dictates how many *should* run. Before delegating parallel tasks, you MUST analyze file-level overlaps. Files that are regenerated entirely or serialized (e.g., DB migrations, snapshot files, global config) cannot be merged cleanly. If multiple tasks touch the same global or serialized files, they MUST run sequentially to prevent "false reds" (ghost failures) and complex merge conflicts.
4. **Pre-Delegation State Logging (Limbo Prevention):** Record the delegation of a task (branch name, agent role, estimation) in `TASKS.md` BEFORE launching the subagent. This is the only defense against a hard crash; if the session drops, the work tree won't be orphaned.
5. **Execution Loops & Mechanical Rules:** Operate via iterative loops (Plan -> Execute -> Validate). Whenever a rule or constraint fails repeatedly, do not try to fix it by writing more prose in the instructions. Instead, build mechanical enforcement (e.g., create `pre-commit` hooks or CI scripts) to gatekeep merges and enforce rules automatically.
6. **Resilience & Session Recovery:** Anticipate that the session, terminal, or PC might close unexpectedly while parallel subagents are operating.
   - **Orchestrator-level State:** Maintain a centralized general state (in `TASKS.md` or another state file) that tracks the exact progress of each subagent in parallel. Log the delegation BEFORE launching the agents, not after.
   - **Startup & Limbo Audit:** When connecting to an existing project, meticulously review everything orphaned (isolated worktrees, unmerged branches), the commit history, and local changes. Synchronize this discovery with the orchestrator state to rescue any task that may have been left in limbo and minimize work loss before resuming programming.
7. **Semantic Versioning & Branching:** Strictly follow semantic versioning. Do NOT commit directly to `main` for active development. Use dedicated branches for features (`feat/`), bugs (`bugfix/`), or experiments. Merge back only when validation passes.
8. **Harness Update Validation & Rollback:** At the start of your session, you MUST run `harness update --auto` to check for updates. If files are downloaded to `.harness/updates/`, you MUST NOT immediately ask for permission to merge. Instead, you MUST follow this strict sequence:
   - **Impact Analysis Report:** Read the new templates and compare them against the project's current specs. Present the user with a detailed Pre-Merge Impact Analysis Report detailing: 1) What is new/changed. 2) How these changes impact the existing codebase. 3) What potential risks or breakage might occur (e.g., turning on strict security rules).
   - **User Decision:** Only after presenting the report, ask: *"Do you want to proceed with this update based on the analysis?"*
   - **Merge, Refactor & Commit:** If the user approves, merge the new directives into the active specs. If the impact analysis identified that the new rules break existing code, you MUST proactively refactor the codebase to comply with the new rules and ensure the application remains fully functional. **You MUST commit both the spec updates and the necessary code corrections in a separate, dedicated git commit** (e.g., `chore: update AI harness specs and refactor for compliance`).
   - **Comprehensive Verification:** After committing, you MUST perform exhaustive verification. This includes: 1) Proving that the newly introduced harness rules are actively enforced. 2) Running all necessary tests (Unit, Integration, E2E, and whatever is required) to validate correct functioning according to the entire governance, guaranteeing that all pre-existing functionalities and processes remain 100% intact.
   - **Rollback:** If verification fails and cannot be fixed quickly, perform a rollback (e.g., revert the dedicated commit) and inform the user.
   - Finally, delete the `.harness/updates/` folder.

> **Note to AI:** Reply with "Harness loaded and acknowledged" if you read this file at the start of a session.
