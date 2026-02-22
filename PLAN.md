# PLAN.md — Implementation Plan

> Actionable, step-by-step plan that translates high-level requirements from [SPEC.md](SPEC.md) into manageable development phases. Execute in **vertical slices** — build features end-to-end (DB → API → UI) for immediate verification.

## Phase 1: Prework — Preparing the Repository

> Interrogate the existing architecture and draft guiding rules to establish guardrails.

- [ ] Run architectural research prompt to codify current patterns
- [ ] Populate CLAUDE.md with project conventions and RAILGUARD rules
- [ ] Set up instructions.md with persistent AI guidelines
- [ ] Verify all context files are in place (SPEC, PLAN, CLAUDE, instructions)

## Phase 2: Foundation — Project Scaffolding

> Use solid frameworks and UI libraries to reduce boilerplate the AI must guess.

- [ ] Initialize project with chosen framework
- [ ] Set up database schema and migrations
- [ ] Configure authentication
- [ ] Set up linting, formatting, and CI pipeline
- [ ] Write initial smoke tests

## Phase 3: Core Features — Vertical Slice Development

> Build each feature end-to-end. Use TDD: write failing tests first, then minimal code to pass.

### Feature 1: [Feature Name]
- [ ] Write failing tests
- [ ] Implement database/model layer
- [ ] Implement API/service layer
- [ ] Implement UI layer
- [ ] Verify tests pass
- [ ] Document in ai/docs/

### Feature 2: [Feature Name]
- [ ] Write failing tests
- [ ] Implement database/model layer
- [ ] Implement API/service layer
- [ ] Implement UI layer
- [ ] Verify tests pass
- [ ] Document in ai/docs/

## Phase 4: Agent Review & Hardening

> Dedicated review passes for bugs, security gaps, and style deviations.

- [ ] Run security review against RAILGUARD criteria
- [ ] Run style/lint review
- [ ] Run performance profiling
- [ ] Fix all identified issues

## Phase 5: Polish & Ship

- [ ] Final integration testing
- [ ] Update all documentation
- [ ] Deploy to staging
- [ ] Stakeholder review
- [ ] Deploy to production

## Notes

- **Start fresh** when context gets noisy — begin a new chat after completing a logical unit
- **Close the loop** — after each feature, document what was built in [ai/docs/](ai/docs/)
- Reference: [vibe coding.txt](vibe%20coding.txt) §II "The Vibe Engineering Lifecycle"
