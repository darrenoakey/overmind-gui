/**
 * Virtual List Implementation
 * Layer 3: Efficiently renders only visible items using virtualization
 */

class VirtualList {
    constructor(container, options = {}) {
        this.container = container;
        this.options = {
            itemHeight: 24, // Default height
            overscan: 5, // Extra items to render outside viewport
            estimateHeight: true, // Dynamic height estimation
            ...options
        };
        
        // State
        this.items = [];
        this.visibleItems = [];
        this.scrollTop = 0;
        this.containerHeight = 0;
        this.totalHeight = 0;
        this.startIndex = 0;
        this.endIndex = 0;
        
        // Performance tracking
        this.renderCount = 0;
        this.lastRenderTime = 0;
        
        // Callbacks
        this.renderItem = options.renderItem || this.defaultRenderItem;
        this.onScroll = options.onScroll || (() => {});
        
        // DOM elements
        this.scrollContainer = null;
        this.viewport = null;
        
        // Height cache for variable height items
        this.heightCache = new Map();
        this.measuredHeights = new Map();
        
        this.init();
    }
    
    init() {
        // Create DOM structure
        this.container.innerHTML = `
            <div class="virtual-list-container" style="
                position: relative;
                width: 100%;
                height: 100%;
                overflow: auto;
                will-change: scroll-position;
            ">
                <div class="virtual-list-spacer" style="
                    position: relative;
                    width: 100%;
                "></div>
            </div>
        `;
        
        this.scrollContainer = this.container.querySelector('.virtual-list-container');
        this.viewport = this.container.querySelector('.virtual-list-spacer');
        
        // Bind events
        this.scrollContainer.addEventListener('scroll', this.handleScroll.bind(this), { passive: true });
        
        // Initial measurement
        this.measureContainer();
        
        // Setup ResizeObserver for container size changes
        if (window.ResizeObserver) {
            this.resizeObserver = new ResizeObserver(() => {
                this.measureContainer();
                this.updateVisibleItems();
            });
            this.resizeObserver.observe(this.container);
        }
    }
    
    measureContainer() {
        const rect = this.scrollContainer.getBoundingClientRect();
        this.containerHeight = rect.height;
    }
    
    handleScroll() {
        this.scrollTop = this.scrollContainer.scrollTop;
        this.updateVisibleItems();
        this.onScroll(this.scrollTop);
    }
    
    /**
     * Update the list with new items
     */
    setItems(items) {
        this.items = items;
        this.updateTotalHeight();
        this.updateVisibleItems();
    }
    
    /**
     * Calculate total height of all items
     */
    updateTotalHeight() {
        if (this.options.estimateHeight) {
            // Use cached heights or estimates
            this.totalHeight = 0;
            for (let i = 0; i < this.items.length; i++) {
                this.totalHeight += this.getItemHeight(i);
            }
        } else {
            // Fixed height
            this.totalHeight = this.items.length * this.options.itemHeight;
        }
        
        this.viewport.style.height = `${this.totalHeight}px`;
    }
    
    /**
     * Get height of item at index
     */
    getItemHeight(index) {
        if (this.measuredHeights.has(index)) {
            return this.measuredHeights.get(index);
        }
        
        if (this.heightCache.has(index)) {
            return this.heightCache.get(index);
        }
        
        // Use item's estimated height or default
        const item = this.items[index];
        return item?.estimatedHeight || this.options.itemHeight;
    }
    
    /**
     * Set measured height for an item
     */
    setItemHeight(index, height) {
        if (this.measuredHeights.get(index) !== height) {
            this.measuredHeights.set(index, height);
            this.updateTotalHeight();
        }
    }
    
    /**
     * Calculate which items should be visible
     */
    updateVisibleItems() {
        if (this.items.length === 0 || this.containerHeight === 0) {
            this.renderItems([]);
            return;
        }
        
        const scrollTop = this.scrollTop;
        const scrollBottom = scrollTop + this.containerHeight;
        
        // Find start index
        this.startIndex = this.findStartIndex(scrollTop);
        
        // Find end index
        this.endIndex = this.findEndIndex(scrollBottom, this.startIndex);
        
        // Add overscan
        const overscanStart = Math.max(0, this.startIndex - this.options.overscan);
        const overscanEnd = Math.min(this.items.length - 1, this.endIndex + this.options.overscan);
        
        // Create visible items array
        const visibleItems = [];
        let offsetY = this.getOffsetForIndex(overscanStart);
        
        for (let i = overscanStart; i <= overscanEnd; i++) {
            const item = this.items[i];
            if (item) {
                visibleItems.push({
                    index: i,
                    item: item,
                    offsetY: offsetY
                });
                offsetY += this.getItemHeight(i);
            }
        }
        
        this.visibleItems = visibleItems;
        this.renderItems(visibleItems);
    }
    
