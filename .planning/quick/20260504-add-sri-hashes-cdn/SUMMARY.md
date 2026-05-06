---
name: 20260504-add-sri-hashes-cdn
status: complete
---

Add SRI hashes to CDN resources in index.html and login.html.

## Changes
- `app/static/index.html`: Added SRI hashes to Google Fonts (link), Chart.js (script), and Lucide icons (script)
- `app/templates/login.html`: Added SRI hash to Google Fonts (link)

## Hashes computed (SHA-384, base64)
- Chart.js 4.4.7 (jsdelivr): `sha384-vsFfeLOOY6KuIYKDlmVH5UiBmgIdB1oEf7p01YgWHuqmOHfZr374+odEv96n9tNC`
- Lucide 0.460.0 (unpkg): `sha384-ieG+IKD0d/ZPXyCBTMVAbqsQdns8QGJR/e26WMw7M4fkaI/rHcS/YIoi+ah9WGge`
- Google Fonts Inter: `sha384-cmj3JhQ6PRbUDt5man3nVqHXcMSvk16BQ1IsZTxTRYPLrlQTshDfe/2KAnfDExPB`
