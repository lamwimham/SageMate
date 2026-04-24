# SageMate Core — VSCode-Style Layout Implementation Plan

> **Goal**: Refactor frontend from single-column centered layout → VSCode-style multi-column layout
> **Strategy**: Incremental migration with backward compatibility
> **Date**: 2026-04-23

---

## 1. Current Architecture Analysis

### 1.1 Current Layout (Single Column)
```
┌──────────────────────────────────────────────┐
│  Top Header: Logo | Nav(6) | API | Theme    │
├──────────────────────────────────────────────┤
│  <main id="main-content">                    │
│    max-w-7xl mx-auto px-4                    │
│    {% block content %}                        │
│  </main>                                     │
├──────────────────────────────────────────────┤
│  Footer                                      │
└──────────────────────────────────────────────┘
```

### 1.2 Key Findings
- **PJAX Router**: Already exists, swaps `<main>` content on internal link clicks
- **Design Tokens**: Well-defined CSS custom properties (dark/light theme)
- **`raw.html`**: Already uses two-panel layout (sidebar + main), closest to target
- **No build step**: Pure HTML templates + vanilla JS + Tailwind CDN
- **Chinese UI labels**: All user-facing text in Chinese

### 1.3 Constraints
- No Node.js build pipeline → all CSS/JS inline or local static files
- Must maintain PJAX compatibility (content swap without full reload)
- Mobile responsive requirement (collapse panels on small screens)
- Chinese labels must be preserved

---

## 2. Target Architecture (VSCode-Style)

### 2.1 Layout Regions
```
┌──────────┬──────────────┬────────────────────────────┬─────────────┐
│ Activity │   Sidebar    │      Main Content          │   Detail    │
│  Bar     │              │                            │   Panel     │
│  48px    │   260px      │      flexible              │   300px     │
│          │              │                            │  (optional) │
│ [📊]     │  Explorer    │  ┌──────────────────┐     │             │
│ [📚]     │  Search      │  │ Tab Bar           │     │  Metadata   │
│ [⚡]     │  Outline     │  ├──────────────────┤     │  Links      │
│ [📂]     │  Tasks       │  │ Content           │     │  Graph      │
│ [🔍]     │              │  │                   │     │             │
│ [⚙️]     │              │  └──────────────────┘     │             │
│          │              │                            │             │
├──────────┴──────────────┴────────────────────────────┴─────────────┤
│                    Bottom Panel (optional)                         │
│                    200px height                                     │
└────────────────────────────────────────────────────────────────────┘
```

### 2.2 Panel Visibility per Page

| Page | Activity Bar | Sidebar | Main | Detail | Bottom |
|------|:---:|:---:|:---:|:---:|:---:|
| Dashboard | ✅ | ✅ Quick Links + Activity | ✅ Stats + Recent | ❌ | ❌ |
| Pages List | ✅ | ✅ Category Tree | ✅ Page Cards | ❌ | ❌ |
| Page Detail | ✅ | ✅ Outline + Links | ✅ Markdown Editor | ✅ Metadata | ❌ |
| Ingest | ✅ | ✅ Task History | ✅ Input Forms | ❌ | ✅ Task Log |
| Raw Files | ✅ | ✅ File Tree | ✅ Preview | ✅ File Meta | ❌ |
| Status | ✅ | ✅ Tab Nav | ✅ Health/Log/Cost | ❌ | ❌ |
| Settings | ✅ | ✅ Section Nav | ✅ Config Forms | ❌ | ❌ |

---

## 3. Implementation Phases

### Phase 1: Layout Shell + Activity Bar (Highest Priority)

**Files Modified**: `base.html`
**Risk**: Low (new layout, old pages still render inside main content)

**Steps**:
1. Add CSS Grid layout to `<body>` in `base.html`
2. Create Activity Bar (left icon rail, 48px wide)
3. Wrap existing `<main>` in new grid structure
4. Add collapsible Sidebar placeholder
5. Add collapsible Detail Panel placeholder
6. Add collapsible Bottom Panel placeholder
7. Add panel toggle buttons
8. Add responsive breakpoints (mobile: collapse all panels)
9. Update PJAX router to handle multi-panel updates

