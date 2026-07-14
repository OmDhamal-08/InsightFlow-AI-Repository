# Frontend — AI BI Platform

## Overview

The frontend is built with **Jinja2 templates** served by FastAPI, styled with **Tailwind CSS** and custom CSS, with **JavaScript** for interactivity.

## Template Inheritance

```
base.html                          ← Global base (head, CDNs, scripts)
├── pages/home.html                ← Public landing page
├── pages/login.html               ← Public login form
├── pages/register.html            ← Public registration form
├── errors/404.html                ← Not found page
├── errors/500.html                ← Server error page
└── base_dashboard.html            ← Authenticated layout (sidebar + navbar)
    ├── pages/dashboard.html       ← Main dashboard
    ├── pages/upload.html          ← Dataset upload
    └── pages/settings.html        ← User settings
```

## Components

| Component | File | Purpose |
|---|---|---|
| Navbar | `components/navbar.html` | Top navigation bar with search, notifications, user dropdown |
| Sidebar | `components/sidebar.html` | Left sidebar with navigation links |
| Footer | `components/footer.html` | Page footer with copyright and links |
| Alerts | `components/alerts.html` | Dismissible alert notifications |
| Loading | `components/loading.html` | Loading spinner overlay |

## CSS Classes

### Glassmorphism
```css
.glass { /* Semi-transparent card with backdrop blur */ }
```

### Buttons
```css
.btn-primary    { /* Blue gradient button */ }
.btn-secondary  { /* Gray outline button */ }
.btn-danger     { /* Red button */ }
.btn-ghost      { /* Transparent button */ }
```

### Cards
```css
.card           { /* Dark card with subtle border */ }
.card-hover     { /* Card with hover lift effect */ }
```

## JavaScript Modules

| Module | File | Purpose |
|---|---|---|
| Main | `js/main.js` | Global initialization, sidebar toggle, dropdowns |
| API | `js/api.js` | Fetch wrapper with auth headers |
| Auth | `js/auth.js` | Login/register form handlers, password strength |
| Dashboard | `js/dashboard.js` | Dashboard data loading, chart placeholders |
| Upload | `js/upload.js` | Drag-and-drop upload, progress bar |
| Settings | `js/settings.js` | Tab switching, form handlers |
| Utils | `js/utils.js` | Shared utilities (formatDate, formatNumber, etc.) |

## Adding a New Page

1. Create `templates/pages/new_page.html`
2. Extend `base_dashboard.html` (authenticated) or `base.html` (public)
3. Add a route in `backend/app/main.py`
4. Add navigation link in `components/sidebar.html`
5. Create `static/js/new_page.js` if needed
