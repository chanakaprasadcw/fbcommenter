"""
Facebook Auto-Commenting System

Automatically posts comments on a Facebook post using the Graph API.
Supports single comments, bulk comments from a file, and scheduled commenting.
"""

import os
import sys
import time
import argparse
import requests
from dotenv import load_dotenv

load_dotenv()

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


def get_config():
    """Load configuration from environment variables."""
    token = os.getenv("FB_ACCESS_TOKEN")
    post_id = os.getenv("FB_POST_ID")
    if not token:
        print("Error: FB_ACCESS_TOKEN not set. See .env.example")
        sys.exit(1)
    return token, post_id


def post_comment(post_id, message, token):
    """Post a single comment on a Facebook post.

    Args:
        post_id: The Facebook post ID (format: {page_id}_{post_id})
        message: The comment text
        token: Facebook Graph API access token

    Returns:
        dict with the API response, or None on failure
    """
    url = f"{GRAPH_API_BASE}/{post_id}/comments"
    params = {"access_token": token, "message": message}

    try:
        resp = requests.post(url, data=params, timeout=30)
        data = resp.json()

        if "error" in data:
            print(f"API Error: {data['error'].get('message', 'Unknown error')}")
            return None

        print(f"Comment posted successfully (ID: {data.get('id', 'N/A')})")
        return data

    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None


def post_comments_from_file(post_id, filepath, token, delay=5):
    """Post multiple comments from a text file (one comment per line).

    Args:
        post_id: The Facebook post ID
        filepath: Path to file with comments (one per line)
        token: Facebook Graph API access token
        delay: Seconds to wait between comments (default: 5)
    """
    if not os.path.isfile(filepath):
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    with open(filepath, "r") as f:
        comments = [line.strip() for line in f if line.strip()]

    if not comments:
        print("No comments found in file.")
        return

    print(f"Posting {len(comments)} comments with {delay}s delay between each...")

    for i, comment in enumerate(comments, 1):
        print(f"\n[{i}/{len(comments)}] Posting: {comment[:50]}{'...' if len(comment) > 50 else ''}")
        result = post_comment(post_id, comment, token)

        if result is None:
            print("Stopping due to error.")
            break

        if i < len(comments):
            print(f"Waiting {delay}s...")
            time.sleep(delay)

    print(f"\nDone. Posted {i} comment(s).")


def get_post_comments(post_id, token, limit=25):
    """Fetch existing comments on a post.

    Args:
        post_id: The Facebook post ID
        token: Facebook Graph API access token
        limit: Max number of comments to retrieve

    Returns:
        list of comment dicts, or empty list on failure
    """
    url = f"{GRAPH_API_BASE}/{post_id}/comments"
    params = {"access_token": token, "limit": limit}

    try:
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()

        if "error" in data:
            print(f"API Error: {data['error'].get('message', 'Unknown error')}")
            return []

        return data.get("data", [])

    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Facebook Auto-Commenting System")
    parser.add_argument("--post-id", help="Facebook post ID (overrides .env)")
    parser.add_argument("--comment", "-c", help="Single comment to post")
    parser.add_argument("--file", "-f", help="File with comments (one per line)")
    parser.add_argument("--delay", "-d", type=int, default=5,
                        help="Delay in seconds between comments (default: 5)")
    parser.add_argument("--list", "-l", action="store_true",
                        help="List existing comments on the post")
    parser.add_argument("--limit", type=int, default=25,
                        help="Max comments to list (default: 25)")

    args = parser.parse_args()
    token, env_post_id = get_config()
    post_id = args.post_id or env_post_id

    if not post_id:
        print("Error: No post ID provided. Use --post-id or set FB_POST_ID in .env")
        sys.exit(1)

    if args.list:
        comments = get_post_comments(post_id, token, args.limit)
        if comments:
            for c in comments:
                print(f"[{c.get('id')}] {c.get('from', {}).get('name', 'Unknown')}: {c.get('message', '')}")
        else:
            print("No comments found.")

    elif args.comment:
        post_comment(post_id, args.comment, token)

    elif args.file:
        post_comments_from_file(post_id, args.file, token, args.delay)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
