/**
 * Application Constants
 * Single source of truth for configuration values
 */

// Maximum number of lines to keep per process
// Each process maintains a circular buffer of this size
export const MAX_LINES_PER_PROCESS = 5000;

// Maximum number of lines to display from selected processes
// When multiple processes are selected, show the most recent N lines across all selected processes
export const MAX_DISPLAY_LINES = 5000;

// Export for CommonJS compatibility (Node.js backend)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        MAX_LINES_PER_PROCESS,
        MAX_DISPLAY_LINES
    };
}