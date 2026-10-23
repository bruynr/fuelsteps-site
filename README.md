# FuelSteps website

Landing page for [FuelSteps](https://fuelsteps.com/), a free Garmin Connect IQ data field for fuel reminders during runs. Static HTML, built and served by GitHub Pages (GitHub Actions).

- Texts: `i18n/<lang>.json` (en, nl, de, fr, es, it); all files have the same keys
- Pages: home (`/`, `/<lang>/`) and the plan builder (`/plan/`, `/<lang>/plan/`: `plan.js` + `plan-core.js`, settings format reference, Umami events)
- Build: `python build.py` (needs Pillow: `pip install pillow`) → `index.html` (en), `<lang>/index.html`, `plan/index.html`, `<lang>/plan/index.html`, WebP images and icons in `img/web/`, `manifest.webmanifest`, `404.html`, `sitemap.xml`, `robots.txt`, `llms.txt`, `llms-full.txt`. These are generated and not in git: on every push to `gh-pages`, `.github/workflows/pages.yml` runs the tests, builds and publishes them. Locally, run `build.py` to preview.
- Tests: `node --test` (Node 22; `plan-core.test.js` mirrors `ScheduleParser.mc` in the app repo)
- Analytics: Umami Cloud (cookieless, no consent banner, `data-domains` so only fuelsteps.com is measured): page views, referrers, countries, UTM sources, and events `plan_view` (builder opened, any language), `plan_template`, `plan_copy_import` (unit, step count, text length), `plan_copy_prompt`, `plan_load_import` (ok), `plan_error` (validation code, once per visit), `donate_click` (provider), `faq_open` (question number); all carry the page language, none carry schedule text
- SEO: canonical + hreflang per page, Open Graph, `SoftwareApplication`, `FAQPage`, `WebSite` and `WebPage` JSON-LD, sitemap with language alternates, responsive WebP; IndexNow ping (Bing, Yandex, …) after every deploy (`python build.py indexnow`, key file at the root)
- Language: the home page sends first-time visitors to their browser language (nl, de, fr, es, it); a choice in the switcher is remembered (localStorage `fuelsteps-lang`) and always wins
- Moving to another domain: change `BASE` in `build.py` and rebuild
- Connect IQ Store: the official badge in the hero (`img/connect-iq-badge.svg`, unaltered per Garmin's brand guidelines), a Download button in the header and menu, a link in install step 1 and `downloadUrl` in the JSON-LD, each to the store page in the page language (`apps.garmin.com/<locale>/apps/<STORE_ID>`); Umami event `store_click` (lang)

If you like FuelSteps: [donate via bunq (card, iDEAL | Wero, Bancontact)](https://bunq.me/fuelsteps) or [PayPal](https://paypal.me/rdbruijn)
