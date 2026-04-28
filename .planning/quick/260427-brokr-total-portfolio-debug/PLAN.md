---
name: brokr-total-portfolio-debug
description: Add TOTAL_PORTFOLIO_DEBUG WARNING log in degiro_client.py
status: complete
---

Add WARNING-level log line in `fetch_portfolio()` after `total_portfolio_data` extraction, before any parsing logic. No other changes.