**Design Pattern**: **Composite Layout** — `base.html` as shell with named `{% block %}` slots:
- `{% block activity_bar %}` — optional, default icons
- `{% block sidebar %}` — optional, per-page sidebar content
- `{% block content %}` — required, main content (existing)
- `{% block detail_panel %}` — optional, per-page detail content
- `{% block bottom_panel %}` — optional, per-page bottom content

### Phase 2: Enhanced PJAX Router

**Files Modified**: `base.html` (script section)
**Risk**: Medium (changes navigation behavior)

**Steps**:
1. Add `data-panel` attribute support on links (`data-panel="sidebar"`, `data-panel="main"`, etc.)
2. Add panel state management (`window.__sagemate__.panels`)
3. Add tab management for main content (open/close/switch tabs)
4. Add event bus for cross-panel communication (`window.__sagemate__.events`)
5. Add keyboard shortcuts handler
6. Add command palette (Ctrl+Shift+P)

### Phase 3: Page Migration (One at a Time)

**Order**: Dashboard → Pages → Page Detail → Raw → Ingest → Status → Settings

For each page:
1. Update template to use new block slots
2. Move sidebar content to `{% block sidebar %}`
3. Move detail panel content to `{% block detail_panel %}`
4. Update main content to fit new layout
5. Test PJAX navigation
6. Test responsive behavior

### Phase 4: Polish + Features

1. Resizable panels (drag borders)
2. Panel state persistence (localStorage)
3. Command palette with fuzzy search
4. Breadcrumbs in main content header
5. Tab management for open pages

---

## 4. Technical Design Decisions

### 4.1 CSS Grid vs Flexbox
**Decision**: CSS Grid for main shell, Flexbox for internal panel layouts

**Rationale**:
- Grid excels at 2D layout (rows + columns simultaneously)
- Flexbox better for 1D layouts (within panels)
- Grid's `minmax()` and `fr` units handle responsive resizing naturally

### 4.2 Panel State Management
**Decision**: Simple JS object on `window.__sagemate__` + localStorage persistence

**Rationale**:
- No framework → no Redux/Vuex
- Single global object is simple and effective
- localStorage for persistence across page reloads
- `CustomEvent` for reactivity (no need for reactive framework)

### 4.3 PJAX Router Enhancement
**Decision**: Extend existing router, don't replace

**Rationale**:
- Current router works well for single-panel swaps
- Add multi-panel support as optional enhancement
- Use `data-panel` attribute for explicit targeting
- Default to `main` panel for backward compatibility

### 4.4 Tab Management
**Decision**: Simple in-memory tab list, rendered in main content header

**Rationale**:
- Tabs are a UI concern, not a routing concern
- Store open tabs in `window.__sagemate__.panels.main.tabs`
- Each tab: `{ url, title, icon, active }`
- Render tab bar above main content
- PJAX navigation adds to tab history

### 4.5 Mobile Responsive Strategy
**Decision**: Overlay panels on mobile, side-by-side on desktop

**Rationale**:
- < 768px: All panels overlay main content (slide-in)
- 768-1024px: Activity bar + main only, sidebar overlays
- > 1024px: Full multi-column layout

---

## 5. Code Structure

### 5.1 New base.html Structure
```html
<body class="layout-shell">
  <!-- Activity Bar (always visible) -->
  <aside id="activity-bar">
    {% block activity_bar %}
      <!-- Default icons for all pages -->
    {% endblock %}
  </aside>

  <div class="layout-body">
    <!-- Sidebar (collapsible) -->
    <aside id="side-bar" class="panel {% if not sidebar_open %}panel-collapsed{% endif %}">
      {% block sidebar %}{% endblock %}
    </aside>

    <!-- Main Content -->
    <main id="main-content" class="main-content">
      {% block tab_bar %}{% endblock %}
      {% block content %}{% endblock %}
    </main>

    <!-- Detail Panel (collapsible) -->
    <aside id="detail-panel" class="panel {% if not detail_open %}panel-collapsed{% endif %}">
      {% block detail_panel %}{% endblock %}
    </aside>
  </div>

  <!-- Bottom Panel (collapsible) -->
  <aside id="bottom-panel" class="panel {% if not bottom_open %}panel-collapsed{% endif %}">
    {% block bottom_panel %}{% endblock %}
  </aside>

  <!-- Command Palette (modal) -->
  <div id="command-palette" class="hidden">...</div>
</body>
```

