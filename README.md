# The Mac Alchemist — Site

Auto-updating website for [theMacAlchemist.com](https://theMacAlchemist.com).

- **Blog posts** sync automatically from Medium every day
- **App recommendations** are managed via `apps.json` — edit on GitHub, done
- **Featured guides** are managed via `featured.json`
- **App icons** are fetched automatically from the App Store on each build

---

## One-time Setup (15 minutes)

### Step 1 — Create a GitHub repo

1. Go to [github.com/new](https://github.com/new)
2. Name it `mac-alchemist-site` (or whatever you like)
3. Set it to **Public**
4. Click **Create repository**

### Step 2 — Upload these files

In the new repo, click **Add file → Upload files** and upload everything in this folder — keeping the folder structure intact (the `.github/workflows/` folder is important).

> **Tip:** It's easiest to zip this entire folder and drag it in, then GitHub will ask you to confirm the structure.

### Step 3 — Connect Cloudflare Pages

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) → **Pages** → **Create a project**
2. Click **Connect to Git** → select your GitHub repo
3. In the build settings:
   - **Build command:** *(leave blank)*
   - **Build output directory:** `/` *(or leave blank)*
4. Click **Save and Deploy**

Your site will now deploy whenever `index.html` is updated in the repo.

### Step 4 — Trigger the first build (get real app icons)

1. In your GitHub repo, click the **Actions** tab
2. Click **Sync Medium Posts & Deploy**
3. Click **Run workflow** → **Run workflow**

This fetches real App Store icons for all 59 apps and syncs your latest Medium posts. After it finishes (about 2 minutes), Cloudflare Pages will auto-deploy the updated site.

### Step 5 — Add your logo

Upload your `mac-alchemist-logo.jpg` file to the root of the repo. It's already referenced in the HTML.

---

## Ongoing: Adding or Removing Apps

1. Go to your GitHub repo
2. Click `apps.json`
3. Click the pencil icon (Edit)
4. Add a new app by copying an existing entry and changing the values, **or** delete an entry to remove an app
5. Click **Commit changes**

The site rebuilds automatically within a few minutes.

### App fields explained

| Field | What it does |
|---|---|
| `name` | Display name of the app |
| `url` | Link to the app's website or App Store page |
| `category` | Slug used for filtering (e.g. `productivity`, `utilities`) |
| `category_label` | Display name for the category filter button |
| `pricing` | One of: `free`, `paid`, `subscription`, `setapp` |
| `icon` | Single letter shown if the App Store icon can't be found |
| `description` | Short description shown on the card |
| `search_term` | What to search on iTunes — use this if the app name is ambiguous |
| `is_ios` | `true` for iOS-only apps so icons are pulled from the iOS store |

### Example: Adding a new app

```json
{
  "name": "Obsidian",
  "url": "https://obsidian.md/",
  "category": "productivity",
  "category_label": "Productivity",
  "pricing": "free",
  "icon": "O",
  "description": "The second brain that actually makes sense.",
  "search_term": "Obsidian markdown notes",
  "is_ios": false
}
```

---

## Ongoing: Updating Featured Guides

The "Essential Mac Guides" section is controlled by `featured.json`. Same process: edit the file on GitHub, commit, done.

---

## How It All Works

```
You publish on Medium
       ↓
GitHub Action runs daily at 7am UTC
       ↓
build.py fetches your Medium RSS feed
       ↓
build.py reads apps.json + featured.json
       ↓
build.py fetches missing app icons from iTunes API
       ↓
index.html is regenerated and committed
       ↓
Cloudflare Pages detects the new commit
       ↓
Your site is live with fresh content ✓
```

Editing `apps.json` or `featured.json` on GitHub also triggers an immediate rebuild.

---

## Files Reference

| File | Purpose |
|---|---|
| `index.html` | The live website (auto-generated — don't edit directly) |
| `template.html` | The HTML template (edit this to change the site design) |
| `apps.json` | All app recommendations |
| `featured.json` | The featured guide cards in the "Essential Mac Guides" section |
| `icon_cache.json` | Cached App Store icon URLs (auto-managed) |
| `build.py` | The build script |
| `.github/workflows/sync-medium.yml` | The daily GitHub Action |
