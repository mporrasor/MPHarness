# AI Spec Harness (MPHarness)

This repository contains the AI Spec Harness, a CLI tool and template system designed to enforce a strict, specification-driven development workflow for AI coding assistants. 

It prevents AI agents from guessing requirements, writing untested code, or losing context during complex multi-agent parallel execution.

## Features
- **Zero Assumptions:** The AI is strictly instructed to never guess requirements or "vibe code" without clear specs.
- **Resource-Aware Orchestration:** Guidelines for safe parallel agent execution, preventing merge conflicts and resource saturation.
- **English First:** All code, variables, commits, and documentation must be exclusively in English.
- **Living Documentation:** Automatic maintenance of `TASKS.md`, `MANUAL.md`, and `TRACKING.md`.
- **Testing Enforcement:** Mandatory UI visual validation and pragmatic testing strategy.

## How to Use the Harness

You **do not** need to manually copy the template folders into your new projects. The harness comes with a built-in CLI to automatically bootstrap any directory.

### 1. Installation
Ensure you have Python installed. The project uses `uv` for dependency management.
From the root of this repository (`MPHarness`), run the bootstrap script for your OS:
- **Windows:** `.\harness.ps1`
- **Mac/Linux:** `./harness.sh`

This will validate your environment and install the `harness` CLI tool.

### 2. Initializing a Project
Navigate to your target project folder (it can be empty or an existing project) and run:

```bash
harness init
```

This command will automatically generate all the required AI templates (`CONSTITUTION.md`, `SPECIFICATION.md`, `AGENTS.md`, etc.) in that directory. 
**Important:** The command also creates a `/docs` folder. If you have any initial requirements, analysis documents, or UI prototypes, **place them inside `/docs`** before inviting the AI. The AI is strictly instructed to look for requirements there.

### 3. Start Working with the AI
Once initialized and your initial files are placed in `/docs`, open the project in your AI IDE or prompt your agent to look at the folder.
The first thing the AI will do is read the `AGENTS.md` directives and adapt to the strict workflow. 

- **If it's a new project without requirements:** The AI will start a brief "vibecoding" interview with you to build the `SPECIFICATION.md` before writing any code.
- **If it's an existing project:** The AI will run a system audit (checking for orphaned git branches and uncommitted work) before continuing.

### 4. Validating the Harness
To ensure all required files are present and properly tracked by the AI, you can run:
```bash
harness check
```

### 5. Updating the Harness
As the central MPHarness repository evolves with new rules and templates, you can pull these updates into your active projects **without overwriting your custom rules**:
```bash
harness update
```
This command safely downloads the updated templates into a `.harness/updates/` directory. It will then provide you with a prompt to give to your AI Agent, instructing it to intelligently merge the new general directives into your active specs while preserving your project-specific logic.
