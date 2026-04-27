Reorder dashboard sections in app/static/index.html per reading hierarchy

Current section order:
  1. summary-cards        (no change)
  2. charts-section       (allocation, sector, top 10)
  3. benchmark-section
  4. attribution-section
  5. positions-section
  6. buy-radar-section
  7. health-alerts-section
  8. winners-losers-section

Target order:
  1. summary-cards        (no change)
  2. benchmark-section    (move up)
  3. health-alerts-section (move up)
  4. buy-radar-section    (move up)
  5. winners-losers-section (move up)
  6. charts-section       (reference material)
  7. positions-section    (reference material)
  8. attribution-section  (wrap in <details>/<summary>, collapsed by default)

Only move HTML section elements and wrap attribution in <details>.
