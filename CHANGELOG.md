# Changelog

## 2.2.0 (2026-11-20)
- Added the "Crowding-in" project (African firm-level financial dataset) to Research and Projects.

## 2.1.1 (2026-11-20)
- Project data moved from `projects.json` and `files/*/manifest.json` into a single `projects-data.js`, so the page no longer needs `fetch` and works under Live Server, from disk, and on GitHub Pages.

## 2.1.0 (2026-11-20)

### Changed
- Removed the standalone `cybersecurity.html` and `artificial-intelligence.html` pages and their navigation links; both projects are now listed only on `research-projects.html`.
- `research-projects.html` is now data-driven: cards are rendered by `research-projects.js` from `projects.json`, and each card lists its files straight from `files/<folder>/manifest.json`. Adding a project no longer needs any HTML edits.
- Replaced `research-downloads.js` (used only by the removed pages).

## 2.0.0 (2026-11-20)

### Upgraded
- Tailwind CSS: unpinned Play CDN (v3) → **4.3.5**, compiled to `assets/css/tailwind.css` (`npm run build:css`).
- Font Awesome: 6.0.0-beta3 (CDN) → **7.3.1 Free**, self-hosted in `assets/vendor/fontawesome/` (solid and regular only).
- No third-party scripts or styles are loaded at runtime any more.
- Added `package.json` and `package-lock.json` with pinned build dependencies.

### Fixed
- `research-projects.html`: the Cybersecurity card linked to the AI script and methodology; it now links to the cybersecurity files. The AI card now has direct downloads too.
- `cybersecurity.html`: "Research in project" → "Research in progress".
- Each project page and card has its own overview (all three previously repeated the same paragraph).
- `index.html`: removed the duplicated profile paragraph, stray "." in icons, double period, empty `<label>`, and the non-functional search box (it now filters the CV sections).
- `ai_data_extraction_code.py`: fixed the invalid-escape `SyntaxWarning`, corrected the script name in the docstring, and replaced a personal email in the usage example with a placeholder.
- Accessibility and SEO: meta descriptions, decorative images with empty `alt`, `aria-expanded` on the menu toggle, pointer cursor on buttons.
