# Frontend

Server-rendered Jinja2 templates styled with Tailwind CSS (CDN) and a small `main.css`. Each page's JavaScript calls the JSON API under `/api/v1`. There is no build step.

## How a page loads

1. FastAPI returns the HTML from a template (`backend/app/routers/pages.py`).
2. `main.js` checks the session with `/api/v1/auth/me` and redirects to `/login` if it is not valid.
3. The page's own script (for example `quality.js`) fetches data with `api.js` and renders tables and Plotly charts.

## Templates

```
base.html                     public layout: <head>, CDN scripts, shared JS
├── pages/home.html, login.html, register.html, forgot_password.html,
│   reset_password.html, terms.html, privacy.html
├── errors/404.html, errors/500.html
└── base_dashboard.html       logged-in layout: sidebar + navbar
    ├── pages/dashboard.html, upload.html, settings.html
    ├── pages/profiling.html, quality.html, preprocessing.html,
    │   eda.html, features.html          (share components/dataset_subnav.html)
    └── pages/experiments.html, experiment_detail.html
```

| Component | Purpose |
|---|---|
| `components/sidebar.html` | Main navigation, theme toggle, user info |
| `components/navbar.html` | Dataset search, notifications, user menu |
| `components/dataset_subnav.html` | Tabs between the per-dataset pages |
| `components/icons.html` | `icon(name)` macro with inline SVG icons |
| `components/alerts.html`, `loading.html`, `footer.html` | Small shared pieces |

## JavaScript

| File | Purpose |
|---|---|
| `api.js` | `fetch` wrapper: adds the access token, refreshes it once on a 401 |
| `utils.js` | Formatting, `escapeHtml`, toasts |
| `main.js` | Session check, sidebar, theme, navbar search and notifications |
| `ml_common.js` | Helpers shared by the AutoML pages |
| `auth.js`, `settings.js`, `dashboard.js`, `upload.js` | One per page |
| `profiling.js`, `quality.js`, `preprocessing.js`, `eda.js`, `features.js` | Per-dataset pages |
| `experiments.js`, `experiment_detail.js` | Training form and leaderboard/evaluation |

Anything that comes from user data (file names, CSV headers, cell values) must go through `escapeHtml()` before it is put into `innerHTML`.

## CSS

`main.css` only holds what Tailwind doesn't: theme variables, `.glass` panels, `.btn-*` and `.card` styles, badges, the drop zone, light-mode overrides and animations.

## Adding a page

1. Create `templates/pages/my_page.html` extending `base_dashboard.html` (or `base.html` for a public page).
2. Add a route in `backend/app/routers/pages.py` using `render(...)`.
3. Add a link in `components/sidebar.html`.
4. Create `static/js/my_page.js` and include it in the template's `page_scripts` block.
