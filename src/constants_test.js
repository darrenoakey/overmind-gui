/**
 * Tests for constants.js
 * Validates application constants are defined and have correct values
 */

import { MAX_LINES_PER_PROCESS, MAX_DISPLAY_LINES } from './constants.js';

// Test that constants are defined and are positive integers
function testConstants() {
    console.log('Testing constants...');

    // Test MAX_LINES_PER_PROCESS
    if (typeof MAX_LINES_PER_PROCESS !== 'number') {
        throw new Error('MAX_LINES_PER_PROCESS must be a number');
    }
    if (MAX_LINES_PER_PROCESS <= 0) {
        throw new Error('MAX_LINES_PER_PROCESS must be positive');
    }
    if (!Number.isInteger(MAX_LINES_PER_PROCESS)) {
        throw new Error('MAX_LINES_PER_PROCESS must be an integer');
    }

    // Test MAX_DISPLAY_LINES
    if (typeof MAX_DISPLAY_LINES !== 'number') {
        throw new Error('MAX_DISPLAY_LINES must be a number');
    }
    if (MAX_DISPLAY_LINES <= 0) {
        throw new Error('MAX_DISPLAY_LINES must be positive');
    }
    if (!Number.isInteger(MAX_DISPLAY_LINES)) {
        throw new Error('MAX_DISPLAY_LINES must be an integer');
    }

    // Test relationship between constants
    if (MAX_DISPLAY_LINES > MAX_LINES_PER_PROCESS) {
        console.warn('Warning: MAX_DISPLAY_LINES is greater than MAX_LINES_PER_PROCESS');
    }

    console.log(`✓ MAX_LINES_PER_PROCESS = ${MAX_LINES_PER_PROCESS}`);
    console.log(`✓ MAX_DISPLAY_LINES = ${MAX_DISPLAY_LINES}`);
    console.log('All constants tests passed!');
}

// Run tests
testConstants();