// React components for the Overmind GUI

const { useState, useEffect, useRef, useCallback } = React;

// Component to render HTML safely with ANSI codes
const AnsiText = ({ children }) => {
    const html = window.AnsiUtils.ansiToHtml(children);
    return React.createElement('span', { 
        dangerouslySetInnerHTML: { __html: html } 
    });
};

// Loading screen component
const LoadingScreen = () => {
    return React.createElement('div', { className: 'loading' },
        React.createElement('h1', null, 'Connecting to Overmind...'),
        React.createElement('div', { className: 'spinner' }),
        React.createElement('p', { 
            style: { marginTop: '20px', opacity: 0.8 } 
        }, 'Make sure Overmind is running and accessible')
    );
};

// Error banner component
const ErrorBanner = ({ status, error }) => {
    if (status !== 'failed') return null;
    
    return React.createElement('div', { className: 'error-banner' },
        React.createElement('div', { className: 'error-content' },
            React.createElement('span', { className: 'error-icon' }, '⚠️'),
            React.createElement('div', { className: 'error-text' },
                React.createElement('strong', null, 'Overmind Failed to Start'),
                React.createElement('div', { className: 'error-detail' }, error)
            )
        )
    );
};

// Process bar component
const ProcessBar = ({ processes, onToggleProcess, onContextMenu }) => {
    const processEntries = Object.entries(processes);
    
    if (processEntries.length === 0) {
        return React.createElement('div', { className: 'process-bar' },
            React.createElement('div', { 
                style: { color: 'rgba(255,255,255,0.8)', fontStyle: 'italic' } 
            }, 'No processes loaded. Make sure there\'s a Procfile in the current directory.')
        );
    }
    
    return React.createElement('div', { className: 'process-bar' },
        ...processEntries.map(([name, process]) =>
            React.createElement('div', {
                key: name,
                className: `process-button ${process.selected ? 'selected' : ''} ${process.status}`,
                onClick: () => onToggleProcess(name),
                onContextMenu: (e) => onContextMenu(e, name),
                title: `${name} - ${process.status} (Click to toggle, Right-click for actions)`
            },
                React.createElement('div', { className: 'process-name' }, name)
            )
        )
    );
};

// Filter controls component
const FilterControls = ({ 
    filterText, 
    onFilterChange, 
    searchText, 
    onSearchChange, 
    searchManager,
    onNextSearch,
    onPrevSearch,
    onClearFilter,
    onClearSearch 
}) => {
    const searchState = searchManager.getSearchState();
    
    return React.createElement('div', { className: 'filters' },
        React.createElement('div', { className: 'filter-group' },
            React.createElement('label', null, 'Filter:'),
            React.createElement('input', {
                type: 'text',
                className: 'filter-input',
                placeholder: 'Filter output by text...',
                value: filterText,
                onChange: (e) => onFilterChange(e.target.value),
                title: 'Filter output lines containing this text'
            }),
            filterText && React.createElement('button', {
                className: 'btn',
                onClick: onClearFilter,
                title: 'Clear filter'
            }, '✕')
        ),
        
        React.createElement('div', { className: 'filter-group' },
            React.createElement('label', null, 'Search:'),
            React.createElement('input', {
                type: 'text',
                className: 'filter-input',
                placeholder: 'Search and navigate...',
                value: searchText,
                onChange: (e) => onSearchChange(e.target.value),
                title: 'Search through filtered output (Ctrl/Cmd+F, Esc to clear)'
            }),
            React.createElement('div', { className: 'search-nav' },
                React.createElement('button', {
                    className: 'search-btn',
                    onClick: onPrevSearch,
                    disabled: !searchState.hasResults,
                    title: 'Previous match'
                }, '◀'),
                React.createElement('button', {
                    className: 'search-btn',
                    onClick: onNextSearch,
                    disabled: !searchState.hasResults,
                    title: 'Next match'
                }, '▶')
            ),
            searchText && React.createElement(React.Fragment, null,
                React.createElement('div', { className: 'search-count' },
                    searchState.hasResults ? 
                        `${searchState.currentIndex + 1} of ${searchState.resultCount}` : 
                        'No matches'
                ),
                React.createElement('button', {
                    className: 'btn',
                    onClick: onClearSearch,
                    title: 'Clear search (Esc)'
                }, '✕')
            )
        )
    );
};

