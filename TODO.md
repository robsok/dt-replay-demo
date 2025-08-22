# Digital Twin Lab Dashboard - TODO

## High Priority Features

### Database Integration
- [ ] Replace pickle file storage with proper database (PostgreSQL or InfluxDB)
- [ ] Add database schema for time-series lab data
- [ ] Implement proper data persistence and querying
- [ ] Add database connection pooling for scalability

### Events Stream Enhancement
- [ ] Create separate "events" stream for lab operations
- [ ] Add event types: "ordered", "500 samples received", "pause", "equipment maintenance"
- [ ] Display text events on timeline as annotations
- [ ] Add event severity levels (info, warning, error)
- [ ] Allow manual event injection via dashboard interface

## Timeline Visualization Improvements

### Swimlane Layout
- [ ] Make swimlane rows thinner (reduce height from 150px)
- [ ] Move stream type labels to left side instead of subplot titles above
- [ ] Add compact lane headers with color indicators
- [ ] Optimize vertical spacing between lanes

### Timeline Navigation
- [ ] Implement maximum timeline length with horizontal scrollbar
- [ ] Add zoom controls (1h, 1d, 1w, 1m views)
- [ ] Add pan/scroll functionality for long time periods
- [ ] Add "Jump to Latest" button

### Date/Time Display
- [ ] Change x-axis format from time-only to full date-time
- [ ] Show dates prominently (YYYY-MM-DD HH:MM format)
- [ ] Add timezone indicator in corner
- [ ] Smart date formatting based on zoom level

### Weekend/Holiday Indicators
- [ ] Add background shading for weekends across all swimlanes
- [ ] Different color for Saturdays vs Sundays
- [ ] Add holiday markers (configurable calendar)
- [ ] Show business hours vs off-hours indicators

## Dashboard Enhancements

### Real-Time Features
- [ ] Add auto-pause/play controls for timeline
- [ ] Show live vs historical data indicators
- [ ] Add "time travel" slider to replay from specific points
- [ ] Real-time statistics: events/minute, active streams

### Data Analysis
- [ ] Add stream health indicators (last activity, error rates)
- [ ] Show data quality metrics per stream
- [ ] Add trend analysis graphs (daily/weekly patterns)
- [ ] Export functionality for data analysis

### User Experience
- [ ] Add dark/light theme toggle
- [ ] Responsive design for mobile/tablet viewing
- [ ] Add loading indicators and progress bars
- [ ] Better error handling and user notifications

## Technical Improvements

### Performance
- [ ] Optimize data loading for large datasets
- [ ] Implement data pagination/windowing
- [ ] Add caching for frequently accessed data
- [ ] Background data processing for heavy operations

### Architecture
- [ ] Separate dashboard from data ingestion services
- [ ] Add API layer between dashboard and data storage
- [ ] Implement proper logging and monitoring
- [ ] Add configuration management system

### Data Processing
- [ ] Add data validation and error handling
- [ ] Implement data aggregation (hourly/daily summaries)
- [ ] Add data cleaning and outlier detection
- [ ] Support for different data formats (CSV, JSON, Parquet)

## Integration & Deployment

### Production Readiness
- [ ] Add Docker containerization
- [ ] Create deployment scripts
- [ ] Add monitoring and alerting
- [ ] Implement backup and recovery procedures

### External Systems
- [ ] REST API for external data access
- [ ] WebSocket support for real-time updates
- [ ] Integration with lab management systems
- [ ] Export to external analytics platforms

## Documentation
- [ ] Create user guide for dashboard
- [ ] Add developer documentation
- [ ] Create deployment guide
- [ ] Add troubleshooting guide

---

## Completed Features
- [x] Basic MQTT data ingestion
- [x] Streamlit dashboard with live updates
- [x] Event counters by stream type
- [x] Basic timeline visualization with colored dots
- [x] Event timestamp parsing and display
- [x] Clear data functionality
- [x] Multi-stream data merging and replay
- [x] Gap detection and handling in data streams