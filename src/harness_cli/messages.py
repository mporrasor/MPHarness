"""Plain-language messages shown to the AI and the user when a guardrail triggers."""

MESSAGES = {
    "secret_in_content": {
        "en": "Blocked: the content contains what looks like a real secret ({kind}). Put secrets in a .env file (ignored by git) and read them from environment variables.",
        "es": "Bloqueado: el contenido incluye lo que parece un secreto real ({kind}). Guarda los secretos en un archivo .env (ignorado por git) y léelos desde variables de entorno.",
    },
    "secret_file": {
        "en": "{path} may contain passwords or keys. Confirm that the AI should access it.",
        "es": "{path} puede contener contraseñas o llaves. Confirma si la IA debe acceder a él.",
    },
    "commit_protected": {
        "en": "Blocked: direct commits to '{branch}' are not allowed. Create a branch first, e.g. 'git switch -c feat/my-change'.",
        "es": "Bloqueado: no se permiten commits directos en '{branch}'. Crea primero una rama, por ejemplo 'git switch -c feat/mi-cambio'.",
    },
    "push_protected": {
        "en": "Blocked: pushing directly to '{branch}' is not allowed. Push your branch and open a Pull Request.",
        "es": "Bloqueado: no se permite subir cambios directamente a '{branch}'. Sube tu rama y abre un Pull Request.",
    },
    "force_push": {
        "en": "Blocked: 'git push --force' can erase other people's work. Use normal pushes, or --force-with-lease on your own branch.",
        "es": "Bloqueado: 'git push --force' puede borrar el trabajo de otras personas. Usa push normal, o --force-with-lease en tu propia rama.",
    },
    "force_with_lease": {
        "en": "This rewrites the branch history on the server. Confirm it is your own branch.",
        "es": "Esto reescribe el historial de la rama en el servidor. Confirma que es tu propia rama.",
    },
    "skip_checks": {
        "en": "Blocked: this would skip the project's safety checks ({detail}). Fix the reported problem instead.",
        "es": "Bloqueado: esto se saltaría los controles de seguridad del proyecto ({detail}). Corrige el problema reportado en su lugar.",
    },
    "destructive": {
        "en": "This command can delete data or work permanently ({detail}). Confirm before continuing.",
        "es": "Este comando puede borrar datos o trabajo de forma permanente ({detail}). Confirma antes de continuar.",
    },
    "remote_script": {
        "en": "This downloads a script from the internet and runs it immediately. Confirm you trust the source.",
        "es": "Esto descarga un script de internet y lo ejecuta de inmediato. Confirma que confías en el origen.",
    },
    "governance_file": {
        "en": "{path} controls this project's guardrails. Confirm that the AI should change it.",
        "es": "{path} controla las protecciones de este proyecto. Confirma si la IA debe modificarlo.",
    },
    "approval_tamper": {
        "en": "Blocked: only a person can approve the plan. Run 'harness approve' yourself in a terminal.",
        "es": "Bloqueado: solo una persona puede aprobar el plan. Ejecuta tú 'harness approve' en una terminal.",
    },
    "plan_not_approved": {
        "en": "Blocked: this project requires an approved plan before editing code. Review the plan, then run 'harness approve' in a terminal.",
        "es": "Bloqueado: este proyecto exige un plan aprobado antes de editar código. Revisa el plan y ejecuta 'harness approve' en una terminal.",
    },
    "custom_blocked": {
        "en": "Blocked by a project rule (custom.blocked_commands: '{pattern}').",
        "es": "Bloqueado por una regla del proyecto (custom.blocked_commands: '{pattern}').",
    },
    "custom_protected": {
        "en": "{path} is marked as protected in governance.yaml. Confirm that the AI should change it.",
        "es": "{path} está marcado como protegido en governance.yaml. Confirma si la IA debe modificarlo.",
    },
    "guard_error": {
        "en": "MPHarness could not evaluate this action ({detail}), so it was blocked for safety.",
        "es": "MPHarness no pudo evaluar esta acción ({detail}), así que se bloqueó por seguridad.",
    },
}


def msg(key, language="es", **kwargs):
    entry = MESSAGES[key]
    text = entry.get(language) or entry["en"]
    return text.format(**kwargs)
