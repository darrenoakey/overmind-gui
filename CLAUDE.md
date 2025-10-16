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

## Project Structure Learnings

### React State Management (app.js)
- Main output state: `allLines` (array of line objects) and `setAllLines`
- Line count tracking: `processLineCounts` (object) and `setProcessLineCounts`
- Line object structure: `{ id, process, html, timestamp }`
- Always use functional setState: `setState(prev => ...)`

### Inline Event Handlers
- Context menu handlers defined as inline functions within OvermindApp component
- Access component state through closures
- NOT React components - use direct DOM manipulation
- Variable references in event handlers can become stale after refactoring

### Common Gotchas
- State variable names may drift between refactorings
- Event handler closures capture old variable names
- No compile-time validation for state variable names in event handlers
- **CODE REVIEW CHECKPOINT**: When refactoring React state, search for ALL references to old state variable names, especially in inline event handlers

### Tooling Decisions
- **No ESLint**: Project uses native ES modules without build tooling - adding linting would require full Node.js dev environment against project philosophy
- **Manual validation**: Rely on code review and grep for state variable consistency

### Failure Declaration System Architecture
- **Configuration Location**: failure_declarations.json stored in Procfile directory (alongside Procfile)
- **State Management**: ProcessManager owns failure declarations, loaded on initialization
- **Detection Flow**: ProcessInfo.add_output() → returns matched pattern → triggers kill in polling loop
- **Process Restart Awareness**: ProcessInfo.restart() clears failure state, initial load skips detection
- **Frontend Integration**: Text selection + context menu → API call → immediate activation
- **API Pattern**: RESTful endpoints for get/add/remove declarations per process

### React Context Menu Pattern
- Inline event handlers in JSX can access component state through closures
- Text selection detection: window.getSelection() + range analysis to find process
- Context menu positioning: Check screen bounds and adjust menu placement
- Click-away pattern: setTimeout + addEventListener for proper event ordering
- **Hybrid Approach**: React for state, vanilla DOM for transient UI (menus) - avoids re-render overhead

### Python Patterns Discovered
- **Tuple Returns for Multi-Value**: Use `tuple[Optional[str], Optional[str]]` when function needs to return multiple related values
- **Async Fire-and-Forget**: `loop.create_task(coroutine)` in Sanic for background operations within request handlers
- **JSON Config Files**: Store in working directory (Procfile location), not project root - follows user's working context

### Native Daemon Architecture (Direct Process Management)
- **Dual Daemon Support**: System supports both overmind-based (legacy) and native (direct) process management
- **Daemon Selection**: `--overmind` flag enables legacy mode, default is native mode without tmux/overmind dependency
- **Module Structure**:
  - `procfile_parser.py`: Standalone Procfile parser with validation
  - `output_formatter.py`: Color allocation and ANSI formatting (mimics overmind's output)
  - `native_process_manager.py`: Per-process threading for stdout/stderr capture
  - `native_daemon.py`: Main daemon orchestration
  - `native_ctl.py`: CLI commands (ps, restart, stop, quit, status)
  - `native_daemon_manager.py`: Daemon lifecycle (start/stop/pid management)
- **Threading Pattern**: Each managed process spawns 3 threads: stdout capture, stderr capture, process monitor
- **Process Lifecycle**: `preexec_fn=os.setsid` creates process group for clean SIGTERM/SIGKILL handling
- **Output Flow**: subprocess stdout/stderr → format with process name/color → convert ANSI to HTML → database
- **Color Allocation**: 12 colors cycle for N processes, matches overmind's color scheme
- **Alignment**: Process names padded to longest name length for consistent "processname | text" format
- **Database Compatibility**: Uses same SQLite schema as overmind daemon for GUI compatibility
- **Manager Abstraction**: Both DaemonManager and NativeDaemonManager expose same interface (is_daemon_running, start_daemon, stop_daemon)
- **Integration Point**: main.py's `initialize_managers()` chooses daemon type based on flag, rest of system is agnostic

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