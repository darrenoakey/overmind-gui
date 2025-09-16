/**
 * Tests for search.js
 * Tests search functionality and navigation
 */

// Load the SearchManager class
import './search.js';

// Create mock DOM elements for testing
function createMockDOM() {
    // Create a mock container with children elements
    const mockContainer = {
        current: {
            children: [
                { scrollIntoView: function() { this.scrolledTo = true; } },
                { scrollIntoView: function() { this.scrolledTo = true; } },
                { scrollIntoView: function() { this.scrolledTo = true; } }
            ]
        }
    };
    return mockContainer;
}

// Test SearchManager constructor and initialization
function testSearchManagerConstructor() {
    console.log('Testing SearchManager constructor...');

    const searchManager = new window.SearchManager();

    if (searchManager.searchText !== '') {
        throw new Error('searchText should be empty initially');
    }

    if (searchManager.searchResults.length !== 0) {
        throw new Error('searchResults should be empty initially');
    }

    if (searchManager.currentSearchIndex !== -1) {
        throw new Error('currentSearchIndex should be -1 initially');
    }

    if (searchManager.outputRef !== null) {
        throw new Error('outputRef should be null initially');
    }

    console.log('✓ SearchManager constructor test passed');
}

// Test setOutputRef method
function testSetOutputRef() {
    console.log('Testing setOutputRef...');

    const searchManager = new window.SearchManager();
    const mockRef = createMockDOM();

    searchManager.setOutputRef(mockRef);

    if (searchManager.outputRef !== mockRef) {
        throw new Error('outputRef should be set to the provided reference');
    }

    console.log('✓ setOutputRef test passed');
}

// Test updateSearch with empty search text
function testUpdateSearchEmpty() {
    console.log('Testing updateSearch with empty text...');

    const searchManager = new window.SearchManager();
    const mockOutput = [
        { cleanText: 'line one' },
        { cleanText: 'line two' },
        { cleanText: 'line three' }
    ];

    const result = searchManager.updateSearch('', mockOutput);

    if (result.results.length !== 0) {
        throw new Error('Empty search should return no results');
    }

    if (result.currentIndex !== -1) {
        throw new Error('Empty search should have currentIndex -1');
    }

    if (searchManager.searchText !== '') {
        throw new Error('searchText should be empty');
    }

    console.log('✓ updateSearch empty test passed');
}

// Test updateSearch with valid search text
function testUpdateSearchWithResults() {
    console.log('Testing updateSearch with search text...');

    const searchManager = new window.SearchManager();
    const mockRef = createMockDOM();
    searchManager.setOutputRef(mockRef);

    const mockOutput = [
        { cleanText: 'error occurred' },
        { cleanText: 'info message' },
        { cleanText: 'another error' },
        { cleanText: 'warning message' }
    ];

    const result = searchManager.updateSearch('error', mockOutput);

    if (result.results.length !== 2) {
        throw new Error(`Expected 2 results, got ${result.results.length}`);
    }

    if (!result.results.includes(0) || !result.results.includes(2)) {
        throw new Error('Results should include indices 0 and 2');
    }

    if (result.currentIndex !== 0) {
        throw new Error('currentIndex should be 0 for new search');
    }

    if (searchManager.searchText !== 'error') {
        throw new Error('searchText should be set to "error"');
    }

    console.log('✓ updateSearch with results test passed');
}

// Test case insensitive search
function testUpdateSearchCaseInsensitive() {
    console.log('Testing case insensitive search...');

    const searchManager = new window.SearchManager();
    const mockOutput = [
        { cleanText: 'ERROR occurred' },
        { cleanText: 'Info Message' },
        { cleanText: 'Another Error' }
    ];

    const result = searchManager.updateSearch('error', mockOutput);

    if (result.results.length !== 2) {
        throw new Error(`Expected 2 results for case insensitive search, got ${result.results.length}`);
    }

    console.log('✓ Case insensitive search test passed');
}

