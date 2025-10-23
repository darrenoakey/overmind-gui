# Overmind GUI

![Overmind GUI](splash.png)

A modern web-based graphical user interface for managing Procfile-based processes. This application provides an intuitive web interface to monitor, control, and interact with your processes through a clean, responsive web UI with real-time output streaming and intelligent failure detection.

## Overview

Overmind GUI is a daemon-based process manager with a web frontend that provides:

- **Two Operating Modes**: Native mode (direct process management) or Overmind mode (legacy tmux-based)
- **Daemon/Frontend Separation**: Backend daemon runs independently, frontend GUI can restart without killing processes
- **Real-time Monitoring**: Live process status and output with 250ms polling intervals
- **Failure Detection**: Automatic process restart on detected failure patterns
- **Persistent Storage**: SQLite database for output history and process state
- **Clean Shutdown**: Cascade shutdown from UI → Backend → Daemon → Processes

## Features

### Core Capabilities
- **Real-time Process Monitoring** - Live updates of process status and output (4x/second)
- **Dual Mode Operation** - Native mode (no dependencies) or Overmind mode (tmux-based)
- **Process Output Buffering** - Persistent SQLite storage with configurable limits
- **Failure Declarations** - Define text patterns that trigger automatic process restart
- **Responsive Web UI** - Works seamlessly on desktop and mobile devices
- **RESTful API** - Clean API endpoints for process management
- **Daemon Independence** - Restart GUI without disrupting running processes
- **Smart Shutdown** - Graceful cascade: GUI → Backend → Daemon → Processes

### Advanced Features
- **Dynamic Port Allocation** - Automatically finds available ports
- **Multiple Working Directories** - Run GUI from any directory containing a Procfile
- **Process Selection** - Filter output display by selecting/deselecting processes
- **Clear Output** - Clear accumulated output without restarting processes
- **Status Monitoring** - Real-time process status (running, stopped, dead, broken)
- **Database Polling** - Efficient incremental polling using last-message-id pattern

## Architecture

### System Design: Why Daemon + Frontend?

The system is split into **two independent processes** for operational flexibility:

1. **Daemon Process** (`native_daemon.py` or `overmind_daemon.py`):
   - Manages actual Procfile processes
   - Writes output to SQLite database (`overmind.db`)
   - Runs continuously in the background
   - Survives GUI restarts

2. **Frontend Process** (`main.py`):
   - Web server + UI for visualization
   - Reads from daemon's database
   - Can restart without killing processes
   - Connects to daemon via PID file + database

**Key Benefits:**
- **Hot Reload**: Restart GUI to pick up code changes without disrupting services
- **Resilience**: GUI crash doesn't kill your processes
- **Multiple Clients**: Future capability to connect multiple GUIs to one daemon
- **Clean Separation**: UI concerns separated from process lifecycle management

### Dual Mode Operation

The system supports two daemon modes:

#### Native Mode (Default - Recommended)
Direct process management without external dependencies.

**Architecture:**
```
GUI Frontend (main.py)
    ↓ polls database
Native Daemon (native_daemon.py)
    ↓ manages directly
Subprocess Manager (native_process_manager.py)
    ↓ spawns/monitors
Your Procfile Processes
```

**Components:**
- `native_daemon.py` - Main daemon orchestration
- `native_daemon_manager.py` - Daemon lifecycle (start/stop/PID management)
- `native_process_manager.py` - Per-process threading for stdout/stderr capture
- `procfile_parser.py` - Standalone Procfile parser with validation
- `output_formatter.py` - Color allocation and ANSI formatting
- `native_ctl.py` - CLI commands (ps, start, stop, restart, quit)

**Features:**
- ✅ No external dependencies (no tmux/overmind)
- ✅ Direct subprocess control with process groups
- ✅ Colored output matching overmind's format (12 colors cycling)
- ✅ Per-process threading (3 threads: stdout, stderr, monitor)
- ✅ SQLite database for persistent storage
- ✅ Compatible with all platforms (not just macOS)

**Process Lifecycle:**
```python
# Each process gets:
subprocess.Popen(
    command,
    stdout=PIPE, stderr=PIPE,
    preexec_fn=os.setsid  # Process group for clean SIGTERM/SIGKILL
)
```

**CLI Commands:**
```bash
./run ps                    # Show process status
./run restart web           # Restart 'web' process
./run stop api              # Stop 'api' process
./run quit                  # Stop daemon and all processes
```

#### Overmind Mode (Legacy)
Uses the overmind/tmux ecosystem for process management.