    /**
     * Find the start index for visible items
     */
    findStartIndex(scrollTop) {
        let index = 0;
        let offset = 0;
        
        while (index < this.items.length && offset < scrollTop) {
            offset += this.getItemHeight(index);
            index++;
        }
        
        return Math.max(0, index - 1);
    }
    
    /**
     * Find the end index for visible items
     */
    findEndIndex(scrollBottom, startIndex) {
        let index = startIndex;
        let offset = this.getOffsetForIndex(startIndex);
        
        while (index < this.items.length && offset < scrollBottom) {
            offset += this.getItemHeight(index);
            index++;
        }
        
        return Math.min(this.items.length - 1, index);
    }
    
    /**
     * Get vertical offset for item at index
     */
    getOffsetForIndex(index) {
        let offset = 0;
        for (let i = 0; i < index; i++) {
            offset += this.getItemHeight(i);
        }
        return offset;
    }
    
    /**
     * Render visible items to DOM
     */
    renderItems(visibleItems) {
        const startTime = performance.now();
        
        // Clear existing items
        this.viewport.innerHTML = '';
        
        // Render each visible item
        visibleItems.forEach(({ index, item, offsetY }) => {
            const element = this.renderItem(item, index);
            
            // Position the element
            element.style.position = 'absolute';
            element.style.top = `${offsetY}px`;
            element.style.left = '0';
            element.style.right = '0';
            element.style.contain = 'content'; // Layer 4 optimization
            
            // Add to viewport
            this.viewport.appendChild(element);
            
            // Measure actual height if needed
            if (this.options.estimateHeight) {
                const rect = element.getBoundingClientRect();
                if (rect.height > 0) {
                    this.setItemHeight(index, rect.height);
                }
            }
        });
        
        // Performance tracking
        this.renderCount++;
        this.lastRenderTime = performance.now() - startTime;
        
        if (this.lastRenderTime > 16) { // More than one frame
            console.warn(`Virtual list render took ${this.lastRenderTime.toFixed(2)}ms for ${visibleItems.length} items`);
        }
    }
    
    /**
     * Default item renderer
     */
    defaultRenderItem(item, index) {
        const element = document.createElement('div');
        element.className = 'virtual-list-item';
        element.textContent = item.toString();
        return element;
    }
    
    /**
     * Scroll to a specific item
     */
    scrollToIndex(index, align = 'auto') {
        if (index < 0 || index >= this.items.length) return;
        
        const itemOffset = this.getOffsetForIndex(index);
        const itemHeight = this.getItemHeight(index);
        
        let scrollTop;
        
        switch (align) {
            case 'start':
                scrollTop = itemOffset;
                break;
            case 'center':
                scrollTop = itemOffset - (this.containerHeight - itemHeight) / 2;
                break;
            case 'end':
                scrollTop = itemOffset - this.containerHeight + itemHeight;
                break;
            default: // 'auto'
                const currentTop = this.scrollTop;
                const currentBottom = currentTop + this.containerHeight;
                
                if (itemOffset < currentTop) {
                    scrollTop = itemOffset;
                } else if (itemOffset + itemHeight > currentBottom) {
                    scrollTop = itemOffset - this.containerHeight + itemHeight;
                } else {
                    return; // Item is already visible
                }
        }
        
        scrollTop = Math.max(0, Math.min(scrollTop, this.totalHeight - this.containerHeight));
        this.scrollContainer.scrollTop = scrollTop;
    }
    
    /**
     * Scroll to bottom
     */
    scrollToBottom() {
        this.scrollContainer.scrollTop = this.totalHeight;
    }
    
    /**
     * Get scroll position info
     */
    getScrollInfo() {
        return {
            scrollTop: this.scrollTop,
            scrollHeight: this.totalHeight,
            clientHeight: this.containerHeight,
            isAtBottom: this.scrollTop + this.containerHeight >= this.totalHeight - 10
        };
    }
    
    /**
     * Get performance stats
     */
    getStats() {
        return {
            totalItems: this.items.length,
            visibleItems: this.visibleItems.length,
            renderCount: this.renderCount,
            lastRenderTime: this.lastRenderTime,
            measuredHeights: this.measuredHeights.size
        };
    }
    
    /**
     * Cleanup resources
     */
    destroy() {
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
            this.resizeObserver = null;
        }
        
        this.heightCache.clear();
        this.measuredHeights.clear();
        this.items = [];
        this.visibleItems = [];
    }
}

// Export
window.VirtualList = VirtualList;