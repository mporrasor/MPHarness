"""Plain-language messages shown when a guardrail triggers.

Messages are in English. The AI agent relays them to the user in the user's own language.
"""

MESSAGES = {
    "secret_in_content": "Blocked: the content contains what looks like a real secret ({kind}). Put secrets in a .env file (ignored by git) and read them from environment variables.",
    "secret_file": "{path} may contain passwords or keys. Confirm that the AI should access it.",
    "commit_protected": "Blocked: direct commits to '{branch}' are not allowed. Create a branch first, e.g. 'git switch -c feat/my-change'.",
    "push_protected": "Blocked: pushing directly to '{branch}' is not allowed. Push your branch and open a Pull Request.",
    "force_push": "Blocked: 'git push --force' can erase other people's work. Use a normal push, or --force-with-lease on your own branch.",
    "force_with_lease": "This rewrites the branch history on the server. Confirm it is your own branch.",
    "skip_checks": "Blocked: this would skip the project's safety checks ({detail}). Fix the reported problem instead.",
    "destructive": "This command can permanently delete data or work ({detail}). Confirm before continuing.",
    "remote_script": "This downloads a script from the internet and runs it immediately. Confirm you trust the source.",
    "governance_file": "{path} controls this project's guardrails. Confirm that the AI should change it.",
    "approval_tamper": "Blocked: only a person can approve the plan. Run 'harness approve' yourself in a terminal.",
    "plan_not_approved": "Blocked: this project requires an approved plan before editing code. Review the plan, then run 'harness approve' in a terminal.",
    "custom_blocked": "Blocked by a project rule (custom.blocked_commands: '{pattern}').",
    "custom_protected": "{path} is marked as protected in governance.yaml. Confirm that the AI should change it.",
    "guard_error": "MPHarness could not evaluate this action ({detail}), so it was blocked for safety.",
    "tracked_secret_file": "{path} looks like a secret file and is tracked by git. Remove it with 'git rm --cached {path}', add it to .gitignore, and rotate any keys it contained.",
    "invalid_governance": "governance.yaml could not be read ({detail}). Strict defaults are being used until it is fixed.",
}


def msg(key, **kwargs):
    return MESSAGES[key].format(**kwargs)
