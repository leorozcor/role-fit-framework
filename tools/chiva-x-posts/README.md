# Chiva X Posts

A small WordPress plugin that shows your latest X posts in the sidebar (widget) or anywhere (shortcode), using the official X API v2.

## Before you install: try the free option once

X's own embed code sometimes still works. Go to publish.twitter.com, paste your profile URL, copy the timeline code into a **Custom HTML** block, and check the page **logged out** (private window). If it shows your posts reliably, you don't need this plugin or an API account. If it shows "Nothing to see here" or nothing at all, use the plugin.

## Setup (about 15 minutes)

1. **X Developer Console** (developer.x.com) — sign in with your own X account.
   - Create a project and app.
   - Add a small amount of API credit, and **set a monthly spending limit** (for example $5).
   - Under *User authentication settings*, set app permissions to **Read**.
   - Under *Keys and tokens*, copy the **API Key** and **API Key Secret**, then generate an **Access Token and Secret** for your own account.
2. **WordPress** → Plugins → Add New → Upload Plugin → choose `chiva-x-posts.zip` → Activate.
3. **Settings → X Posts** → paste the four keys → Save → click **Refresh now**. The status should show your @username and a fetch time.
4. **Show it**: Appearance → Widgets → add **X Posts** to the sidebar. Or, in a block theme, add a Shortcode block with `[chiva_x_posts]` (or `[chiva_x_posts count="3"]`).

## Cost

X moved to pay-per-use in February 2026. Reading your own posts with your own app is billed at the "owned read" rate ($0.001 per post at the time of writing; the general read rate is $0.005). The plugin caches posts and only calls X once per refresh interval, whatever your traffic:

| Refresh every | Posts per fetch | Owned-read rate | Worst case (standard rate) |
|---|---|---|---|
| 3 hours | 5 | ≈ $1.20 / month | ≈ $6 / month |
| 6 hours | 5 | ≈ $0.60 / month | ≈ $3 / month |

The settings page shows the estimate for your own settings. Prices change; the Developer Console is the source of truth.

## Behaviour

- If X is down, out of credit or rate-limited, the widget keeps showing the last posts it fetched and retries after 15 minutes; the error appears on the settings page.
- Replies and reposts are hidden by default (toggle in settings).
- Links are shown as readable links rather than t.co.
- Keys are stored in the WordPress options table, like other plugins' API keys. Uninstalling the plugin deletes them.
