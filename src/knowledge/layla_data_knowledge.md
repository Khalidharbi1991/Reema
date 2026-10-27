# Layla's Data Visualization & Power BI Knowledge Base

## POWER BI EXPERTISE

### Dashboard Design Principles
1. **F-Pattern Layout**: Users scan dashboards in F-pattern (top-left is prime real estate)
2. **3-Second Rule**: Key insights should be understood within 3 seconds
3. **5-Chart Maximum**: Don't overload a single page (max 5-7 visuals)
4. **Consistent Navigation**: Place filters and slicers in same position across pages
5. **Mobile-First**: Design for mobile, enhance for desktop

### Visual Selection Guide
- **KPI Cards**: Single metric comparison (actual vs target)
- **Line Charts**: Trends over time, continuous data
- **Bar/Column Charts**: Comparisons across categories
- **Pie/Donut Charts**: Part-to-whole (max 5 slices)
- **Tables/Matrix**: Detailed data, cross-tabulation
- **Gauge Charts**: Progress toward goals
- **Waterfall Charts**: Sequential positive/negative changes
- **Scatter Plots**: Correlation between two metrics
- **Heat Maps**: Patterns across two dimensions
- **Funnel Charts**: Sequential process stages

### DAX Best Practices
```dax
// Measure naming convention: [Metric Name]
Total Sales = SUM(Sales[Amount])

// Use variables for readability
Customer Lifetime Value =
VAR TotalPurchases = SUM(Purchases[Amount])
VAR CustomerCount = DISTINCTCOUNT(Customers[CustomerID])
RETURN DIVIDE(TotalPurchases, CustomerCount, 0)

// Time intelligence patterns
YoY Growth % =
DIVIDE(
    [Total Sales] - CALCULATE([Total Sales], SAMEPERIODLASTYEAR('Date'[Date])),
    CALCULATE([Total Sales], SAMEPERIODLASTYEAR('Date'[Date])),
    0
)

// Use SWITCH for categorization
Priority Level =
SWITCH(
    TRUE(),
    [Days Open] <= 1, "Critical",
    [Days Open] <= 3, "High",
    [Days Open] <= 7, "Medium",
    "Low"
)
```

### Data Modeling Best Practices
1. **Star Schema Preferred**: Fact tables surrounded by dimension tables
2. **One-to-Many Relationships**: Avoid many-to-many when possible
3. **Date Table Required**: Create dedicated calendar table
4. **Avoid Bi-Directional Filters**: Use unidirectional relationships
5. **Hide Unnecessary Columns**: Reduce model complexity
6. **Aggregate Tables**: For large datasets (>1M rows)

### Color Psychology in Dashboards
- **Red**: Alerts, negative, critical issues
- **Green**: Success, positive, on-target
- **Yellow/Orange**: Warning, needs attention
- **Blue**: Neutral, informational, trust
- **Grey**: Inactive, baseline, background
- **Consistent Palette**: Use same colors for same metrics across pages

### ITSM Analytics Frameworks

#### Incident Management Metrics
**Operational KPIs:**
- Mean Time to Resolve (MTTR)
- Mean Time to Acknowledge (MTTA)
- First Contact Resolution Rate (FCR)
- Incident Volume (by priority, category, time)
- SLA Compliance Rate
- Backlog Age
- Reopened Incident Rate

**Dashboard Pages:**
1. Executive Overview (KPI cards, trend lines)
2. Incident Volume Analysis (bar charts, heat maps)
3. Resolution Performance (waterfall, gauge)
4. SLA Compliance (matrix, conditional formatting)
5. Team Performance (scatter plot, ranking)

#### Change Management Analytics
**Key Metrics:**
- Change Success Rate
- Emergency Change %
- Change Volume by Type
- Average Implementation Time
- Change-Related Incidents
- CAB Meeting Efficiency

**Visualizations:**
- Change Calendar (heat map)
- Success/Failure Funnel
- Risk Assessment Matrix
- Timeline Gantt-style view

#### Problem Management Metrics
**Core KPIs:**
- Known Errors Identified
- Root Cause Analysis Completion Rate
- Problem Resolution Time
- Recurring Incident Reduction
- Major Incident Prevention Rate

#### Service Request Management
**Metrics:**
- Request Fulfillment Time
- Request Volume by Category
- Automation Rate
- Self-Service Adoption
- Customer Satisfaction Score (CSAT)

### Power BI Architecture Patterns

#### Enterprise Deployment Model
```
Workspace Structure:
├── Development Workspace
│   ├── Dev Datasets
│   ├── Test Reports
│   └── Sandbox Dataflows
├── Test/UAT Workspace
│   ├── UAT Datasets
│   └── UAT Reports
└── Production Workspace
    ├── Certified Datasets
    ├── Published Reports
    └── Production Dataflows

Deployment Pipeline: Dev → Test → Prod
```

#### Data Refresh Strategy
- **Streaming**: Real-time data (< 1 min delay)
- **DirectQuery**: Live connection, no data import
- **Incremental Refresh**: Large datasets (>1GB)
- **Scheduled Refresh**: Import mode (8x/day free, 48x/day Premium)
- **Hybrid**: Combination based on data freshness needs

### Row-Level Security (RLS) Patterns

```dax
// Manager sees only their team
[Manager Email] = USERPRINCIPALNAME()

// Regional access
[Region] IN PATHCONTAINS('User_Security'[Regions], USERPRINCIPALNAME())

// Dynamic security with bridge table
VAR UserEmail = USERPRINCIPALNAME()
RETURN CONTAINS(SecurityTable, SecurityTable[Email], UserEmail)
```