**Architecture:**
```
GUI Frontend (main.py)
    ↓ polls database
Overmind Daemon (overmind_daemon.py)
    ↓ controls
Overmind CLI (external binary)
    ↓ manages via tmux
Your Procfile Processes
```

**Components:**
- `overmind_daemon.py` - Daemon that wraps overmind binary
- `daemon_manager.py` - Daemon lifecycle management
- External `overmind` binary (must be installed)
- External `tmux` (required by overmind)

**Features:**
- ⚠️ Requires overmind and tmux installation
- ⚠️ macOS-centric (though overmind supports Linux)
- ✅ Battle-tested overmind ecosystem
- ✅ tmux session management capabilities

**CLI Commands:**
```bash
overmind ps                 # Show process status
overmind restart web        # Restart 'web' process
overmind stop api           # Stop 'api' process
overmind quit               # Stop daemon and all processes
```

**To Use Overmind Mode:**
```bash
./run server --overmind     # Start with overmind daemon
python src/main.py --overmind
```

### Database Schema

Both modes use the same SQLite database (`overmind.db`) for GUI compatibility:

```sql
-- Output lines (written by daemon, read by GUI)
CREATE TABLE output_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    process TEXT NOT NULL,
    html TEXT NOT NULL
);

-- Commands (written by GUI, read by daemon)
CREATE TABLE daemon_commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command TEXT NOT NULL,           -- 'start', 'stop', 'restart'
    process_name TEXT,
    timestamp REAL NOT NULL,
    status TEXT DEFAULT 'pending'    -- 'pending', 'completed'
);

-- Status updates (written by daemon, read by GUI)
CREATE TABLE process_status (
    process_name TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    pid INTEGER,
    updated_at REAL NOT NULL
);
```

**Communication Flow:**
- **GUI → Daemon**: Insert into `daemon_commands`, daemon polls every 0.5s
- **Daemon → GUI**: Insert into `output_lines` and `process_status`, GUI polls every 0.25s

### Failure Declaration System

**Purpose**: Automatically restart processes when specific error patterns appear in output.

**Configuration File**: `failure_declarations.json` (stored in Procfile directory)

**Example:**
```json
{
  "web": [
    "Error: EADDRINUSE",
    "panic:",
    "Fatal error"
  ],
  "worker": [
    "Connection refused",
    "Database timeout"
  ]
}
```

**Detection Flow:**
1. Process outputs text containing "Error: EADDRINUSE"
2. `ProcessInfo.add_output()` detects pattern match
3. Returns `(process_name, failure_pattern)` tuple
4. `daemon_management_task()` receives detection
5. Calls `kill_process_on_failure()` via event loop
6. Process is stopped and marked as "broken"

**Management via UI:**
- Select text in process output
- Right-click for context menu
- Choose "Add as Failure Declaration"
- Pattern is saved and activated immediately

**Management via API:**
```bash
# Add failure declaration
curl -X POST http://localhost:8000/api/failure-declarations/web/add \
  -H "Content-Type: application/json" \
  -d '{"failure_string": "Error: EADDRINUSE"}'

# Remove failure declaration
curl -X POST http://localhost:8000/api/failure-declarations/web/remove \
  -H "Content-Type: application/json" \
  -d '{"failure_string": "Error: EADDRINUSE"}'

# Get declarations for process
curl http://localhost:8000/api/failure-declarations/web
```

**Important Notes:**
- Failure detection only runs on NEW output (not historical lines from initial load)
- Process restart clears "broken" status (`ProcessInfo.restart()`)
- Case-insensitive pattern matching

## Prerequisites

### Native Mode (Default)
- **Python 3.8+** - Required for running the daemon and web server
- **Procfile** - Standard Procfile format for process definitions

### Overmind Mode (Legacy)
- **Python 3.8+** - Required for running the daemon and web server
- **tmux** - Required by overmind for session management
- **overmind CLI** - The overmind binary must be in your PATH
- **Procfile** - Standard Procfile format

### Optional Dependencies
- **psutil** - Enhanced zombie process detection (highly recommended)
- **pywebview** - Native window instead of browser (set `USE_PYTHON_WEBVIEW=1`)

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/[username]/overmind-gui-web.git
   cd overmind-gui-web
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   # Or manually:
   pip install sanic psutil ansi2html
   ```

3. **For Overmind Mode Only:**
   ```bash
   # macOS with Homebrew
   brew install tmux overmind

   # Verify installation
   which overmind
   which tmux
   ```

4. **Verify Setup:**
   ```bash
   # Make run script executable
   chmod +x run

   # Show help
   ./run help
   ```

## Usage

### Quick Start

**From any directory containing a Procfile:**

```bash
# Start GUI (native mode - default)
./run server

