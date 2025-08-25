/**
 * Client-side configuration for the Digital Twin Dashboard
 * Contains settings and constants used by JavaScript modules
 */

window.DashboardConfig = {
    
    // Application settings
    app: {
        name: 'Lab Digital Twin Dashboard',
        version: '1.0.0',
        refreshInterval: 5000, // 5 seconds
        animationDuration: 300, // milliseconds
        debounceDelay: 250, // milliseconds for search/filter inputs
        notificationTimeout: 3000 // 3 seconds
    },
    
    // Theme configuration
    theme: {
        primaryColor: '#4ECDC4',
        secondaryColor: '#44A08D',
        backgroundColor: '#1a202c',
        surfaceColor: '#2d3748',
        
        // Status colors
        colors: {
            success: '#48BB78',
            warning: '#ED8936', 
            error: '#F56565',
            info: '#4299E1',
            
            // Project-specific colors
            projects: {
                'RM43971': '#4ECDC4', // WEx1
                'RM44125': '#45B7D1', // WEx2  
                'RM43875': '#96CEB4'  // General
            }
        },
        
        // Font settings
        fonts: {
            primary: "'Segoe UI', 'Roboto', -apple-system, BlinkMacSystemFont, sans-serif",
            monospace: "'Fira Code', 'Monaco', 'Consolas', monospace"
        }
    },
    
    // Chart and visualization settings
    charts: {
        defaultHeight: 400,
        colors: ['#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD'],
        
        // Timeline settings
        timeline: {
            minHeight: 100,
            maxHeight: 800,
            swimlaneHeight: 80,
            weekendOpacity: 0.15,
            holidayOpacity: 0.2
        },
        
        // Animation settings
        transitions: {
            duration: 750,
            easing: 'cubic-bezier(0.4, 0, 0.2, 1)'
        }
    },
    
    // Keyboard shortcuts
    shortcuts: {
        refresh: ['ctrl+r', 'cmd+r'],
        weekView: ['w'],
        monthView: ['m'], 
        quarterView: ['q'],
        yearView: ['y'],
        previousPeriod: ['ArrowLeft'],
        nextPeriod: ['ArrowRight'],
        latestPeriod: ['Home'],
        
        // Project switching
        project1: ['1'],
        project2: ['2'],
        project3: ['3']
    },
    
    // API and data settings
    api: {
        baseUrl: window.location.origin,
        timeout: 30000, // 30 seconds
        retryAttempts: 3,
        retryDelay: 1000 // 1 second
    },
    
    // Local storage keys
    storage: {
        userPreferences: 'dt_dashboard_preferences',
        lastProject: 'dt_last_project',
        zoomLevel: 'dt_zoom_level',
        timeReference: 'dt_time_reference',
        dashboardSettings: 'dt_dashboard_settings'
    },
    
    // Feature flags
    features: {
        keyboardShortcuts: true,
        notifications: true,
        autoRefresh: true,
        connectionMonitoring: true,
        performanceMonitoring: false, // Disable in production
        debugMode: false,
        
        // Experimental features
        experimental: {
            voiceCommands: false,
            gestureNavigation: false,
            predictiveLoading: false
        }
    },
    
    // UI settings
    ui: {
        // Responsive breakpoints (px)
        breakpoints: {
            mobile: 768,
            tablet: 1024,
            desktop: 1200,
            wide: 1600
        },
        
        // Component settings
        components: {
            counterCards: {
                minWidth: 75,
                maxWidth: 200,
                animationDelay: 100 // stagger animation
            },
            
            dropdown: {
                maxHeight: 300,
                zIndex: 9999
            },
            
            tooltip: {
                delay: 500, // milliseconds
                maxWidth: 250
            }
        },
        
        // Layout settings
        layout: {
            headerHeight: 120,
            sidebarWidth: 250,
            footerHeight: 60,
            contentPadding: 20
        }
    },
    
    // Performance thresholds
    performance: {
        // Warning thresholds (milliseconds)
        slowRender: 1000,
        slowInteraction: 100,
        
        // Memory usage thresholds (MB)
        memoryWarning: 100,
        memoryCritical: 200,
        
        // Network thresholds
        slowConnection: 3000, // 3G equivalent
        offlineDetection: true
    },
    
    // Accessibility settings
    accessibility: {
        focusVisible: true,
        reducedMotion: false, // Will be set based on user preference
        highContrast: false,
        largeText: false,
        
        // ARIA settings
        announcements: true,
        liveRegions: true,
        
        // Keyboard navigation
        tabOrder: true,
        skipLinks: true
    },
    
    // Development and debugging
    debug: {
        enabled: false, // Set to true in development
        logLevel: 'warn', // 'debug', 'info', 'warn', 'error'
        showPerformanceMetrics: false,
        enableReactDevTools: false
    },
    
    // Data format settings
    formats: {
        date: 'YYYY-MM-DD',
        time: 'HH:mm:ss',
        datetime: 'YYYY-MM-DD HH:mm:ss',
        timezone: 'Australia/Perth', // Adjust for your location
        
        // Number formatting
        numbers: {
            decimals: 2,
            thousandsSeparator: ',',
            decimalSeparator: '.',
            currency: 'AUD'
        }
    },
    
    // Integration settings
    integrations: {
        mqtt: {
            reconnectInterval: 5000,
            keepAliveInterval: 60000
        },
        
        influxdb: {
            maxRetries: 3,
            timeout: 10000
        },
        
        // External services
        analytics: {
            enabled: false, // Set to true to enable analytics
            trackingId: null
        }
    }
};

// Initialize configuration based on environment
(function initializeConfig() {
    const config = window.DashboardConfig;
    
    // Detect user preferences
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        config.accessibility.reducedMotion = true;
        config.charts.transitions.duration = 0;
    }
    
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        // Already using dark theme, no changes needed
    }
    
    // Set debug mode based on hostname
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        config.debug.enabled = true;
        config.debug.logLevel = 'debug';
        config.features.performanceMonitoring = true;
    }
    
    // Load user preferences from localStorage
    const savedPreferences = DashboardUtils?.storage?.get(config.storage.userPreferences, {});
    if (savedPreferences) {
        // Merge saved preferences with defaults
        Object.assign(config.ui, savedPreferences.ui || {});
        Object.assign(config.accessibility, savedPreferences.accessibility || {});
    }
    
    console.log('🔧 Dashboard configuration initialized:', config);
})();

// Export for use in modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = window.DashboardConfig;
}

console.log('✅ Dashboard configuration loaded');