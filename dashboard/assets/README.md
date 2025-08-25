# Dashboard Assets

This folder contains all client-side assets for the Digital Twin Dashboard, including CSS stylesheets and JavaScript modules.

## File Organization

### CSS Files
- **`styles.css`** - Main stylesheet with all component styling and responsive design

### JavaScript Files  
- **`config.js`** - Configuration settings and constants
- **`utils.js`** - Common utility functions and helpers
- **`dashboard.js`** - Main dashboard functionality and interactions

## JavaScript Architecture

### Loading Order
Dash loads assets alphabetically, so files are loaded in this order:
1. `config.js` (configuration first)
2. `dashboard.js` (main functionality)
3. `styles.css` (styling)
4. `utils.js` (utilities)

### Global Objects
- **`window.DashboardConfig`** - Configuration settings
- **`window.DashboardUtils`** - Utility functions

## Features Provided by JavaScript

### 🎯 Dashboard Functionality
- **Keyboard shortcuts** for navigation (W/M/Q/Y for zoom levels)
- **Connection monitoring** with online/offline indicators
- **Visual feedback** with button animations and loading states
- **Responsive layout** adjustments
- **Accessibility enhancements** with ARIA labels and keyboard navigation

### ⌨️ Keyboard Shortcuts
- `W` - Switch to Week view
- `M` - Switch to Month view  
- `Q` - Switch to Quarter view
- `Y` - Switch to Year view
- `←` - Previous time period
- `→` - Next time period  
- `Home` - Jump to latest period
- `Ctrl/Cmd + R` - Refresh dashboard (prevents page reload)

### 🔧 Utilities Available
- **Number formatting** (`DashboardUtils.formatNumber()`)
- **Timestamp formatting** (`DashboardUtils.formatTimestamp()`)
- **Color manipulation** (`DashboardUtils.color.*`)
- **Local storage helpers** (`DashboardUtils.storage.*`)
- **Performance monitoring** (`DashboardUtils.performance.*`)
- **Device detection** (`DashboardUtils.device.*`)

### 🎨 Visual Enhancements
- **Ripple effects** on button clicks
- **Loading states** with spinners
- **Connection status** indicators
- **Toast notifications** for user feedback
- **Smooth scrolling** and animations

## Configuration

### Customizing Settings
Edit `config.js` to modify:
- **Colors and theme** settings
- **Animation durations** and easing
- **Keyboard shortcuts** mapping
- **Performance thresholds**
- **Feature flags** to enable/disable functionality

### Example Configuration Changes
```javascript
// In config.js, modify:
DashboardConfig.theme.primaryColor = '#FF6B6B'; // Change primary color
DashboardConfig.features.keyboardShortcuts = false; // Disable shortcuts
DashboardConfig.app.refreshInterval = 10000; // Change to 10 seconds
```

## Adding New JavaScript Functionality

### 1. Inline JavaScript (for small scripts)
```python
# In your Dash app
app.layout = html.Div([
    # Your layout here...
    
    # Add inline JavaScript
    html.Script("""
        console.log('Inline script executed');
        // Your JavaScript code here
    """)
])
```

### 2. External JavaScript Files
```python
# Add to your app initialization
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
            <!-- Custom external script -->
            <script src="/assets/custom-script.js"></script>
        </footer>
    </body>
</html>
'''
```

### 3. New Asset Files
Simply create new `.js` files in the `assets/` folder. They will be automatically loaded by Dash in alphabetical order.

## Best Practices

### ✅ Do
- Use `DashboardConfig` for all configuration
- Use `DashboardUtils` for common functions
- Add proper error handling and logging
- Follow naming conventions (camelCase for functions, UPPER_CASE for constants)
- Use meaningful variable and function names
- Add comments and documentation

### ❌ Don't  
- Modify global objects directly (use configuration)
- Add inline event listeners without cleanup
- Use `document.write()` or similar blocking methods
- Ignore browser compatibility
- Hardcode values (use configuration instead)

## Browser Compatibility

The JavaScript code is designed to work with:
- **Modern browsers** (Chrome 60+, Firefox 55+, Safari 12+, Edge 79+)
- **Mobile browsers** (iOS Safari 12+, Chrome Mobile 60+)
- **Graceful degradation** for older browsers

## Development vs Production

### Development Mode
- Automatically enabled on `localhost`
- Enhanced logging and debugging
- Performance monitoring enabled
- Debug mode indicators

### Production Mode  
- Minimal logging (warnings and errors only)
- Performance monitoring disabled
- Optimized for performance

## Troubleshooting

### Common Issues
1. **Scripts not loading**: Check browser console for 404 errors
2. **Functions not available**: Ensure proper loading order
3. **Configuration not applied**: Check `DashboardConfig` initialization
4. **Mobile issues**: Test responsive breakpoints in `config.js`

### Debugging
```javascript
// Enable debug mode temporarily
DashboardConfig.debug.enabled = true;
DashboardConfig.debug.logLevel = 'debug';

// Check if utilities are loaded
console.log('Utils loaded:', typeof DashboardUtils !== 'undefined');

// Check configuration  
console.log('Config:', DashboardConfig);
```

## Future Enhancements

Planned features for future versions:
- **Voice commands** for navigation
- **Gesture support** on touch devices  
- **Predictive data loading**
- **Advanced analytics integration**
- **Custom dashboard layouts**
- **Real-time collaboration features**

---

For questions or issues with the JavaScript functionality, check the browser console for error messages and ensure all files are loading correctly.