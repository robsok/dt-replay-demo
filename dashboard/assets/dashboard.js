/**
 * Dashboard JavaScript functionality
 * This file contains client-side enhancements for the Digital Twin Dashboard
 */

// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Dashboard JavaScript loaded');
    
    // Initialize dashboard functionality
    initializeDashboard();
    
    // Set up keyboard shortcuts
    setupKeyboardShortcuts();
    
    // Initialize tooltips and enhancements
    initializeEnhancements();
});

/**
 * Initialize main dashboard functionality
 */
function initializeDashboard() {
    // Add smooth scrolling to all internal links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });
    
    // Add loading states to buttons
    enhanceButtons();
    
    // Monitor connection status
    monitorConnectionStatus();
}

/**
 * Setup keyboard shortcuts for better UX
 */
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(event) {
        // Only trigger shortcuts when not typing in inputs
        if (event.target.tagName.toLowerCase() === 'input' || 
            event.target.tagName.toLowerCase() === 'textarea') {
            return;
        }
        
        // Ctrl/Cmd + R: Refresh data (prevent default page refresh)
        if ((event.ctrlKey || event.metaKey) && event.key === 'r') {
            event.preventDefault();
            refreshDashboard();
        }
        
        // 'W' key: Switch to Week view
        if (event.key.toLowerCase() === 'w') {
            switchZoomLevel('Week');
        }
        
        // 'M' key: Switch to Month view
        if (event.key.toLowerCase() === 'm') {
            switchZoomLevel('Month');
        }
        
        // 'Q' key: Switch to Quarter view
        if (event.key.toLowerCase() === 'q') {
            switchZoomLevel('Quarter');
        }
        
        // 'Y' key: Switch to Year view
        if (event.key.toLowerCase() === 'y') {
            switchZoomLevel('Year');
        }
        
        // Arrow keys for navigation
        if (event.key === 'ArrowLeft') {
            clickButton('prev-button');
        }
        if (event.key === 'ArrowRight') {
            clickButton('next-button');
        }
        if (event.key === 'Home') {
            clickButton('latest-button');
        }
    });
}

/**
 * Initialize UI enhancements and tooltips
 */
function initializeEnhancements() {
    // Add tooltips to counter cards
    addCounterTooltips();
    
    // Add visual feedback for interactions
    addVisualFeedback();
    
    // Initialize resize handlers
    setupResizeHandlers();
    
    // Add accessibility enhancements
    enhanceAccessibility();
}

/**
 * Add tooltips to counter cards for better UX
 */
function addCounterTooltips() {
    // Find all counter cards and add hover information
    const counterCards = document.querySelectorAll('.counter-card');
    counterCards.forEach(card => {
        const title = card.querySelector('.counter-title');
        const value = card.querySelector('.counter-value');
        
        if (title && value) {
            const swimlaneName = title.textContent.trim();
            const count = value.textContent.trim();
            
            card.setAttribute('title', 
                `${swimlaneName}: ${count} events\nClick to see detailed breakdown`
            );
            
            // Add click handler for future detailed view
            card.addEventListener('click', function() {
                console.log(`Clicked ${swimlaneName} counter with ${count} events`);
                // Future: Show detailed breakdown modal
            });
        }
    });
}

/**
 * Add visual feedback for button interactions
 */
function addVisualFeedback() {
    // Add ripple effect to navigation buttons
    const navButtons = document.querySelectorAll('.nav-button');
    navButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            createRippleEffect(e, this);
        });
    });
    
    // Add loading states
    const allButtons = document.querySelectorAll('button');
    allButtons.forEach(button => {
        button.addEventListener('click', function() {
            if (!this.classList.contains('loading')) {
                this.classList.add('loading');
                setTimeout(() => {
                    this.classList.remove('loading');
                }, 1000); // Remove loading state after 1 second
            }
        });
    });
}

/**
 * Create ripple effect for button clicks
 */
function createRippleEffect(event, element) {
    const ripple = document.createElement('span');
    const rect = element.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const x = event.clientX - rect.left - size / 2;
    const y = event.clientY - rect.top - size / 2;
    
    ripple.style.width = ripple.style.height = size + 'px';
    ripple.style.left = x + 'px';
    ripple.style.top = y + 'px';
    ripple.classList.add('ripple');
    
    element.appendChild(ripple);
    
    setTimeout(() => {
        ripple.remove();
    }, 600);
}

/**
 * Monitor connection status and show indicators
 */
function monitorConnectionStatus() {
    // Monitor online/offline status
    window.addEventListener('online', function() {
        showConnectionStatus('online', '🟢 Connected');
    });
    
    window.addEventListener('offline', function() {
        showConnectionStatus('offline', '🔴 Disconnected');
    });
    
    // Check initial status
    if (navigator.onLine) {
        showConnectionStatus('online', '🟢 Connected');
    } else {
        showConnectionStatus('offline', '🔴 Disconnected');
    }
}

/**
 * Show connection status message
 */
