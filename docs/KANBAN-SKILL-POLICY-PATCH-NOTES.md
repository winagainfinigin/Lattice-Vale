# LatticeVale v14.3.38 — Kanban / Skill Policy Reliability

> Canonical release entry: `CHANGELOG.md` → `14.3.38` (2026-08-19). This file retains detailed implementation/audit context.

## Why this patch exists

Live Hermes diagnostics showed two separate model-facing failure classes while the underlying services remained functional:

- ordinary gateway turns could see Kanban tools and call worker-scoped lifecycle operations without a real `HERMES_KANBAN_TASK`, or pass the shell-variable name literally;
- `skill_manage` could receive an invalid human-readable name, malformed/unclosed YAML frontmatter, an over-budget description, or a patch before the current `SKILL.md` had been loaded, and some models repeated the same rejected call until Hermes' normal tool-loop hard stop fired.

A subsequent end-to-end Kanban test also demonstrated that the core shared board, dispatcher locking, dependency graph, triage/decomposition, cross-profile workers, completion flow, and durable attachments work. v14.3.38 therefore **does not replace or simplify that machinery**.

## Kanban policy

LatticeVale generates `latticevale-kanban-policy` v1.2.0 for installer-managed gateway profiles when Kanban is enabled. It uses Hermes `pre_tool_call` behavior conservatively:

- an unbound root `kanban_create` with a valid installed assignee is shallow-modified to `triage=true`;
- a literal `HERMES_KANBAN_TASK` task-id argument is shallow-replaced only when a real worker binding exists;
- missing/invented assignees are blocked with the discovered real profile roster;
- worker-only lifecycle operations require an actual bound worker task and cannot target a different task;
- task-scoped reads/comments from normal sessions require an explicit real task id;
- worker-created child cards are not recursively forced back through root triage.

The managed SOUL policy additionally tells agents to avoid duplicate cards, respect dependencies/concurrency/review flow, use durable task results/attachments after completion, and return substantive task results when that is what the user requested.

## Profile portability / ownership

The installer discovers every real Hermes profile directory with a readable `config.yaml` for **routing validation**. LatticeVale still edits only:

- the default Hermes configuration it manages; and
- profile names recorded in `.installer-managed-profiles`.

A valid user-created profile may remain `orchestrator_profile` or `default_assignee` without becoming installer-owned. If a saved default assignee is stale, LatticeVale prefers another managed profile; otherwise it falls back to the valid orchestrator rather than conscripting an arbitrary external profile. No username, WSL distro name, Windows drive, model identifier, Matrix room, or secondary-profile name is hard-coded by this policy.

## Skill authoring / recovery

Managed profiles receive an installer-owned SOUL block that instructs agents to:

- normalize human-readable names to valid skill slugs;
- generate a complete closed YAML frontmatter block;
- keep descriptions within the installed Hermes validation budget;
- use `create`, `patch`, `edit`, and `write_file` for their intended scopes;
- load the current skill with `skill_view` before patching an existing skill;
- read all requested source/input coverage before authoring;
- treat validation errors as corrective data and never repeat an identical rejected call;
- change strategy after two failures instead of weakening tool-loop hard stops;
- verify the resulting skill after a successful write.

Fresh managed profiles receive `skills.write_approval: false` only when the setting is absent. Existing explicit booleans are preserved during repair/update/reconfigure. With automatic decomposition/dispatch enabled, Kanban cards can cause workers to execute the tools available to their assigned profiles; the context guard is not a sandbox for untrusted task content. Users who require an approval boundary for agent-managed skill changes should explicitly enable `skills.write_approval`.

## Clean and repair adoption

The `integrations` checkpoint revision advances to 2. Clean installs execute the policy normally. Existing managed stacks whose older integrations checkpoint is already complete re-run the stage on their next mutating LatticeVale operation, including Resume / repair, Change components, Reconfigure providers/profiles, Advanced recovery, and Update / repair. The migration does not require a component software refresh and does not delete existing Kanban cards or persistent skill data.
