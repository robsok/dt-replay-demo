/**
 * Utility functions for the Digital Twin Dashboard
 * Common helper functions and utilities
 */

/**
 * Formatting utilities
 */
const DashboardUtils = {
    
    /**
     * Format numbers with appropriate units (K, M, B)
     */
    formatNumber: function(num) {
        if (num >= 1000000000) {
            return (num / 1000000000).toFixed(1) + 'B';
        } else if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        } else {
            return num.toString();
        }
    },
    
    /**
     * Format timestamps to human-readable format
     */
    formatTimestamp: function(timestamp) {
        const date = new Date(timestamp * 1000);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) {
            return 'Just now';
        } else if (diffMins < 60) {
            return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
        } else if (diffHours < 24) {
            return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
        } else if (diffDays < 7) {
            return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
        } else {
            return date.toLocaleDateString();
        }
    },
    
    /**
     * Format file sizes
     */
    formatFileSize: function(bytes) {
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let size = bytes;
        let unitIndex = 0;
        
        while (size >= 1024 && unitIndex < units.length - 1) {
            size /= 1024;
            unitIndex++;
        }
        
        return `${size.toFixed(1)} ${units[unitIndex]}`;
    },
    
    /**
     * Generate random colors for data visualization
     */
    generateColor: function(index) {
        const colors = [
            '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
            '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE',
            '#85C1E9', '#F8C471', '#82E0AA', '#F1948A'
        ];
        return colors[index % colors.length];
    },
    
    /**
     * Debounce function to limit function calls
     */
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    
    /**
     * Throttle function to limit function calls
     */
    throttle: function(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },
    
    /**
     * Deep clone an object
     */
    deepClone: function(obj) {
        if (obj === null || typeof obj !== 'object') return obj;
        if (obj instanceof Date) return new Date(obj.getTime());
        if (obj instanceof Array) return obj.map(item => this.deepClone(item));
        if (typeof obj === 'object') {
            const clonedObj = {};
            for (const key in obj) {
                if (obj.hasOwnProperty(key)) {
                    clonedObj[key] = this.deepClone(obj[key]);
                }
            }
            return clonedObj;
        }
    },
    
    /**
     * Check if element is visible in viewport
     */
    isInViewport: function(element) {
        const rect = element.getBoundingClientRect();
        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth)
        );
    },
    
    /**
     * Smooth scroll to element
     */
    scrollToElement: function(element, offset = 0) {
        const elementPosition = element.getBoundingClientRect().top + window.pageYOffset;
        const targetPosition = elementPosition - offset;
        
        window.scrollTo({
            top: targetPosition,
            behavior: 'smooth'
        });
    },
    
    /**
     * Copy text to clipboard
     */
    copyToClipboard: function(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(text);
        } else {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.opacity = '0';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            
            try {
                const successful = document.execCommand('copy');
                document.body.removeChild(textArea);
                return Promise.resolve(successful);
            } catch (err) {
                document.body.removeChild(textArea);
                return Promise.reject(err);
            }
        }
    },
    
    /**
     * Get URL parameters
     */
    getUrlParams: function() {
        const params = {};
        const searchParams = new URLSearchParams(window.location.search);
        for (const [key, value] of searchParams) {
            params[key] = value;
        }
        return params;
    },
    
    /**
     * Set URL parameter without page reload
     */
    setUrlParam: function(key, value) {
        const url = new URL(window.location);
        if (value) {
            url.searchParams.set(key, value);
        } else {
            url.searchParams.delete(key);
        }
        window.history.replaceState({}, '', url);
    },
    
    /**
     * Validate email address
     */
    isValidEmail: function(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    },
    
    /**
     * Generate UUID
     */
    generateUUID: function() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    },
    
    /**
     * Local storage helpers with error handling
     */
    storage: {
        set: function(key, value) {
            try {
                localStorage.setItem(key, JSON.stringify(value));
                return true;
            } catch (e) {
                console.error('Error saving to localStorage:', e);
                return false;
            }
        },
        
        get: function(key, defaultValue = null) {
            try {
                const item = localStorage.getItem(key);
                return item ? JSON.parse(item) : defaultValue;
            } catch (e) {
                console.error('Error reading from localStorage:', e);
                return defaultValue;
            }
        },
        
        remove: function(key) {
            try {
                localStorage.removeItem(key);
                return true;
            } catch (e) {
                console.error('Error removing from localStorage:', e);
                return false;
            }
        },
        
        clear: function() {
            try {
                localStorage.clear();
                return true;
            } catch (e) {
                console.error('Error clearing localStorage:', e);
                return false;
            }
        }
    },
    
    /**
     * Performance monitoring helpers
     */
    performance: {
        mark: function(name) {
            if (window.performance && window.performance.mark) {
                window.performance.mark(name);
            }
        },
        
        measure: function(name, startMark, endMark) {
            if (window.performance && window.performance.measure) {
                try {
                    window.performance.measure(name, startMark, endMark);
                    const measurement = window.performance.getEntriesByName(name)[0];
                    return measurement ? measurement.duration : null;
                } catch (e) {
                    console.warn('Performance measurement failed:', e);
                    return null;
                }
            }
            return null;
        },
        
        clearMarks: function(name) {
            if (window.performance && window.performance.clearMarks) {
                window.performance.clearMarks(name);
            }
        }
    },
    
    /**
     * Device and browser detection
     */
    device: {
        isMobile: function() {
            return window.innerWidth < 768;
        },
        
        isTablet: function() {
            return window.innerWidth >= 768 && window.innerWidth < 1024;
        },
        
        isDesktop: function() {
            return window.innerWidth >= 1024;
        },
        
        getTouchSupport: function() {
            return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
        },
        
        getScreenDensity: function() {
            return window.devicePixelRatio || 1;
        }
    },
    
    /**
     * Color utilities
     */
    color: {
        hexToRgb: function(hex) {
            const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
            return result ? {
                r: parseInt(result[1], 16),
                g: parseInt(result[2], 16),
                b: parseInt(result[3], 16)
            } : null;
        },
        
        rgbToHex: function(r, g, b) {
            return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
        },
        
        adjustBrightness: function(hex, percent) {
            const rgb = this.hexToRgb(hex);
            if (!rgb) return hex;
            
            const adjust = (color) => {
                const adjusted = Math.round(color * (100 + percent) / 100);
                return Math.max(0, Math.min(255, adjusted));
            };
            
            return this.rgbToHex(adjust(rgb.r), adjust(rgb.g), adjust(rgb.b));
        }
    }
};

// Make utilities available globally
window.DashboardUtils = DashboardUtils;

console.log('✅ Dashboard utilities loaded');