// Output display component
const OutputDisplay = ({ 
    filteredOutput, 
    output, 
    outputRef, 
    onScroll, 
    boundToEnd, 
    onScrollToBottom,
    searchManager 
}) => {
    const searchState = searchManager.getSearchState();
    
    if (filteredOutput.length === 0) {
        return React.createElement('div', { className: 'output-container' },
            React.createElement('div', { 
                className: 'output', 
                ref: outputRef,
                onScroll: onScroll 
            },
                React.createElement('div', {
                    style: {
                        color: '#6c757d',
                        fontStyle: 'italic',
                        textAlign: 'center',
                        marginTop: '50px'
                    }
                }, output.length === 0 ? 
                    'No output yet. Waiting for process output...' :
                    'No output matches current filter/selection.')
            )
        );
    }
    
    return React.createElement('div', { className: 'output-container' },
        React.createElement('div', { 
            className: 'output', 
            ref: outputRef,
            onScroll: onScroll 
        },
            ...filteredOutput.map((line, index) =>
                React.createElement('div', {
                    key: index,
                    className: `output-line ${searchManager.isLineHighlighted(index) ? 'highlight' : ''}`
                },
                    React.createElement(AnsiText, null, line)
                )
            )
        ),
        
        // Show "new output" button when not bound to end and there's output
        !boundToEnd && output.length > 0 && React.createElement('div', {
            style: {
                position: 'absolute',
                bottom: '20px',
                right: '20px',
                background: 'rgba(0,123,255,0.9)',
                color: 'white',
                padding: '8px 12px',
                borderRadius: '20px',
                cursor: 'pointer',
                fontSize: '12px',
                boxShadow: '0 2px 10px rgba(0,0,0,0.2)',
                animation: 'bounce 2s infinite'
            },
            onClick: onScrollToBottom,
            title: 'Click to scroll to bottom and follow new output'
        }, '↓ New output')
    );
};

// Footer stats and actions component
const Footer = ({ 
    stats, 
    filteredOutput, 
    output, 
    onSelectAll, 
    onDeselectAll, 
    onClearOutput 
}) => {
    return React.createElement('div', { className: 'footer' },
        React.createElement('div', { className: 'stats' },
            React.createElement('span', null, `Processes: ${stats.total || 0}`),
            React.createElement('span', null, `Running: ${stats.running || 0}`),
            React.createElement('span', null, `Selected: ${stats.selected || 0}`),
            React.createElement('span', null, `Output Lines: ${filteredOutput.length}`),
            React.createElement('span', null, `Total Lines: ${output.length}`)
        ),
        React.createElement('div', { className: 'action-buttons' },
            React.createElement('button', {
                className: 'btn',
                onClick: onSelectAll,
                title: 'Select all processes for output'
            }, 'Select All'),
            React.createElement('button', {
                className: 'btn',
                onClick: onDeselectAll,
                title: 'Deselect all processes'
            }, 'Select None'),
            React.createElement('button', {
                className: 'btn btn-danger',
                onClick: onClearOutput,
                title: 'Clear all output (Ctrl/Cmd+K)'
            }, 'Clear Output')
        )
    );
};

// Context menu component
const ContextMenu = ({ contextMenu, onProcessAction }) => {
    if (!contextMenu) return null;
    
    return React.createElement('div', {
        className: 'context-menu',
        style: { left: contextMenu.x, top: contextMenu.y }
    },
        React.createElement('div', {
            className: 'context-menu-item',
            onClick: () => onProcessAction(contextMenu.processName, 'start')
        }, '🟢 Start'),
        React.createElement('div', {
            className: 'context-menu-item',
            onClick: () => onProcessAction(contextMenu.processName, 'stop')
        }, '🛑 Stop'),
        React.createElement('div', {
            className: 'context-menu-item',
            onClick: () => onProcessAction(contextMenu.processName, 'restart')
        }, '🔄 Restart')
    );
};

// Export components
window.Components = {
    AnsiText,
    LoadingScreen,
    ErrorBanner,
    ProcessBar,
    FilterControls,
    OutputDisplay,
    Footer,
    ContextMenu
};
