"""
Facebook Auto-Commenting System (Selenium + AI)

Automatically posts replies on a Facebook post using Selenium.
Supports:
- Attaching to an existing Chrome window (Remote Debugging)
- Context-aware replies using OpenAI (GPT)
- Manual Login fallback
"""

import os
import sys
import time
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv
import openai

load_dotenv()

def get_config():
    """Load configuration from environment variables."""
    email = os.getenv("FB_EMAIL")
    password = os.getenv("FB_PASSWORD")
    post_url = os.getenv("FB_POST_URL")
    openai_key = os.getenv("OPENAI_API_KEY")
    debug_address = os.getenv("CHROME_DEBUGGER_ADDRESS")
    fb_name = os.getenv("FB_NAME", "You") # Default to "You" if not set
    
    return email, password, post_url, openai_key, debug_address, fb_name

def setup_driver(debug_address=None):
    """Initialize Chrome WebDriver, optionally connecting to an existing instance."""
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-notifications")
    options.add_argument("--start-maximized")
    
    if debug_address:
        print(f"Attempting to connect to existing Chrome at {debug_address}...")
        options.add_experimental_option("debuggerAddress", debug_address)
    
    try:
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
        return driver
    except Exception as e:
        print(f"Failed to setup driver: {e}")
        if debug_address:
            print("Ensure Chrome is running with: --remote-debugging-port=9222")
        sys.exit(1)

def get_profile_context(driver, profile_url):
    """
    Opens profile in a new tab, scrapes intro/posts, closes tab.
    Returns a string of context or None.
    """
    if not profile_url:
        return None
        
    print(f"Scraping profile: {profile_url} ...")
    original_window = driver.current_window_handle
    context = ""
    
    try:
        # Open new tab
        driver.switch_to.new_window('tab')
        driver.get(profile_url)
        time.sleep(5) # Wait for profile load
        
        # Scrape Intro
        try:
            # Intro is often in a specific container, but text search is easier
            # Look for typical intro text containers
            # This is fragile. We'll try to get the whole body text and truncate? No, too messy.
            # Let's look for "Intro" header and text following it.
            intro_elements = driver.find_elements(By.XPATH, "//span[text()='Intro']/ancestor::div[3]")
            if intro_elements:
                 intro_text = intro_elements[0].text.replace("\n", " ")
                 context += f"Profile Intro: {intro_text}. "
                 print("Found Intro.")
        except:
            pass
            
        # Scrape Latest Post (Best Effort)
        try:
            # Look for the first post container. 
            # Posts usually have aria-posinset="1" or are the first div role="article"
            posts = driver.find_elements(By.XPATH, "//div[@role='article']")
            if posts:
                # The first one might be the pinning or the intro box depending on layout
                # We try to get text from the first substantial one
                for post in posts[:2]:
                    text = post.text.replace("\n", " ").strip()
                    if len(text) > 50: # Skip empty/small controls
                        context += f"Recent Activity: {text[:300]}... "
                        print("Found Recent Activity.")
                        break
        except:
            pass
            
    except Exception as e:
        print(f"Profile scrape failed: {e}")
    finally:
        # Close tab and return
        try:
            driver.close()
        except:
            pass
        driver.switch_to.window(original_window)
        
    return context if len(context) > 10 else None

def generate_ai_reply(comment_text, author_name, api_key, profile_context=None):
    """Generate a reply using OpenAI."""
    if not api_key:
        return None
        
    try:
        client = openai.OpenAI(api_key=api_key)
        
        context_instruction = ""
        if profile_context:
            context_instruction = (
                f"Information about the user '{author_name}': {profile_context}\n"
                f"Use this information to make the reply personal and relevant to them. "
                f"Mention something nice about their profile or recent value if applicable, but keep it natural."
            )
        
        prompt = (
            f"A user named '{author_name}' commented: '{comment_text}'.\n"
            f"{context_instruction}\n"
            f"Write a nice, friendly, and personal reply. "
            f"Do not ask for inquiries, business, or sales. "
            f"Do not sound corporate or like a bot. "
            f"Do not use hashtags. Keep it under 2 sentences."
        )
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a friendly personal Facebook user replying to friends or followers."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=60,
            temperature=0.7
        )
        
        reply = response.choices[0].message.content.strip()
        # Remove any surrounding quotes
        if reply.startswith('"') and reply.endswith('"'):
            reply = reply[1:-1]
            
        print(f"AI Generated Reply: {reply}")
        return reply
        
    except Exception as e:
        print(f"AI Generation failed: {e}")
        return None
    
