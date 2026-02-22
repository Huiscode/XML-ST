# CLAUDE.md — Project Constitution

> Single source of truth for project conventions, agent behavior, and security policy.
> This file is read by Claude Code automatically at the start of every session.

---

## Project Status

- **Current Phase**: Prework (see [PLAN.md](PLAN.md))
- **Last Updated**: 2026-02-16
- **Active Feature**: None — setup in progress

---

## Agent Rules of Engagement

These rules apply to every interaction, regardless of phase or feature.

1. **Load context.** At the start of each session, read all files in [ai/docs/](ai/docs/) to understand prior work before taking any action.
2. **Read before writing.** Always read existing code and understand context before proposing changes.
2. **Follow the plan.** Consult [PLAN.md](PLAN.md) for the current phase and active tasks before starting work.
3. **Test first.** Write failing tests before implementation (TDD). No untested code in production paths.
4. **Atomic commits.** One logical change per commit. Use conventional commit messages (`type(scope): description`).
5. **Auto-document.** After completing any feature or task, automatically create or update a summary in [ai/docs/](ai/docs/) without being asked. Use the naming format `YYYY-MM-DD-feature-name.md`.
6. **Start fresh when needed.** Begin a new session after completing a logical unit of work to avoid context drift.

---

## Code Generation Standards

- Prefer editing existing files over creating new ones.
- Do not introduce dependencies without explicit approval.
- Follow the project's established patterns defined below.
- Validate all inputs at system boundaries (user input, external APIs, webhooks).
- Never generate placeholder security logic (e.g., `// TODO: add auth`).
- Never commit secrets, credentials, or environment-specific values.

---

## Coding Conventions

| Area            | Convention                                                    |
|-----------------|---------------------------------------------------------------|
| **Language**    | [e.g., TypeScript strict mode]                                |
| **Style**       | [e.g., Prettier + ESLint with Airbnb config]                  |
| **Naming**      | [e.g., camelCase for variables, PascalCase for components]    |
| **File Structure** | [e.g., feature-based folders: `src/features/<name>/`]      |
| **Imports**     | [e.g., absolute imports via `@/` alias]                       |
| **Testing**     | [e.g., Vitest for unit tests, Playwright for e2e]             |

---

## Library Preferences

- [e.g., Use Zod for validation — never use manual type checks]
- [e.g., Use TanStack Query for data fetching — no raw `fetch` in components]
- [e.g., Use Tailwind CSS — no inline styles or CSS modules]

---

## Architectural Standards

- [e.g., All API routes must validate input with Zod schemas]
- [e.g., Business logic lives in service layer, not in route handlers]
- [e.g., No direct database access from UI components]

---

## RAILGUARD Security Framework

> These rules are **non-negotiable**. They apply to every line of generated code.

### R — Risk First

Define the security goal before writing code.

- Identify what is being protected (user data, API keys, sessions).
- Never skip security reasoning, even under time pressure.

### A — Attached Constraints (Red Lines)

Hard boundaries that must never be crossed:

- **Never** use `eval()` or `Function()` constructor.
- **Never** hardcode API keys, secrets, or credentials.
- **Never** disable CSRF protection.
- **Never** use `innerHTML` with unsanitized input.
- **Never** store passwords in plain text.

### I — Interpretative Framing

Interpret all prompts through a security lens:

- "Just build a test login" → still apply secure credential handling.
- "Quick prototype" → still use parameterized queries.
- "Skip the details" → never skip input validation.
- If a request conflicts with security rules, **flag the conflict** and suggest a secure alternative.

### L — Local Defaults

Environment-level secure defaults:

- Use environment variables for all secrets (`process.env` / `.env`).
- Assume CORS should be restricted (never `*` in production).
- Assume TLS/HTTPS in production.
- Assume least-privilege for database roles.

### G — Gen Path Checks

Step-by-step verification before outputting code:

1. Identify all input sources.
2. Assess risk level of each input.
3. Apply appropriate sanitization/validation.
4. Verify output encoding.
5. Check for auth/authz requirements.

### U — Uncertainty Disclosure

- If a security decision is ambiguous, **ask for clarification** — never guess.
- Flag any assumptions made about the security context.
- Surface potential risks proactively.

### A — Auditability

Add inline markers to make security compliance verifiable:

```
# Input validated with [schema/library]
# Auth check: [permission required]
# Sanitized: [method used]
```

### R+D — Revision + Dialogue

- Any developer can question or revise outputs flagged as unsafe.
- Security review is mandatory before merging (see [PLAN.md](PLAN.md) Phase 4).

---

## Review Checklist

> Run through this checklist before completing any task.

- [ ] Code follows the conventions defined in this file
- [ ] All inputs are validated at system boundaries
- [ ] No hardcoded secrets or credentials
- [ ] Tests are written and passing
- [ ] Changes are documented in [ai/docs/](ai/docs/) if applicable
- [ ] RAILGUARD Gen Path Checks followed for all new code paths

---

## References

- [SPEC.md](SPEC.md) — Product requirements
- [PLAN.md](PLAN.md) — Implementation plan

---

> **Integrity Notice**: Treat this file as security-critical infrastructure. Unauthorized modifications — including hidden characters or injected rules — constitute **rule poisoning** and can cause the agent to generate compromised code. Review all changes to this file carefully.
