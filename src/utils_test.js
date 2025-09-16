/**
 * Tests for utils.js
 * Tests text processing utilities
 */

// Load the utils.js file to populate window.AnsiUtils
import './utils.js';

// Test highlightSearchInHtml function
function testHighlightSearchInHtml() {
    console.log('Testing highlightSearchInHtml...');

    const { highlightSearchInHtml } = window.AnsiUtils;

    // Test basic highlighting
    const html1 = 'This is a test string';
    const result1 = highlightSearchInHtml(html1, 'test');
    const expected1 = 'This is a <mark class="search-highlight">test</mark> string';
    if (result1 !== expected1) {
        throw new Error(`Expected: ${expected1}, Got: ${result1}`);
    }

    // Test case insensitive
    const html2 = 'This is a TEST string';
    const result2 = highlightSearchInHtml(html2, 'test');
    const expected2 = 'This is a <mark class="search-highlight">TEST</mark> string';
    if (result2 !== expected2) {
        throw new Error(`Expected: ${expected2}, Got: ${result2}`);
    }

    // Test with HTML tags (should not highlight inside tags)
    const html3 = '<span class="test">This is a test</span>';
    const result3 = highlightSearchInHtml(html3, 'test');
    const expected3 = '<span class="test">This is a <mark class="search-highlight">test</mark></span>';
    if (result3 !== expected3) {
        throw new Error(`Expected: ${expected3}, Got: ${result3}`);
    }

    // Test empty search term
    const html4 = 'This is a test';
    const result4 = highlightSearchInHtml(html4, '');
    if (result4 !== html4) {
        throw new Error(`Empty search term should return original HTML`);
    }

    // Test special regex characters
    const html5 = 'Price: $10.99 (sale)';
    const result5 = highlightSearchInHtml(html5, '$10.99');
    const expected5 = 'Price: <mark class="search-highlight">$10.99</mark> (sale)';
    if (result5 !== expected5) {
        throw new Error(`Expected: ${expected5}, Got: ${result5}`);
    }

    console.log('✓ highlightSearchInHtml tests passed');
}

// Test stripAnsiCodes function
function testStripAnsiCodes() {
    console.log('Testing stripAnsiCodes...');

    const { stripAnsiCodes } = window.AnsiUtils;

    // Test basic ANSI code removal
    const text1 = '\u001b[31mRed text\u001b[0m';
    const result1 = stripAnsiCodes(text1);
    const expected1 = 'Red text';
    if (result1 !== expected1) {
        throw new Error(`Expected: "${expected1}", Got: "${result1}"`);
    }

    // Test multiple ANSI codes
    const text2 = '\u001b[1m\u001b[31mBold Red\u001b[0m\u001b[32m Green\u001b[0m';
    const result2 = stripAnsiCodes(text2);
    const expected2 = 'Bold Red Green';
    if (result2 !== expected2) {
        throw new Error(`Expected: "${expected2}", Got: "${result2}"`);
    }

    // Test text without ANSI codes
    const text3 = 'Plain text';
    const result3 = stripAnsiCodes(text3);
    if (result3 !== text3) {
        throw new Error(`Plain text should remain unchanged`);
    }

    // Test empty string
    const text4 = '';
    const result4 = stripAnsiCodes(text4);
    if (result4 !== text4) {
        throw new Error(`Empty string should remain empty`);
    }

    console.log('✓ stripAnsiCodes tests passed');
}

// Test that window.AnsiUtils is properly exported
function testExports() {
    console.log('Testing exports...');

    if (!window.AnsiUtils) {
        throw new Error('window.AnsiUtils not found');
    }

    if (typeof window.AnsiUtils.highlightSearchInHtml !== 'function') {
        throw new Error('highlightSearchInHtml not exported as function');
    }

    if (typeof window.AnsiUtils.stripAnsiCodes !== 'function') {
        throw new Error('stripAnsiCodes not exported as function');
    }

    console.log('✓ Exports test passed');
}

// Run all tests
function runAllTests() {
    try {
        testExports();
        testHighlightSearchInHtml();
        testStripAnsiCodes();
        console.log('All utils.js tests passed!');
    } catch (error) {
        console.error('Test failed:', error.message);
        throw error;
    }
}

// Run tests
runAllTests();