def load_more_comments(driver):
    """
    Scrolls down and clicks 'View more comments' buttons until none are found or limit reached.
    Also tries to switch to 'All comments' if possible.
    """
    print("Attempting to load all comments...")
    
    # Scroll to bottom to trigger lazy loading
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)
    
    # 1. Try to switch to "All comments"
    try:
        # Find dropdown trigger often containing "Most relevant"
        triggers = driver.find_elements(By.XPATH, "//span[contains(text(), 'Most relevant')]")
        if triggers:
            # Check if visible
            trigger = triggers[0]
            if trigger.is_displayed():
                print("Found comment filter. Attempting to switch to 'All comments'...")
                driver.execute_script("arguments[0].click();", trigger)
                time.sleep(2)
                
                # Click "All comments" in the menu
                # Note: This is an approximation. Facebook UI classes change often.
                # We look for the text "All comments"
                all_comments_opts = driver.find_elements(By.XPATH, "//span[contains(text(), 'All comments')]")
                for opt in all_comments_opts:
                    if opt.is_displayed():
                        driver.execute_script("arguments[0].click();", opt)
                        print("Switched to 'All comments'.")
                        time.sleep(3)
                        break
    except Exception as e:
        print(f"Could not switch comment filter (non-critical): {e}")

    # 2. Expand View More
    # We loop until no buttons are found or for a max number of iterations
    max_loops = 50 # Increased to 50 to load more comments
    consecutive_no_clicks = 0
    
    for i in range(max_loops):
        try:
            print(f"Comment Expansion Loop {i+1}/{max_loops}...")
            
            # Scroll to bottom again to ensure lazy loading triggers
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            # Look for typical "View more comments" buttons
            # Facebook text often: "View more comments", "View 1 more comment", "View previous comments", "See more"
            # Also "View replies" to ensure nested comments are seen? 
            # Note: Expanding EVERY reply might be too much, but user wants ALL.
            view_more_btns = driver.find_elements(By.XPATH, 
                "//span[contains(text(), 'View more') and contains(text(), 'comment')] | "
                "//span[contains(text(), 'View previous comments')] | "
                "//span[contains(text(), 'See more')] | "
                "//div[contains(text(), 'View more comments')] | "
                "//span[contains(text(), 'View') and contains(text(), 'replies')]")
            
            visible_btns = [b for b in view_more_btns if b.is_displayed()]
            
            if not visible_btns:
                consecutive_no_clicks += 1
                if consecutive_no_clicks > 2: # Stop if we didn't find anything 3 times in a row
                    print("No more 'View more' buttons found.")
                    break
                else:
                    time.sleep(2)
                    continue
            
            consecutive_no_clicks = 0
            print(f"Found {len(visible_btns)} 'View more/replies' buttons. Clicking...")
            
            clicked_count = 0
            for btn in visible_btns:
                try:
                    # Scroll to avoid header obstructions
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", btn)
                    clicked_count += 1
                    time.sleep(1) 
                except:
                    pass
            
            if clicked_count == 0:
                 # If we found elements but failed to click any, maybe we are done or blocked
                 break
                
            print(f"Clicked {clicked_count} buttons. Waiting for content reload...")
            time.sleep(4) # Wait longer for content to load
            
        except Exception as e:
            print(f"Error during expansion: {e}")
            break

def is_already_replied(driver, reply_btn, fb_name):
    """
    Check if the comment has already been replied to by the user.
    """
    try:
        # 1. Get the parent container of the comment
        # The reply button is usually in a list of actions under the comment body
        # Structure: Comment Div -> ... -> Actions Div -> [Like, Reply...]
        # Replies are usually in a sibling div or a nested list.
        
        # We traverse up to find the main container for this comment thread
        parent = reply_btn
        for _ in range(6):
            parent = parent.find_element(By.XPATH, "..")
            # Heuristic: Container usually has role="article" or aria-label
            if parent.get_attribute("role") == "article":
                break
        
        # 2. Search for our name in valid author links within this container
        # We avoid matching the name if it's just mentioned in text.
        # Authors are usually links.
        links = parent.find_elements(By.TAG_NAME, "a")
        for link in links:
            txt = link.text.strip()
            # If our name is found in a link, and it's not the 'Reply' button itself
            if fb_name.lower() in txt.lower() and len(txt) < len(fb_name) + 5:
                # We found a link with our name.
                # Just need to be sure it's an author name, not "Reply to [Name]"
                # Usually author names are bold or have specific classes, but verifying that is hard.
                # Simplest check: Is this link appearing AFTER the main comment?
                # This is hard to determine in DOM order easily for all layouts.
                
                # Assume if our name appears as a link in the thread, we participated.
                return True
                
    except Exception as e:
        # If check fails, assume safe to reply to avoid skipping valid ones (user preference)
        # print(f"Warning: Duplicate check failed {e}")
        pass
        
    return False