// Test nextSearch method
function testNextSearch() {
    console.log('Testing nextSearch...');

    const searchManager = new window.SearchManager();
    const mockRef = createMockDOM();
    searchManager.setOutputRef(mockRef);

    const mockOutput = [
        { cleanText: 'error one' },
        { cleanText: 'info' },
        { cleanText: 'error two' },
        { cleanText: 'error three' }
    ];

    // First update search to get results
    searchManager.updateSearch('error', mockOutput);

    // Test next search
    const result1 = searchManager.nextSearch();
    if (!result1) {
        throw new Error('nextSearch should return true when results exist');
    }

    if (searchManager.currentSearchIndex !== 1) {
        throw new Error('currentSearchIndex should be 1 after first nextSearch');
    }

    // Test wrapping around
    searchManager.nextSearch(); // Index should be 2
    const result2 = searchManager.nextSearch(); // Should wrap to 0

    if (searchManager.currentSearchIndex !== 0) {
        throw new Error('nextSearch should wrap around to 0');
    }

    console.log('✓ nextSearch test passed');
}

// Test prevSearch method
function testPrevSearch() {
    console.log('Testing prevSearch...');

    const searchManager = new window.SearchManager();
    const mockRef = createMockDOM();
    searchManager.setOutputRef(mockRef);

    const mockOutput = [
        { cleanText: 'error one' },
        { cleanText: 'info' },
        { cleanText: 'error two' },
        { cleanText: 'error three' }
    ];

    // First update search to get results
    searchManager.updateSearch('error', mockOutput);

    // Test previous search (should wrap to last)
    const result1 = searchManager.prevSearch();
    if (!result1) {
        throw new Error('prevSearch should return true when results exist');
    }

    if (searchManager.currentSearchIndex !== 2) {
        throw new Error('prevSearch should wrap to last index (2)');
    }

    // Test normal previous
    searchManager.prevSearch();
    if (searchManager.currentSearchIndex !== 1) {
        throw new Error('prevSearch should decrement index to 1');
    }

    console.log('✓ prevSearch test passed');
}

// Test getSearchState method
function testGetSearchState() {
    console.log('Testing getSearchState...');

    const searchManager = new window.SearchManager();
    const mockOutput = [
        { cleanText: 'error one' },
        { cleanText: 'info' }
    ];

    searchManager.updateSearch('error', mockOutput);

    const state = searchManager.getSearchState();

    if (state.searchText !== 'error') {
        throw new Error('searchText in state should be "error"');
    }

    if (state.results.length !== 1) {
        throw new Error('results in state should have length 1');
    }

    if (state.currentIndex !== 0) {
        throw new Error('currentIndex in state should be 0');
    }

    if (!state.hasResults) {
        throw new Error('hasResults should be true');
    }

    if (state.resultCount !== 1) {
        throw new Error('resultCount should be 1');
    }

    console.log('✓ getSearchState test passed');
}

// Test clearSearch method
function testClearSearch() {
    console.log('Testing clearSearch...');

    const searchManager = new window.SearchManager();
    const mockOutput = [{ cleanText: 'error' }];

    // First set up some search state
    searchManager.updateSearch('error', mockOutput);

    // Then clear it
    searchManager.clearSearch();

    if (searchManager.searchText !== '') {
        throw new Error('searchText should be empty after clear');
    }

    if (searchManager.searchResults.length !== 0) {
        throw new Error('searchResults should be empty after clear');
    }

    if (searchManager.currentSearchIndex !== -1) {
        throw new Error('currentSearchIndex should be -1 after clear');
    }

    console.log('✓ clearSearch test passed');
}

// Run all tests
function runAllTests() {
    try {
        testSearchManagerConstructor();
        testSetOutputRef();
        testUpdateSearchEmpty();
        testUpdateSearchWithResults();
        testUpdateSearchCaseInsensitive();
        testNextSearch();
        testPrevSearch();
        testGetSearchState();
        testClearSearch();
        console.log('All SearchManager tests passed!');
    } catch (error) {
        console.error('Test failed:', error.message);
        throw error;
    }
}

// Run tests
runAllTests();