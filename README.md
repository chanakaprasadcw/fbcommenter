# Facebook Auto-Commenting System

Automatically post comments on Facebook posts using the Graph API.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   ```

3. Get a Facebook access token from the [Graph API Explorer](https://developers.facebook.com/tools/explorer/) with `publish_actions` or `pages_manage_engagement` permission and add it to `.env`.

4. Set your target post ID in `.env`.

## Usage

**Post a single comment:**
```bash
python fb_commenter.py --comment "Great post!"
```

**Post multiple comments from a file (one per line):**
```bash
python fb_commenter.py --file comments.txt --delay 10
```

**List existing comments on a post:**
```bash
python fb_commenter.py --list
```

**Override post ID from command line:**
```bash
python fb_commenter.py --post-id 123456_789012 --comment "Hello!"
```

## Options

| Flag | Description |
|------|-------------|
| `--post-id` | Facebook post ID (overrides .env) |
| `-c, --comment` | Single comment text |
| `-f, --file` | File with comments (one per line) |
| `-d, --delay` | Seconds between comments (default: 5) |
| `-l, --list` | List existing comments |
| `--limit` | Max comments to list (default: 25) |
