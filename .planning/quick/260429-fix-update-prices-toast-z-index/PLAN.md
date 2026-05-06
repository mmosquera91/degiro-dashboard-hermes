Fix toast z-index so Update Prices toast renders above header.

# Problem
The Update Prices toast (`.toast-top-center`) had position: fixed but no z-index,
causing it to render behind the header (z-index: 100).

# Fix
In `app/static/style.css` line ~1019, added `z-index: 1000` to `.toast-top-center`
and changed `top: 16px` to `top: 1rem` for consistency.

# Files changed
- app/static/style.css: .toast-top-center { z-index: 1000; top: 1rem; }
