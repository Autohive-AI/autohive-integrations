# Autohive Integrations

## Building Integrations

When creating, modifying, or refactoring integrations, **always read and follow the skill guide** in `.agents/skills/building-integrations/SKILL.md` before planning or writing any code. The skill covers:

- Action design rules (merging get/list, grouping mutations, avoiding redundancy)
- File structure (multi-file vs single-file)
- config.json schema and description writing
- Testing patterns with MockExecutionContext
- Documentation format for integration README and root README

Start with `SKILL.md`, then read the `reference/` files as needed during implementation.