def reply_to_comments(driver, post_url, default_message, delay=45, openai_key=None, fb_name="You"):
    """Navigate to a post and reply to all visible comments."""
    if post_url:
        print(f"Navigating to post: {post_url}")
        driver.get(post_url)
    else:
        print("No URL provided, assuming already on correct page...")
    
    try:
        print("Waiting for comments to load...")
        time.sleep(5)
        
        # Load all comments
        load_more_comments(driver)
        
        # Strategy: Find Comment Containers
        # We look for aria-label starting with "Comment by" or similar structure
        # A common generic container for a comment often has aria-label="Comment by [Name]"
        
        # DEBUG: Take screenshot
        try:
             driver.save_screenshot("debug_after_loading.png")
             print("Saved screenshot to 'debug_after_loading.png'. Please check this image!")
        except Exception as e:
             print(f"Could not save debug screenshot: {e}")
        
        # This xpath looks for the comment article/container
        # Note: Selectors are fragile. We try to find the "Reply" button and work backwards/sideways to find context.
        
        # Find all "Reply" buttons first as they are our action targets
        # Expanded selector: Case insensitive "Reply", various roles.
        reply_buttons = driver.find_elements(By.XPATH, 
             "//div[@role='button'][translate(text(), 'REPLY', 'reply')='reply'] | "
             "//span[translate(text(), 'REPLY', 'reply')='reply'] | "
             "//a[@role='button'][translate(text(), 'REPLY', 'reply')='reply']")
             
        visible_reply_buttons = [btn for btn in reply_buttons if btn.is_displayed()]
        
        print(f"Found {len(visible_reply_buttons)} visible 'Reply' buttons.")
        
        if len(visible_reply_buttons) == 0:
             print("DEBUG INFO: No 'Reply' buttons found.")
             print("Possible reasons: 1. You are not logged in. 2. Post is private/restricted. 3. Facebook changed the UI.")
             print("Check 'debug_after_loading.png' to see what the script sees.")
        
        count = 0
        for i, btn in enumerate(visible_reply_buttons):
            try:
                print(f"[{i+1}/{len(visible_reply_buttons)}] Processing...")
                
                # Context Extraction (Best Effort)
                author_name = "User"
                comment_text = ""
                profile_context = None
                
                try:
                    # Move up from the Reply button to find the comment container
                    # Reply button -> List item or Actions -> Comment Body
                    # This is very structure dependent. 
                    # Alternative: Look for the nearest 'dir="auto"' div which usually contains the text
                    
                    # Simple heuristic: The comment text is usually in a div with dir="auto" nearby the reply action
                    # Author name is usually an anchor tag nearby
                    
                    # Try to extract Author Name & Profile URL
                    # Go up to a common parent (e.g., the comment article)
                    # We look for an anchor tag with href containing 'user', 'profile.php' or simply isn't a hashtag/post link
                    parent_block = btn.find_element(By.XPATH, "./ancestor::div[@role='article'][1]")
                    
                    # Find Author Name Link
                    # usually <a role="link" tabindex="0">Name</a> inside the header of the comment
                    # or just the first link with text
                    links = parent_block.find_elements(By.TAG_NAME, "a")
                    for link in links:
                        href = link.get_attribute("href")
                        text = link.text
                        if href and text and len(text) > 2 and "comment" not in href and "photo" not in href:
                             author_name = text
                             # Clean URL (remove query params for safety/cleanliness although args might be needed)
                             if "profile.php" in href:
                                 profile_url = href
                             else:
                                 profile_url = href.split("?")[0]
                             
                             print(f"Identified Author: {author_name} ({profile_url})")
                             
                             # GET PROFILE CONTEXT
                             # We only do this if we have an API key (otherwise useless)
                             if openai_key:
                                 profile_context = get_profile_context(driver, profile_url)
                             break
                    
                except Exception as e:
                    print(f"Extraction warning: {e}")

                # Scroll to button
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn)
                time.sleep(1)
                
                # DUPLICATE CHECK EXECUTION
                if is_already_replied(driver, btn, fb_name):
                    print(f"Skipping comment (Already replied by {fb_name}).")
                    continue
                
                # Click Reply
                try:
                    btn.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", btn)
                
                time.sleep(2)
                
                # Switch to active element (the input box)
                active_element = driver.switch_to.active_element
                
                # Generate Message
                message_to_send = default_message
                
                # Try AI generation if key exists, even if author is unknown (use 'friend')
                if openai_key:
                     # Use "friend" if name extraction failed
                     target_name = author_name if author_name != "User" else "friend"
                     ai_reply = generate_ai_reply(f"(Comment text unavailable)", target_name, openai_key, profile_context)
                     if ai_reply:
                         message_to_send = ai_reply

                # Fail-safe: Ensure we never send None
                if not message_to_send:
                     message_to_send = "Thanks for the comment!"
                     print("Warning: Used hardcoded fallback message as AI and default failed.")

                print(f"Typing reply: {message_to_send}")
                active_element.send_keys(message_to_send)
                time.sleep(1)
                active_element.send_keys(Keys.RETURN)
                
                print("Reply sent.")
                count += 1
                
                print(f"Waiting {delay}s before next reply...")
                time.sleep(delay)
                
            except Exception as e:
                print(f"Failed to reply to comment {i+1}: {e}")
                continue
                
        print(f"Finished. Replied to {count} comments.")
        return True
        
    except Exception as e:
        print(f"Error during reply process: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Facebook Auto-Commenter (Selenium + AI)")
    parser.add_argument("--url", help="Facebook post URL")
    parser.add_argument("--comment", "-c", help="Default comment if AI fails")
    parser.add_argument("--delay", "-d", type=int, default=45, help="Delay in seconds")
    parser.add_argument("--attach", action="store_true", help="Attach to existing Chrome (localhost:9222)")
    
    args = parser.parse_args()
    
    email, password, env_url, openai_key, debug_address, fb_name = get_config()
    print(f"Configuration Loaded: User='{fb_name}'")
    post_url = args.url or env_url
    
    # Validation
    if not args.attach:
        if not post_url:
             print("Error: Post URL required unless attaching to existing session manually.")
             # We allow proceeding if attach is true, assuming user is on the page
    
    if not args.comment and not openai_key:
        # If no AI, we need a comment
        try:
             args.comment = input("Enter default reply message: ")
        except KeyboardInterrupt:
             sys.exit(0)

    # Setup Driver
    debugger = debug_address if args.attach else None
    driver = setup_driver(debugger)
    
    try:
        if not args.attach:
            # Login Flow
            print("\n" + "="*50)
            print("BROWSER OPENED. PLEASE LOG IN MANUALLY.")
            print("1. Go to the browser window.")
            print("2. Log in to Facebook.")
            print("3. Navigate to the Home page or keep it open.")
            print("="*50 + "\n")
            
            driver.get("https://www.facebook.com")
            input("Press Enter here AFTER you have successfully logged in...")
        else:
            print(f"Attached to browser. Assuming you are logged in.")

        # Continuous Processing Loop
        while True:
            print("\n" + "-"*30)
            if post_url:
                current_url = post_url
                post_url = None # Clear it so we don't reuse it next loop
            else:
                try:
                    current_url = input("Enter Facebook Post URL (or 'q' to quit): ").strip()
                except KeyboardInterrupt:
                    break
            
            if current_url.lower() in ['q', 'quit', 'exit']:
                break
                
            if not current_url:
                continue

            print(f"\nProcessing: {current_url}")
            reply_to_comments(driver, current_url, args.comment, args.delay, openai_key, fb_name)
            print("Finished processing post.")
        
    finally:
        if not args.attach:
            print("Closing browser in 5 seconds...")
            time.sleep(5)
            driver.quit()
        else:
            print("Detaching from browser (leaving it open).")

if __name__ == "__main__":
    main()