### 5.2 CSS Grid Layout
```css
.layout-shell {
  display: grid;
  grid-template-columns: 48px 1fr;
  grid-template-rows: 1fr auto;
  height: 100vh;
  overflow: hidden;
}

.layout-shell .layout-body {
  display: grid;
  grid-template-columns: [sidebar] 0px [main] 1fr [detail] 0px;
  overflow: hidden;
}

.layout-shell.sidebar-open .layout-body {
  grid-template-columns: [sidebar] 260px [main] 1fr [detail] 0px;
}

.layout-shell.detail-open .layout-body {
  grid-template-columns: [sidebar] 260px [main] 1fr [detail] 300px;
}

.layout-shell.bottom-open {
  grid-template-rows: 1fr 200px;
}

/* Mobile responsive */
@media (max-width: 768px) {
  .layout-shell {
    grid-template-columns: 48px 1fr;
  }
  .layout-shell .layout-body {
    grid-template-columns: 1fr;
  }
  #side-bar, #detail-panel {
    position: fixed;
    top: 0;
    height: 100vh;
    width: 280px;
    z-index: 40;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
  }
  #side-bar.panel-open {
    transform: translateX(0);
  }
  #detail-panel {
    right: 0;
    left: auto;
    transform: translateX(100%);
  }
  #detail-panel.panel-open {
    transform: translateX(0);
  }
}
```

### 5.3 JavaScript State Management
```javascript
window.__sagemate__ = {
  layout: {
    sidebarOpen: false,
    detailOpen: false,
    bottomOpen: false,
  },
  panels: {
    main: {
      tabs: [],
      activeTab: null,
    }
  },
  nav: {
    active: 'dashboard',
    history: [],
  },
  events: new EventTarget(),

  // Methods
  toggleSidebar() { ... },
  toggleDetail() { ... },
  toggleBottom() { ... },
  navigate(url, panel = 'main') { ... },
  openTab(url, title) { ... },
  closeTab(index) { ... },
};
```

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| PJAX breaks existing pages | Medium | High | Test each page after migration |
| CSS Grid not supported | Low | Low | All modern browsers support Grid |
| Mobile layout broken | Medium | Medium | Test on real device, use overlay pattern |
| Performance regression | Low | Medium | Lazy load panel content |
| Chinese labels lost | Low | High | Preserve all existing text |
| Theme toggle breaks | Low | High | Keep existing theme code intact |

---

## 7. Migration Checklist

### Phase 1: Layout Shell
- [ ] Create new `base.html` with grid layout
- [ ] Add Activity Bar with 6 icons
- [ ] Add collapsible Sidebar
- [ ] Add collapsible Detail Panel
- [ ] Add collapsible Bottom Panel
- [ ] Add panel toggle logic
- [ ] Add responsive breakpoints
- [ ] Test all pages render correctly
- [ ] Test theme toggle works
- [ ] Test mobile layout

### Phase 2: Enhanced PJAX
- [ ] Add `data-panel` attribute support
- [ ] Add panel state management
- [ ] Add tab management
- [ ] Add event bus
- [ ] Add keyboard shortcuts
- [ ] Add command palette

### Phase 3: Page Migration
- [ ] Migrate Dashboard
- [ ] Migrate Pages List
- [ ] Migrate Page Detail
- [ ] Migrate Ingest
- [ ] Migrate Raw Files
- [ ] Migrate Status
- [ ] Migrate Settings

### Phase 4: Polish
- [ ] Resizable panels
- [ ] State persistence
- [ ] Breadcrumbs
- [ ] Fuzzy search in command palette
- [ ] Accessibility (ARIA labels, keyboard nav)

---

## 8. Next Steps

1. **Start with Phase 1**: Refactor `base.html` to add the VSCode-style layout shell
2. **Keep backward compatibility**: Old pages should still render inside the new main content area
3. **Test incrementally**: After each change, verify all pages still work
4. **Document changes**: Update this plan as implementation progresses

---

*End of Plan*
