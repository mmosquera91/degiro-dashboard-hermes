---
name: 260429-fix-update-prices-toast-z-index
description: Fix toast z-index so Update Prices toast renders above header
type: quick
status: complete
---

Fixed `.toast-top-center` in `app/static/style.css` by adding `z-index: 1000`
(above header's z-index: 100) and normalizing `top` to `1rem`.
