#!/usr/bin/env node

/**
 * Test script for per-process circular buffers
 * Simulates the exact scenario: one high-volume process, multiple low-volume processes
 */

console.log('🧪 Testing per-process circular buffers');

let lineId = 1;

// Simulate the scenario described:
// - One high-volume process that generates 1000x more logs
// - Several low-volume processes that only generate a few lines

// Low-volume processes: send just a few lines at the start
const lowVolumeProcesses = ['config', 'monitor', 'health'];
lowVolumeProcesses.forEach(processName => {
    console.log(`\x1b[1;36m${processName}\x1b[0m | Line ${lineId++} - Initial startup`);
    console.log(`\x1b[1;36m${processName}\x1b[0m | Line ${lineId++} - Configuration loaded`);
    console.log(`\x1b[1;36m${processName}\x1b[0m | Line ${lineId++} - Service ready`);
    lineId += 20; // Gap in IDs to simulate other processes
});

console.log('\n\x1b[33m--- Now starting high-volume process ---\x1b[0m\n');

// High-volume process: generates continuous logs
let highVolumeCounter = 0;
const sendHighVolumeMessage = () => {
    const message = `Request ${highVolumeCounter++} processed - ${new Date().toISOString()}`;
    console.log(`\x1b[1;32mapi\x1b[0m | Line ${lineId++} - ${message}`);
};

// Send 100 initial high-volume messages quickly
for (let i = 0; i < 100; i++) {
    sendHighVolumeMessage();
}

console.log('\n\x1b[33m=== TEST SCENARIOS ===\x1b[0m');
console.log('1. \x1b[32mAll processes ON\x1b[0m: Should show mostly API logs (high volume)');
console.log('2. \x1b[31mAPI process OFF\x1b[0m: Should show config, monitor, health logs');
console.log('3. \x1b[36mToggle processes\x1b[0m: Should immediately show relevant history');
console.log('\n\x1b[33mSending continuous API logs...\x1b[0m');

// Continue sending high-volume messages
const interval = setInterval(() => {
    sendHighVolumeMessage();
    
    // Stop after reaching line 2000
    if (lineId >= 2000) {
        clearInterval(interval);
        console.log('\n\x1b[1;32m=== Test completed ===\x1b[0m');
        console.log('\x1b[33mExpected behavior:\x1b[0m');
        console.log('- API process should have 5000 most recent lines in its buffer');
        console.log('- Each low-volume process should have 3 lines preserved');
        console.log('- Display should show last 5000 chronological lines from selected processes');
        console.log('- Turning off API should immediately reveal low-volume process history');
    }
}, 50); // Send every 50ms

process.on('SIGINT', () => {
    clearInterval(interval);
    console.log('\n\x1b[1;31mTest interrupted\x1b[0m');
    process.exit(0);
});

// Simulate occasional low-volume messages
setTimeout(() => {
    console.log(`\x1b[1;35mmonitor\x1b[0m | Line ${lineId++} - Health check passed`);
    lineId += 50; // Gap in IDs
}, 5000);

setTimeout(() => {
    console.log(`\x1b[1;34mconfig\x1b[0m | Line ${lineId++} - Configuration reloaded`);
    lineId += 30; // Gap in IDs  
}, 10000);