# Or with explicit path
./run server /path/to/your/app

# Start with overmind mode (legacy)
./run server --overmind
```

**What happens:**
1. GUI backend starts on available port (default 8000, auto-increments if busy)
2. Daemon starts (native or overmind depending on `--overmind` flag)
3. Daemon reads Procfile and starts all processes
4. GUI opens in browser (or native window if `USE_PYTHON_WEBVIEW=1`)
5. Database (`overmind.db`) created in working directory
6. PID file (`overmind-daemon.pid`) created for daemon tracking

### Using the Run Script

The `./run` script provides unified access to all functionality:

#### Server Commands
```bash
./run                            # Start from current directory
./run server                     # Explicit server start
./run server /path/to/app        # Start from specific directory
./run server --overmind          # Use overmind mode instead of native
./run test_proc                  # Start with demo Procfile (logs to output/)
```

#### Process Control (Native Mode)
```bash
./run ps                         # Show all process status
./run ps /path/to/app            # Show status for specific directory
./run status                     # Show daemon status
./run start web                  # Start 'web' process
./run stop api                   # Stop 'api' process
./run restart worker             # Restart 'worker' process
./run quit                       # Stop daemon and all processes
```

#### Development Commands
```bash
./run test                       # Run all tests
./run test <module>              # Run specific module tests
./run lint                       # Run linting (flake8/pylint)
./run setup                      # Install dependencies
./run dev                        # Start with debug mode
./run integration                # Run full integration test
```

### Direct Python Usage

#### Starting the GUI
```bash
# Native mode (default)
python src/main.py

# Overmind mode
python src/main.py --overmind

# Custom working directory
python src/main.py --working-dir /path/to/app

# Custom port
python src/main.py --port 9000

# Without UI (headless)
python src/main.py --no-ui
```

#### Native Daemon Control (Native Mode)
```bash
# Show process status
python src/native_ctl.py ps

# Control processes
python src/native_ctl.py start web
python src/native_ctl.py stop api
python src/native_ctl.py restart worker

# Daemon management
python src/native_ctl.py status
python src/native_ctl.py quit

# With specific working directory
python src/native_ctl.py --working-dir /path/to/app ps
```

### Web Interface Features

#### Process Dashboard
- **Process List**: All Procfile processes with status indicators
- **Real-time Output**: Live streaming output with ANSI color preservation
- **Status Indicators**:
  - 🟢 **running**: Process is active and healthy
  - 🔴 **stopped**: Process was intentionally stopped
  - ⚫ **dead**: Process crashed unexpectedly
  - 🟠 **broken**: Failure pattern detected
  - ⚪ **unknown**: Status not yet determined

#### Process Controls
- **Restart**: Click restart button or use context menu
- **Stop**: Stop individual processes
- **Select/Deselect**: Filter which processes show output
- **Clear Output**: Clear accumulated output without restarting

#### Output Features
- **Auto-scroll**: Automatically scrolls to latest output
- **Search**: Find text in output (browser Ctrl+F)
- **Context Menu**: Right-click text to add failure declarations
- **Color Preservation**: ANSI colors converted to HTML

#### Shutdown Button
- **Location**: Top-right corner, always visible
- **Function**: Initiates cascade shutdown
- **Flow**: UI → Backend → Daemon → Processes
- **Graceful**: All processes receive SIGTERM first, then SIGKILL if needed

### API Endpoints

The REST API is available at `http://localhost:PORT/api/`:

#### State & Status
```bash
# Get full current state (initial load)
GET /api/state

# Get all processes
GET /api/processes

# Poll for updates since last ID
GET /api/poll?last_message_id=123

# Get system status
GET /api/status

# Get daemon info
GET /api/daemon/info
```

#### Process Control
```bash
# Start a process
POST /api/process/<name>/start

# Stop a process
POST /api/process/<name>/stop

# Restart a process
POST /api/process/<name>/restart

# Toggle process selection
POST /api/process/<name>/toggle
```

#### Bulk Operations
```bash
# Select all processes
POST /api/processes/select-all

# Deselect all processes
POST /api/processes/deselect-all

# Clear all output
POST /api/output/clear
```

#### Failure Declarations
```bash
# Get declarations for process
GET /api/failure-declarations/<process_name>

# Add declaration
POST /api/failure-declarations/<process_name>/add
Content-Type: application/json
{"failure_string": "error text"}

# Remove declaration
POST /api/failure-declarations/<process_name>/remove
Content-Type: application/json
{"failure_string": "error text"}
```

