# Native Daemon - Direct Process Management

The native daemon provides direct process management without requiring overmind or tmux. It's the default mode as of this update.

## Overview

The native daemon system replaces the overmind/tmux stack with direct subprocess management, while maintaining full compatibility with the existing GUI and API.

## Architecture

### Components

1. **procfile_parser.py** - Parses and validates Procfile format
2. **output_formatter.py** - Allocates colors and formats output (mimics overmind)
3. **native_process_manager.py** - Manages multiple processes with threading
4. **native_daemon.py** - Main daemon process
5. **native_ctl.py** - CLI for daemon control
6. **native_daemon_manager.py** - Daemon lifecycle management

### How It Works

1. **Process Spawning**: Each Procfile entry spawns a subprocess with dedicated threads for stdout/stderr capture
2. **Output Formatting**: Raw output is formatted as `processname | text` with ANSI colors (matching overmind)
3. **Database Storage**: Formatted HTML output is stored in SQLite (same schema as overmind mode)
4. **GUI Compatibility**: Frontend polls the database and displays output identically to overmind mode

### Threading Model

Each managed process has 3 threads:
- **stdout_thread**: Captures and formats stdout
- **stderr_thread**: Captures and formats stderr
- **monitor_thread**: Detects process death and triggers callbacks

## Usage

### Starting the GUI (Default: Native Mode)

```bash
python src/main.py
```

This starts the web GUI with the native daemon (no overmind/tmux required).

### Starting the GUI (Legacy: Overmind Mode)

```bash
python src/main.py --overmind
```

This uses the traditional overmind/tmux-based daemon.

### CLI Commands

```bash
# Check daemon status
python src/native_ctl.py status

# Show process list
python src/native_ctl.py ps

# Restart a process (via API)
# Currently requires GUI/API - direct CLI restart coming soon

# Stop daemon and all processes
python src/native_ctl.py quit
```

## Key Features

### ✅ What Works
- Direct subprocess management (no tmux/overmind dependency)
- Colored output matching overmind's format
- Per-process output capture with threading
- Clean process shutdown (SIGTERM → SIGKILL escalation)
- Same database format for GUI compatibility
- Process group management for clean kills
- Automatic color allocation for N processes
- Output alignment (process names padded)

### 🚧 Planned Features
- Direct CLI process restart (currently via API only)
- Process status in CLI (currently via GUI only)
- Inter-process communication via sockets
- Process dependency management
- Failure detection and auto-restart

## Advantages Over Overmind Mode

1. **No External Dependencies**: No need for overmind or tmux installation
2. **Simpler Architecture**: Direct subprocess management is easier to debug
3. **Better Control**: Direct process group management for clean shutdown
4. **Faster Startup**: No tmux session initialization overhead
5. **Easier Testing**: Python-only stack is easier to test

## Compatibility

The native daemon is **100% compatible** with the existing GUI:
- Same SQLite database schema
- Same API endpoints
- Same output format (ANSI → HTML)
- Same process lifecycle management

You can switch between native and overmind mode without any GUI changes.

## Files Changed

### New Files
- `src/procfile_parser.py` - Procfile parser
- `src/procfile_parser_test.py` - Parser tests
- `src/output_formatter.py` - Color and formatting
- `src/output_formatter_test.py` - Formatter tests
- `src/native_process_manager.py` - Process management
- `src/native_daemon.py` - Main daemon
- `src/native_ctl.py` - CLI tool
- `src/native_daemon_manager.py` - Lifecycle management

### Modified Files
- `src/main.py` - Added `--overmind` flag and daemon mode selection

## Testing

Run the core module tests:

```bash
# Test Procfile parser
python src/procfile_parser_test.py

# Test output formatter
python src/output_formatter_test.py
```

All tests should pass (100% success rate achieved).

## Implementation Notes

### Process Group Management
- Uses `preexec_fn=os.setsid` to create new process group
- Enables killing entire process tree with `os.killpg()`
- Graceful shutdown: SIGTERM (5s) → SIGKILL fallback

### Output Capture
- Non-blocking readline from stdout/stderr pipes
- Separate threads prevent deadlocks
- UTF-8 decoding with error replacement
- Empty lines filtered out

### Color Allocation
- 12 ANSI colors matching overmind's palette
- Colors cycle when more processes than colors
- Consistent color assignment per process
- ANSI codes preserved through to HTML conversion

### Database Storage
- Same schema as overmind daemon
- HTML content includes ANSI color codes (converted)
- Process name stored separately for filtering
- Auto-incrementing IDs for polling

## Future Work

1. **Enhanced CLI**: Add direct process control (restart, stop) via CLI
2. **Socket Communication**: Enable daemon-CLI communication via Unix sockets
3. **Process Dependencies**: Support process startup ordering
4. **Auto-Restart**: Monitor and auto-restart failed processes
5. **Resource Monitoring**: Track CPU/memory per process
6. **Log Rotation**: Automatic log file rotation and cleanup
