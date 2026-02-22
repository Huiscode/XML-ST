# ai/docs/ — Living Knowledge Base

> AI-generated feature summaries that can be fed back into the agent's context to maintain long-term consistency. Each file documents a completed feature or significant change.

## Purpose

This directory serves as **institutional memory** for the project. After completing each feature, a summary document is created here using the `/document` skill (see [SKILL.md](../SKILL.md)).

These documents are referenced by the AI agent in future sessions to:
- Understand what has already been built
- Maintain consistency with prior design decisions
- Avoid re-implementing or contradicting existing work

## Naming Convention

Files should follow this format:

```
YYYY-MM-DD-feature-name.md
```

Example: `2026-02-16-user-authentication.md`

## Document Template

Each feature doc should include:

1. **Feature name and purpose**
2. **Key design decisions and trade-offs**
3. **API contracts or interfaces introduced**
4. **Database changes** (if any)
5. **Known limitations or future considerations**
6. **How to test manually**

## References

- [vibe coding.txt](../../vibe%20coding.txt) — §I "ai/docs/ [Directory]"
- [prompts.md](../../prompts.md) — §7 "Documentation Prompt"
