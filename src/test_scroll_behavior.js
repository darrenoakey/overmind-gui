#!/usr/bin/env node

/**
 * Test script to verify scroll behavior with continuous new content
 * This script sends continuous output to help test the scrolling improvements
 */

console.log('🧪 Testing scroll behavior - sending continuous output');

let lineCounter = 0;
const processes = ['web', 'worker', 'monitor', 'api'];

const sendLine = () => {
    const process = processes[lineCounter % processes.length];
    const timestamp = new Date().toISOString();
    const message = `Line ${lineCounter++} from ${process} - ${timestamp}`;
    
    // Add some variety with colors and formatting
    const colorCodes = [31, 32, 33, 34, 35, 36, 37]; // Red, Green, Yellow, Blue, Magenta, Cyan, White
    const color = colorCodes[lineCounter % colorCodes.length];
    
    if (lineCounter % 10 === 0) {
        // Every 10th line is bold and colored
        console.log(`\x1b[1;${color}m${process}\x1b[0m | \x1b[${color}m${message}\x1b[0m`);
    } else if (lineCounter % 5 === 0) {
        // Every 5th line has background color
        console.log(`\x1b[${color}m${process}\x1b[0m | ${message}`);
    } else {
        // Regular line
        console.log(`${process} | ${message}`);
    }
};

// Test scenarios:
console.log('\x1b[1;33m=== Scroll Test Started ===\x1b[0m');
console.log('\x1b[33mInstructions:\x1b[0m');
console.log('1. \x1b[32mWith autoscroll ON\x1b[0m: Should smoothly follow new content');
console.log('2. \x1b[31mWith autoscroll OFF\x1b[0m: Should stay in current position, no jumping');
console.log('3. \x1b[36mWhile scrolling\x1b[0m: Should scroll smoothly without interruption');
console.log('4. \x1b[35mSearch mode\x1b[0m: Should maintain search position');
console.log('\x1b[1;33m=== Starting continuous output ===\x1b[0m');

// Send initial burst
for (let i = 0; i < 50; i++) {
    sendLine();
}

// Then send continuous lines
const interval = setInterval(() => {
    sendLine();
    
    // Stop after 500 lines
    if (lineCounter >= 500) {
        clearInterval(interval);
        console.log('\x1b[1;32m=== Test completed - 500 lines sent ===\x1b[0m');
        console.log('\x1b[33mCheck that:\x1b[0m');
        console.log('- No blinking or jumping when autoscroll is OFF');
        console.log('- Smooth scrolling when manually scrolling');
        console.log('- Proper autoscroll when at bottom');
        console.log('- Search results stay stable');
    }
}, 200); // Send a line every 200ms

process.on('SIGINT', () => {
    clearInterval(interval);
    console.log('\n\x1b[1;31mTest interrupted\x1b[0m');
    process.exit(0);
});