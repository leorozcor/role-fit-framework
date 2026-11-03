"""Wrap page.html and a roles file into one self-contained HTML page that opens in any browser.

Usage, from jobs-agent/:
    python3 dashboard/make_preview.py [ROLES.json] [OUT.html] [--as-of YYYY-MM-DD] [--title TEXT]

Defaults: the dummy sample in, dashboard/sample/preview.html out. --as-of pins "today"
so recency colours stay stable (the sample is pinned to the fictional date 2032-08-15); omit it for real data.

page.html is written for the Claude Dashboard artifact runtime (dash.calc, dash.draw,
dash.data, dash.colors). The small shim below implements just enough of that runtime
for the page to run unchanged outside Claude. It is not the runtime itself.
"""
import argparse, html, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
p = argparse.ArgumentParser()
p.add_argument('roles', nargs='?', default=os.path.join(HERE, 'sample', 'roles.sample.json'))
p.add_argument('out', nargs='?', default=os.path.join(HERE, 'sample', 'preview.html'))
p.add_argument('--as-of', default=None)
p.add_argument('--title', default='Job search')
a = p.parse_args()
if a.as_of is None and os.path.abspath(a.roles) == os.path.join(HERE, 'sample', 'roles.sample.json'):
    a.as_of = '2032-08-15'

roles = json.load(open(a.roles))
page = open(os.path.join(HERE, 'page.html')).read().replace('<meta name="dash-one-writer">', '')

SHIM_CSS = """
:root {
  color-scheme: light dark;
  --font-anthropic-sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-anthropic-serif: Georgia, "Times New Roman", serif;
  --cds-font-size-title: 2rem; --cds-font-size-heading: 1.25rem; --cds-font-size-body: 1rem; --cds-font-size-caption: .8125rem;
  --cds-font-weight-medium: 600;
  --cds-gap-xs: .25rem; --cds-gap-sm: .5rem; --cds-gap-md: 1rem; --cds-gap-xl: 2rem;
  --cds-pad-xs: .25rem; --cds-pad-sm: .5rem; --cds-pad-lg: 1.25rem;
  --cds-radius: 10px; --cds-dur-slow: .3s;
  --color-bg: #faf9f6; --color-panel: #ffffff; --color-fg: #1f1e1c; --color-fg-muted: #6b6862;
  --color-border-line: #e4e1da; --color-ok: #2e8b57;
  --cds-chart-muted: #b9b5ad; --cds-chart-grid: #ece9e2; --cds-chart-axis: #c9c5bd;
  --cds-surface-popover: #ffffff; --cds-border: #d9d5cc; --cds-text-secondary: #6b6862;
  --cds-shadow-popover: 0 4px 16px rgba(0,0,0,.12);
  --dash-c0: #3b6fd8;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --color-bg: #1b1a18; --color-panel: #252421; --color-fg: #ecebe7; --color-fg-muted: #a39f97;
    --color-border-line: #3a3834; --color-ok: #4fbf82;
    --cds-chart-muted: #5f5c56; --cds-chart-grid: #33312d; --cds-chart-axis: #4a4843;
    --cds-surface-popover: #2c2b28; --cds-border: #45433e; --cds-text-secondary: #a39f97;
    --cds-shadow-popover: 0 4px 16px rgba(0,0,0,.5);
    --dash-c0: #7da2ee;
  }
}
:root[data-theme="dark"] {
  --color-bg: #1b1a18; --color-panel: #252421; --color-fg: #ecebe7; --color-fg-muted: #a39f97;
  --color-border-line: #3a3834; --color-ok: #4fbf82;
  --cds-chart-muted: #5f5c56; --cds-chart-grid: #33312d; --cds-chart-axis: #4a4843;
  --cds-surface-popover: #2c2b28; --cds-border: #45433e; --cds-text-secondary: #a39f97;
  --cds-shadow-popover: 0 4px 16px rgba(0,0,0,.5);
  --dash-c0: #7da2ee;
}
html, body { margin: 0; background: var(--color-bg); color: var(--color-fg); }
body { padding: 24px 16px 48px; font-family: var(--font-anthropic-sans); line-height: 1.45; }
.preview-banner { max-width: 72rem; margin: 0 auto 16px; font-size: .8125rem; color: var(--color-fg-muted); }
"""

SHIM_JS = """
window.DASH_NOW = %(asof)s;
window.dash = (() => {
  const calcs = {}, draws = {}, data = {};
  return {
    colors: ['var(--dash-c0)'],
    calc(name, spec) { calcs[name] = spec; },
    draw(name, fn) { draws[name] = fn; },
    data(name) { return data[name] || {status: 'loading', data: []}; },
    _boot(rows) {
      data.roles = {status: 'ok', data: rows};
      for (const [name, spec] of Object.entries(calcs)) {
        try { data[name] = {status: 'ok', data: spec.fn(...spec.inputs.map((i) => data[i].data))}; }
        catch (e) { data[name] = {status: 'failed', data: [], message: String(e)}; console.error(name, e); }
      }
      const render = () => document.querySelectorAll('[data-draw]').forEach((el) => draws[el.dataset.draw] && draws[el.dataset.draw](el));
      render();
      let t; addEventListener('resize', () => { clearTimeout(t); t = setTimeout(render, 150); });
    }
  };
})();
"""

doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(a.title)}</title>
<style>{SHIM_CSS}</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script>{SHIM_JS % {'asof': json.dumps(a.as_of)}}</script>
</head>
<body>
<p class="preview-banner">{'Dummy data for illustration: every company, role and date is invented.' if 'sample' in os.path.basename(a.roles) else 'Local preview of the job-search dashboard.'}</p>
{page}
<script id="roles-data" type="application/json">{json.dumps(roles, ensure_ascii=False).replace('</', '<\\/')}</script>
<script>dash._boot(JSON.parse(document.getElementById('roles-data').textContent));</script>
</body>
</html>
"""
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
open(a.out, 'w').write(doc)
print(len(roles), 'roles ->', a.out)