#### System Control
```bash
# Shutdown everything (cascade)
POST /api/shutdown

# Restart GUI backend (preserves daemon)
POST /api/restart
```

### Proper Daemon Usage Patterns

#### Pattern 1: Long-running Development Environment
```bash
# Morning: Start daemon + GUI
./run server /path/to/myapp

# During day: GUI crashes or needs update
# Processes keep running!

# Restart just the GUI
./run server /path/to/myapp

# Your services never went down
```

#### Pattern 2: Multiple Projects
```bash
# Terminal 1: Project A
cd /path/to/project-a
./run server

# Terminal 2: Project B
cd /path/to/project-b
./run server --port 8001

# Each has independent daemon + GUI
```

#### Pattern 3: Headless Server
```bash
# Start daemon without GUI
./run server --no-ui

# Access via API
curl http://localhost:8000/api/state

# Or connect GUI later
# (GUI will find running daemon via PID file)
```

#### Pattern 4: Clean Shutdown
```bash
# Option 1: Click shutdown button in GUI
# - GUI sends shutdown request
# - Backend stops daemon gracefully
# - Daemon stops all processes with SIGTERM
# - Cascade completes, all exits cleanly

# Option 2: Use CLI
./run quit

# Option 3: Ctrl+C in terminal
# - Signal handler triggers shutdown
# - Same cascade as button
```

#### Pattern 5: Orphaned Daemon Cleanup
```bash
# If daemon is running but GUI died:
./run status                 # Check daemon status
./run ps                     # See process status
./run quit                   # Stop daemon cleanly

# If PID file is stale:
# - System auto-detects with psutil
# - Stale PID file removed automatically
```

## Configuration

### Environment Variables
```bash
# Disable UI launch (headless mode)
NO_UI_LAUNCH=1

# Use native window instead of browser
USE_PYTHON_WEBVIEW=1

# Debug mode
DEBUG=1
```

### Working Directory Structure
```
/path/to/your/app/
├── Procfile                      # Required: process definitions
├── overmind.db                   # Created: SQLite database
├── overmind-daemon.pid           # Created: daemon PID tracking
├── failure_declarations.json     # Optional: failure patterns
├── native-daemon.log             # Created: daemon logs
└── [your app files]
```

### Procfile Format
Standard Procfile format:
```
web: python app.py --port 3000
worker: python worker.py --queue default
api: node server.js
scheduler: python scheduler.py
```

Rules:
- One process per line
- Format: `name: command`
- Process names must be alphanumeric with optional hyphens/underscores
- Comments start with `#`
- Empty lines ignored

## Project Structure

```
overmind-gui-web/
├── run                              # Unified CLI for all commands
├── version.txt                      # Auto-incrementing version
├── requirements.txt                 # Python dependencies
│
├── src/                             # All source code
│   ├── main.py                      # GUI backend entry point
│   ├── api_routes_daemon.py         # REST API endpoints
│   ├── static_files.py              # Static asset serving
│   ├── process_manager.py           # Process state model
│   ├── database_client.py           # SQLite client for GUI
│   ├── update_queue.py              # Message queue abstraction
│   │
│   ├── native_daemon.py             # Native daemon (default mode)
│   ├── native_daemon_manager.py     # Native daemon lifecycle
│   ├── native_process_manager.py    # Direct subprocess management
│   ├── native_ctl.py                # Native CLI commands
│   │
│   ├── overmind_daemon.py           # Overmind daemon (legacy mode)
│   ├── daemon_manager.py            # Overmind daemon lifecycle
│   │
│   ├── procfile_parser.py           # Procfile parsing/validation
│   ├── output_formatter.py          # Color allocation/ANSI formatting
│   │
│   ├── index.html                   # Main web UI
│   ├── app.js                       # Frontend logic
│   ├── styles.css                   # UI styling
│   │
│   └── [test files]                 # *_test.py files
│
└── output/                          # Generated files (gitignored)
    ├── test-run/                    # Test Procfile runs
    └── [logs, builds, etc]
```

## Technology Stack

### Backend
- **Python 3.8+** - Core language
- **Sanic** - Async web framework
- **SQLite3** - Persistent storage
- **asyncio** - Async task management
- **threading** - Per-process output capture (native mode)

### Process Management
- **Native Mode**: Direct `subprocess.Popen` with process groups
- **Overmind Mode**: External overmind binary + tmux

### Frontend
- **HTML5/CSS3** - Modern web standards
- **Vanilla JavaScript** - No framework dependencies
- **ANSI-to-HTML** - Terminal color preservation
- **HTTP Polling** - 250ms intervals for real-time updates

