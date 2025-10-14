# Claude Code Notes

## Testing Constraints
- NEVER actually run or start the application
- NEVER stop existing runs
- ONLY use Python-style unit tests for testing
- This constraint applies to all development work on this project

## Error Handling Philosophy
- ERRORS ARE ERRORS - we don't avoid them or hide them - we fix them
- Never mask errors with try/catch blocks to make them "graceful"
- Never add generic exception handling to suppress problems
- Always identify and fix the root cause of errors
- Clean shutdown means no errors occur, not that we ignore errors that occur

## Continuous Improvement Protocol
**Execute AGGRESSIVELY at the end of EVERY task before marking complete**

### 1. Repository Learning Capture
After completing any task, analyze and document:
- **Code Structure Insights**: Patterns discovered about how this codebase is organized
- **Architectural Learnings**: Relationships between components, data flow patterns
- **Naming Conventions**: Specific naming patterns used in this project
- **Common Patterns**: Recurring code patterns that future tasks should follow
- **Gotchas & Edge Cases**: Tricky areas that need special attention
- **File Organization**: Where specific types of code live and why

**Action**: Update this CLAUDE.md with any structural insights that would help future tasks

### 2. Tooling Opportunity Analysis
After completing any task, evaluate:
- **Could a tool have made this faster?** (linters, formatters, code generators)
- **Could a script automate repetitive parts?** (commit helpers, test runners, build scripts)
- **Could a language server improve accuracy?** (better autocomplete, refactoring support)
- **Could configuration reduce manual work?** (IDE settings, git hooks, CI/CD)
- **Could documentation generation help?** (API docs, type definitions, diagrams)

**Action**: If a tool/script would GENUINELY help (not just for the sake of having tools):
- Add a task to implement/install/configure the tool
- Execute that task immediately as part of the current workflow
- DO NOT ask the user for permission - just do it if it's clearly beneficial
- DO NOT create tools speculatively - only when there's a real, demonstrated need from the task you just completed

**Guard Against Tool Creep**: Only create tooling when:
- The same type of task will happen repeatedly in this project
- The manual approach was measurably tedious or error-prone
- The tool would save time/tokens on 3+ future tasks

### 3. Compound Efficiency Goal
**Target**: Each task should make the next task 5-10% easier/faster/cheaper through:
- Better understanding captured in documentation
- New tools/scripts available for reuse
- Patterns established that reduce decision-making
- Automation that eliminates repetitive work

**Measurement**: Track time/tokens per similar task types - trend should be downward