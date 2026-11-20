# theogene-habimana.github.io (portfolio)

Static academic portfolio. No runtime dependencies; open `index.html` or serve the folder.

## Rebuild the stylesheet
```bash
npm install
npm run build:css   # Tailwind 4 → assets/css/tailwind.css
```
Re-run after adding or changing Tailwind classes in any `*.html` file.

## Adding a project to Research and Projects
1. Create `files/<folder>/` and put the project files in it.
2. Open `projects-data.js`, copy an existing project object, and change `id`, `title`, `icon`, `status`, `folder`, `overview` and the `files` lists (`excel`, `code`, `results`, `methodology`; each item is `{ "title", "path", "description" }`).

The project appears on `research-projects.html` automatically and can be linked as `research-projects.html#<id>`.
No server is needed: the data is a plain script, so the page also works when opened from disk or Live Server.
File names may contain letters, digits, dots, spaces, hyphens and underscores only. Do not publish confidential or licensed data.
