// Search functionality for the output

class SearchManager {
    constructor() {
        this.searchText = '';
        this.searchResults = [];
        this.currentSearchIndex = -1;
        this.outputRef = null;
        this.lastSearchedLineContent = null; // Track content of current search result
    }

    setOutputRef(ref) {
        this.outputRef = ref;
    }

    // Update search results based on text and filtered output
    updateSearch(searchText, filteredOutput) {
        this.searchText = searchText;
        
        if (!searchText) {
            this.searchResults = [];
            this.currentSearchIndex = -1;
            this.lastSearchedLineContent = null;
            return { results: [], currentIndex: -1 };
        }
        
        const results = [];
        const searchLower = searchText.toLowerCase();
        
        filteredOutput.forEach((line, index) => {
            // Search in clean text without ANSI codes
            const cleanLine = window.AnsiUtils.stripAnsiCodes(line);
            if (cleanLine.toLowerCase().includes(searchLower)) {
                results.push(index);
            }
        });
        
        // If we had a previous search position, try to maintain it
        if (this.currentSearchIndex >= 0 && this.lastSearchedLineContent && results.length > 0) {
            // Try to find the same line content in the new results
            let newIndex = -1;
            for (let i = 0; i < results.length; i++) {
                const resultLineIndex = results[i];
                if (resultLineIndex < filteredOutput.length) {
                    const lineContent = window.AnsiUtils.stripAnsiCodes(filteredOutput[resultLineIndex]);
                    if (lineContent === this.lastSearchedLineContent) {
                        newIndex = i;
                        break;
                    }
                }
            }
            
            // If we found the same content, use that position
            if (newIndex >= 0) {
                this.searchResults = results;
                this.currentSearchIndex = newIndex;
            } else {
                // If we can't find the exact content, try to maintain relative position
                const relativePosition = this.currentSearchIndex / this.searchResults.length;
                this.searchResults = results;
                this.currentSearchIndex = Math.min(
                    Math.floor(relativePosition * results.length),
                    results.length - 1
                );
            }
        } else {
            // No previous position, start from beginning
            this.searchResults = results;
            this.currentSearchIndex = results.length > 0 ? 0 : -1;
        }
        
        // Update the tracked content for the current position
        this._updateTrackedContent(filteredOutput);
        
        // Scroll to current result if we have one
        if (this.currentSearchIndex >= 0) {
            this.scrollToCurrentResult();
        }
        
        return { 
            results: this.searchResults, 
            currentIndex: this.currentSearchIndex 
        };
    }

    // Navigate to next search result
    nextSearch() {
        if (this.searchResults.length === 0) return false;
        
        this.currentSearchIndex = (this.currentSearchIndex + 1) % this.searchResults.length;
        this.scrollToCurrentResult();
        this._updateTrackedContent();
        return true;
    }

    // Navigate to previous search result
    prevSearch() {
        if (this.searchResults.length === 0) return false;
        
        this.currentSearchIndex = this.currentSearchIndex <= 0 ? 
            this.searchResults.length - 1 : 
            this.currentSearchIndex - 1;
        this.scrollToCurrentResult();
        this._updateTrackedContent();
        return true;
    }

    // Update the tracked content for position maintenance
    _updateTrackedContent(filteredOutput = null) {
        if (this.currentSearchIndex >= 0 && this.outputRef?.current) {
            if (filteredOutput) {
                const resultLineIndex = this.searchResults[this.currentSearchIndex];
                if (resultLineIndex < filteredOutput.length) {
                    this.lastSearchedLineContent = window.AnsiUtils.stripAnsiCodes(
                        filteredOutput[resultLineIndex]
                    );
                }
            }
        }
    }

    // Scroll to the current search result
    scrollToCurrentResult() {
        if (this.currentSearchIndex < 0 || !this.outputRef?.current) return;
        
        const lineElements = this.outputRef.current.children;
        const targetLineIndex = this.searchResults[this.currentSearchIndex];
        const lineElement = lineElements[targetLineIndex];
        
        if (lineElement) {
            // Smooth scroll to the element
            lineElement.scrollIntoView({ 
                behavior: 'smooth', 
                block: 'center',
                inline: 'nearest'
            });
        }
    }

    // Get current search state
    getSearchState() {
        return {
            searchText: this.searchText,
            results: this.searchResults,
            currentIndex: this.currentSearchIndex,
            hasResults: this.searchResults.length > 0,
            resultCount: this.searchResults.length
        };
    }

    // Check if a line index should be highlighted
    isLineHighlighted(lineIndex) {
        return this.searchResults.includes(lineIndex) && 
               this.searchResults[this.currentSearchIndex] === lineIndex;
    }
}

// Export for use in other files
window.SearchManager = SearchManager;