### Storage
- **SQLite** - Process output, commands, status
- **JSON Files** - Failure declarations configuration
- **PID Files** - Daemon process tracking

## Development

### Running Tests
```bash
# All tests
./run test

# Specific module
./run test process_manager

# Integration test
./run integration
```

### Linting
```bash
./run lint
```

### Debug Mode
```bash
./run dev
# Or:
DEBUG=1 python src/main.py
```

### Key Design Principles

1. **Daemon Independence**: GUI crashes don't kill processes
2. **No Mocking in Tests**: Real database, real processes, real testing
3. **DRY**: Factor out repeated concepts immediately
4. **KISS**: Simplest solution that actually works
5. **YAGNI**: No speculative features
6. **Errors Are Errors**: Never mask errors, always fix root cause
7. **Logging**: Every key action logged with context (no PII)
8. **Explicit Over Implicit**: Always clear about what's happening

### Adding Features

**Example: Add a new daemon command**

1. Add command to `daemon_commands` table (already exists)
2. Implement handler in `native_daemon.py` command loop:
   ```python
   elif command == 'your_command' and process_name:
       self.your_command_handler(process_name)
   ```
3. Add CLI command in `native_ctl.py`:
   ```python
   def cmd_your_command(args):
       _send_daemon_command(working_dir, "your_command", args.process)
   ```
4. Add API endpoint in `api_routes_daemon.py`:
   ```python
   @api_bp.route("/process/<process_name>/your_command", methods=["POST"])
   async def your_command_endpoint(request, process_name):
       ...
   ```
5. Add button/UI in `app.js` and `index.html`
6. Write tests

## Troubleshooting

### Common Issues

#### "No daemon running (PID file not found)"
```bash
# Check if daemon is actually running
ps aux | grep daemon

# Check working directory
ls overmind-daemon.pid

# Start daemon manually if needed
python src/native_daemon.py --working-dir .
```

#### "Procfile not found"
```bash
# Make sure you're in the right directory
ls Procfile

# Or specify working directory
./run server /path/to/app
```

#### "Port already in use"
```bash
# GUI automatically finds available port
# Check logs for actual port:
# "ALLOCATED PORT: 8001 (dynamically found)"

# Or specify port manually
python src/main.py --port 9000
```

#### Processes not starting
```bash
# Check daemon logs
tail -f native-daemon.log

# Check Procfile syntax
cat Procfile

# Verify commands work independently
python app.py  # test your actual command
```

#### Zombie processes
```bash
# Install psutil for better detection
pip install psutil

# Check process status
./run ps

# Force cleanup if needed
./run quit
killall -9 python  # nuclear option
```

#### Database locked
```bash
# Stop all processes accessing database
./run quit

# Remove database (loses history)
rm overmind.db

# Restart
./run server
```

#### Stale PID file
```bash
# System auto-cleans with psutil installed
# Manual cleanup:
rm overmind-daemon.pid
```

### Debug Checklist

1. **Check daemon is running**: `./run status`
2. **Check database exists**: `ls overmind.db`
3. **Check PID file exists**: `ls overmind-daemon.pid`
4. **Check Procfile syntax**: `cat Procfile`
5. **Check daemon logs**: `tail -f native-daemon.log`
6. **Check port allocation**: Look for "ALLOCATED PORT" in logs
7. **Check browser console**: F12 in browser
8. **Check API responds**: `curl http://localhost:8000/api/state`

### Known Limitations

- **Single daemon per directory**: One `overmind.db` per Procfile location
- **No process dependencies**: All processes start in parallel
- **No process groups in Procfile**: Unlike Foreman's numbered processes
- **Database growth**: Old output not auto-pruned (manual cleanup needed)
- **No Windows support for native mode**: Uses `os.setsid()` for process groups
- **No multi-user support**: Designed for single-user development environments

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make changes following design principles (see above)
4. Write tests (no mocks - test reality)
5. Run linting: `./run lint`
6. Test thoroughly: `./run test`
7. Submit PR with clear description

## License

This project is open source. Please check the LICENSE file for specific terms.

## Support

For issues, feature requests, or questions:
- Open an issue on GitHub
- Check existing issues for similar problems
- Provide detailed information:
  - Operating system
  - Python version
  - Mode (native or overmind)
  - Procfile content
  - Relevant logs
  - Steps to reproduce

---

**Design Philosophy**: This application prioritizes **operational clarity** over convenience. Daemons run explicitly, failures surface immediately, and the system state is always transparent. The daemon/frontend separation ensures your services stay up while you iterate on the UI or fix bugs in the backend.