### Performance Optimization Techniques

1. **Query Folding**: Push transformations to source
2. **Remove Unused Columns**: In Power Query
3. **Disable Auto Date/Time**: Reduces model size
4. **Use Aggregations**: For DirectQuery performance
5. **Optimize DAX**: CALCULATE vs FILTER, variables
6. **Reduce Cardinality**: In dimension columns
7. **Compression**: Proper data types (whole number vs decimal)

### Mobile Dashboard Design

**Mobile Layout Checklist:**
- Portrait orientation (9:16 ratio)
- Touch-friendly buttons (min 44x44 px)
- Simplified visuals (fewer data points)
- Larger fonts (min 12pt)
- Vertical scrolling (avoid horizontal)
- Essential KPIs only

### Accessibility Standards (WCAG 2.1)

1. **Color Contrast**: Minimum 4.5:1 ratio
2. **Alt Text**: Describe all visuals
3. **Keyboard Navigation**: Tab order logical
4. **Screen Reader**: Proper labeling
5. **Color Independence**: Don't rely solely on color
6. **Focus Indicators**: Visible when tabbing

### Data Governance Framework

**Data Quality Dimensions:**
- Accuracy: Correct values
- Completeness: No missing data
- Consistency: Same values across systems
- Timeliness: Up-to-date information
- Validity: Conforms to business rules
- Uniqueness: No duplicates

**Metadata Management:**
- Data dictionary
- Business glossary
- Data lineage documentation
- Impact analysis
- Change management

### Advanced Analytics in Power BI

#### R/Python Integration
```python
# Clustering visualization
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt

kmeans = KMeans(n_clusters=3)
dataset['Cluster'] = kmeans.fit_predict(dataset[['X', 'Y']])
```

#### AI Visuals
- Key Influencers: What drives a metric
- Decomposition Tree: Hierarchical analysis
- Q&A Visual: Natural language queries
- Smart Narrative: Auto-generated insights
- Anomaly Detection: Outlier identification

### Report Design Patterns

#### Drill-Through Page Design
```
Source Page: Overview
→ Right-click on data point
→ Drill through to: Detail Page
→ Filter context passed automatically
→ Back button returns to source
```

#### Tooltip Page Design
- Small canvas (300x200 px typical)
- Quick insights on hover
- Related but different data
- No navigation elements

#### Bookmarks for Storytelling
1. Create views (filtered states)
2. Add bookmarks
3. Create buttons with bookmark actions
4. Build narrative flow

### ITSM-Specific Dashboard Examples

#### IT Service Desk Executive Dashboard
**Top Section (KPI Cards):**
- Open Tickets
- Avg Resolution Time
- SLA Compliance %
- Customer Satisfaction

**Middle Section:**
- Ticket Volume Trend (Line chart, 90 days)
- Tickets by Priority (Stacked bar)
- Top 5 Categories (Horizontal bar)

**Bottom Section:**
- SLA Performance by Team (Matrix with conditional formatting)
- Aging Tickets (Heat map)

#### Asset Management Dashboard
**Visuals:**
- Asset Count by Type (Donut chart)
- Asset Lifecycle (Funnel)
- Compliance Status (Gauge)
- Cost by Department (Treemap)
- Warranty Expiration (Timeline)

### Integration Patterns

#### ServiceNow Integration
```
1. REST API connection
2. OAuth authentication
3. JSON parsing in Power Query
4. Incremental refresh on sys_updated_on
```

#### Active Directory Integration
```
1. DirectQuery to AD
2. User attributes (department, manager, location)
3. RLS based on AD groups
4. Automatic user provisioning
```

### Best Practices Summary

**DO:**
- Use consistent formatting across all visuals
- Provide clear titles and labels
- Add tooltips for context
- Test on mobile devices
- Document DAX measures
- Version control reports (Power BI Desktop → Git)
- Use parameters for flexibility

**DON'T:**
- Overuse 3D charts (reduce readability)
- Mix too many visual types on one page
- Use default color schemes (customize for brand)
- Show raw data tables on executive dashboards
- Ignore performance (>3 second load time is bad)
- Forget accessibility (color-blind users)

### Metric Calculation Formulas

#### IT Service Management
```
MTTR = Total Resolution Time / Number of Incidents Resolved
FCR % = (Incidents Resolved on First Contact / Total Incidents) × 100
SLA Compliance % = (Incidents Met SLA / Total Incidents) × 100
Backlog = Open Incidents at End of Period
Reopened % = (Reopened Incidents / Total Resolved) × 100
```

#### Availability & Performance
```
Availability % = (Uptime Hours / Total Hours) × 100
MTBF = Total Uptime / Number of Failures
MTBSI = Total Operating Time / Number of Incidents
```

#### Change & Release
```
Change Success Rate = (Successful Changes / Total Changes) × 100
Emergency Change % = (Emergency Changes / Total Changes) × 100
Failed Change % = (Failed Changes / Total Changes) × 100
```

### Storytelling with Data

**Narrative Structure:**
1. **Context**: What's the situation?
2. **Complication**: What's the problem?
3. **Resolution**: What's the solution?
4. **Action**: What should we do?

**Dashboard Flow:**
- Page 1: Executive summary (the story)
- Page 2: Supporting details (the evidence)
- Page 3: Deep dive (the analysis)
- Page 4: Action items (the next steps)

This knowledge base represents world-class expertise in data visualization, Power BI development, and IT analytics. Use it to create actionable, visually compelling, and strategically valuable analytics solutions.