function showConnectionStatus(status, message) {
    // Create or update status indicator
    let statusEl = document.getElementById('connection-status');
    if (!statusEl) {
        statusEl = document.createElement('div');
        statusEl.id = 'connection-status';
        statusEl.style.cssText = `
            position: fixed;
            top: 10px;
            right: 10px;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
            z-index: 10000;
            transition: all 0.3s ease;
        `;
        document.body.appendChild(statusEl);
    }
    
    statusEl.textContent = message;
    statusEl.className = `connection-${status}`;
    
    if (status === 'online') {
        statusEl.style.backgroundColor = 'rgba(72, 187, 120, 0.9)';
        statusEl.style.color = 'white';
    } else {
        statusEl.style.backgroundColor = 'rgba(245, 101, 101, 0.9)';
        statusEl.style.color = 'white';
    }
    
    // Auto-hide after 3 seconds if online
    if (status === 'online') {
        setTimeout(() => {
            statusEl.style.opacity = '0';
            setTimeout(() => {
                if (statusEl.parentNode) {
                    statusEl.remove();
                }
            }, 300);
        }, 3000);
    }
}

/**
 * Setup window resize handlers
 */
function setupResizeHandlers() {
    let resizeTimeout;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(function() {
            console.log('Window resized, adjusting layout...');
            // Future: Trigger Plotly relayout for graphs
            adjustLayoutForScreenSize();
        }, 250);
    });
}

/**
 * Adjust layout based on screen size
 */
function adjustLayoutForScreenSize() {
    const isMobile = window.innerWidth < 768;
    const controlsPanels = document.querySelectorAll('.controls-panel');
    
    controlsPanels.forEach(panel => {
        if (isMobile) {
            panel.classList.add('mobile-layout');
        } else {
            panel.classList.remove('mobile-layout');
        }
    });
}

/**
 * Enhance accessibility features
 */
function enhanceAccessibility() {
    // Add ARIA labels to interactive elements
    const counterCards = document.querySelectorAll('.counter-card');
    counterCards.forEach((card, index) => {
        card.setAttribute('role', 'button');
        card.setAttribute('tabindex', '0');
        card.setAttribute('aria-label', `Counter card ${index + 1}`);
        
        // Add keyboard navigation
        card.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.click();
            }
        });
    });
    
    // Add focus indicators
    const focusableElements = document.querySelectorAll(
        'button, [tabindex], .counter-card, .Select-control'
    );
    focusableElements.forEach(el => {
        el.addEventListener('focus', function() {
            this.setAttribute('data-focused', 'true');
        });
        el.addEventListener('blur', function() {
            this.removeAttribute('data-focused');
        });
    });
}

/**
 * Utility functions for Dash integration
 */

/**
 * Switch zoom level for the active project
 */
function switchZoomLevel(level) {
    // Find the active tab and its zoom dropdown
    const activeTab = document.querySelector('.tab-content [role="tabpanel"][aria-hidden="false"]');
    if (activeTab) {
        const zoomDropdown = activeTab.querySelector('[id*="zoom-dropdown"]');
        if (zoomDropdown) {
            // Trigger Dash callback to change zoom level
            console.log(`Switching to ${level} view`);
            // Note: This would require integration with Dash's callback system
            // For now, just log the action
        }
    }
}

/**
 * Click a button by partial ID match
 */
function clickButton(partialId) {
    const button = document.querySelector(`[id*="${partialId}"]`);
    if (button && !button.disabled) {
        button.click();
        console.log(`Clicked ${partialId} button`);
    }
}

/**
 * Refresh dashboard data
 */
function refreshDashboard() {
    console.log('🔄 Refreshing dashboard data...');
    // Future: Trigger manual refresh of all components
    showNotification('Refreshing data...', 'info');
}

/**
 * Show notification to user
 */
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 12px 16px;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 500;
        z-index: 10000;
        animation: slideIn 0.3s ease;
        max-width: 300px;
    `;
    
    // Set colors based on type
    const colors = {
        info: { bg: 'rgba(78, 205, 196, 0.9)', color: 'white' },
        success: { bg: 'rgba(72, 187, 120, 0.9)', color: 'white' },
        warning: { bg: 'rgba(237, 137, 54, 0.9)', color: 'white' },
        error: { bg: 'rgba(245, 101, 101, 0.9)', color: 'white' }
    };
    
    const colorScheme = colors[type] || colors.info;
    notification.style.backgroundColor = colorScheme.bg;
    notification.style.color = colorScheme.color;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 300);
    }, 3000);
}

// Add slide animations to CSS if not present
if (!document.querySelector('#js-animations')) {
    const style = document.createElement('style');
    style.id = 'js-animations';
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
        
        .ripple {
            position: absolute;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.3);
            pointer-events: none;
            animation: rippleEffect 0.6s ease-out;
        }
        
        @keyframes rippleEffect {
            from { transform: scale(0); opacity: 1; }
            to { transform: scale(1); opacity: 0; }
        }
        
        .loading {
            position: relative;
            pointer-events: none;
        }
        
        .loading::after {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 16px;
            height: 16px;
            margin: -8px 0 0 -8px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-top: 2px solid white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        [data-focused="true"] {
            outline: 2px solid #4ECDC4;
            outline-offset: 2px;
        }
        
        .mobile-layout > div {
            display: block !important;
            margin: 10px 0 !important;
        }
    `;
    document.head.appendChild(style);
}

console.log('✅ Dashboard JavaScript initialization complete');