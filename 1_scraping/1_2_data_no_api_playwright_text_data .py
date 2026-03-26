"""
Map review scraper (Playwright).

Reads restaurant CSV. For each place opens the reviews tab scrolls and saves.
Resumes from temp if present.
Use SPLIT even or odd when two browsers run together so temp files stay separate.
"""
import os
import re
import sys
import time
import random
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout

# big outputs on external disk / edit EXTERNAL_DRIVE if your mount path differs
EXTERNAL_DRIVE = Path("/Volumes/data_out/ai_goole_map_data")
# point pyc + chromium at that disk via these two env vars
CACHE_DIR = EXTERNAL_DRIVE / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
(CACHE_DIR / "pycache").mkdir(parents=True, exist_ok=True)
(CACHE_DIR / "playwright_browsers").mkdir(parents=True, exist_ok=True)
os.environ["PYTHONPYCACHEPREFIX"] = str(CACHE_DIR / "pycache")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(CACHE_DIR / "playwright_browsers")
# first time no browser yet / run playwright install chromium with PLAYWRIGHT_BROWSERS_PATH set

INPUT_DIR = EXTERNAL_DRIVE / "Data1_Information(R_Info)"
OUTPUT_DIR = EXTERNAL_DRIVE / "Data2_Information(Review_Text)"

# change REGION here / same as api OUTPUT_SUFFIX so csv names match
REGION = "mitte"
INPUT_FILE = INPUT_DIR / f"restaurants_{REGION}.csv"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# lower if too slow / raise again if timeouts pile up
SAVE_INTERVAL = 50
SAVE_EVERY_N_REVIEWS = 100
MAX_SCROLLS = 5000
MAX_REVIEWS_PER_PLACE = 200

# odd vs even row split for two processes / single run just leave even
SPLIT = "even"

# timeouts ms / scroll pacing is the sleeps later
CARD_PARSE_TIMEOUT = 200
MORE_BTN_TIMEOUT = 30
SORT_BTN_TIMEOUT = 1500
DROPDOWN_TIMEOUT = 3000
SCROLL_PX = 3500
NO_NEW_LIMIT = 5  # stop after this many passes with no new cards

# even or odd in temp name so two runs do not share one file
temp_suffix = SPLIT if SPLIT in ("odd", "even") else "all"
TEMP_CSV_PATH = OUTPUT_DIR / f"reviews_{REGION}_raw_temp_{temp_suffix}.csv"

# log to console and to file
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(OUTPUT_DIR / f"scraping_{REGION}.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

print("=" * 60, flush=True)
print(f"start region {REGION} split {SPLIT}", flush=True)
print(f"root {EXTERNAL_DRIVE}", flush=True)
print(f"out {OUTPUT_DIR}", flush=True)
print(f"cache {CACHE_DIR}", flush=True)
print("=" * 60, flush=True)

if not INPUT_FILE.exists():
    raise FileNotFoundError(f"missing csv {INPUT_FILE}")

res_df = pd.read_csv(INPUT_FILE)
print(f"got {len(res_df)} rows", flush=True)

# resume temp / ids compared as strings
already_collected = set()
all_reviews = []
print(f"temp path {TEMP_CSV_PATH}", flush=True)
if TEMP_CSV_PATH.exists():
    try:
        existing_df = pd.read_csv(TEMP_CSV_PATH, encoding="utf-8-sig")
        col = "restaurant_id"
        if col not in existing_df.columns:
            col = next((c for c in existing_df.columns if "restaurant" in c.lower() or c.strip() == "restaurant_id"), None)
        if col:
            already_collected = set(existing_df[col].astype(str).str.strip().unique())
            all_reviews = existing_df.to_dict("records")
            print(f"skipping {len(already_collected)} places already done {len(all_reviews)} rows in temp", flush=True)
        else:
            print("temp missing restaurant_id column / starting from scratch", flush=True)
    except Exception as e:
        log.warning("temp load failed %s", e)
        print(f"temp read error {e} / starting from scratch", flush=True)
else:
    print("no temp file / full run", flush=True)


def _pid(p):
    return str(p).strip()


def _keep_by_split(index: int) -> bool:
    """even keeps even rows odd keeps odd."""
    if SPLIT == "even":
        return index % 2 == 0
    if SPLIT == "odd":
        return index % 2 == 1
    return True


to_process = [
    row
    for i, (_, row) in enumerate(res_df.iterrows())
    if _pid(row["restaurant_id"]) not in already_collected
    and _keep_by_split(i)
]
print(f"queue {len(to_process)} out of {len(res_df)}", flush=True)
if to_process:
    print(f"first place {to_process[0].get('r_name', to_process[0].get('name', '?'))}", flush=True)
if len(to_process) == 0:
    print("nothing to do / change REGION or delete temp and retry", flush=True)
    sys.exit(0)


def _dismiss_consent_if_present(page: Page) -> None:
    # consent popup click Accept manually / no automation here
    return


def set_reviews_sort_newest(page: Page) -> bool:
    # open Sort then choose Newest
    try:
        sort_btn = page.locator(
            "button[aria-label*='Sort'], button:has-text('Sort')"
        ).first
        if not sort_btn.is_visible(timeout=SORT_BTN_TIMEOUT):
            print("sort button not visible", flush=True)
            return False

        sort_btn.click(timeout=2000, force=True)

        page.wait_for_selector("[role='menu']", timeout=DROPDOWN_TIMEOUT)

        newest_btn = page.locator(
            "[role='menu'] [role='menuitemradio']:has-text('Newest')"
        ).first
        if not newest_btn.is_visible(timeout=SORT_BTN_TIMEOUT):
            print("no newest option", flush=True)
            return False

        newest_btn.click(timeout=2000, force=True)
        page.wait_for_timeout(800)
        return True

    except Exception as e:
        print(f"sort failed {e}", flush=True)
        return False


def _years_ago_from_label(label: str) -> Optional[int]:
    # year count from strings like "3 years ago"
    s = (label or "").strip().lower()
    # strip edited prefix
    s = re.sub(r"^edited\s+", "", s)
    if not s:
        return None
    if "year ago" in s and s.startswith("a "):
        return 1
    m = re.search(r"(\d+)\s+years?\s+ago", s)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def open_reviews_tab(page: Page, place_id: str) -> bool:
    url = f"https://www.google.com/maps/place/?q=place_id:{place_id}&hl=en"
    t0 = time.perf_counter()

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)

        _dismiss_consent_if_present(page)

        review_tab = page.locator(
            "//button[@role='tab'][.//div[contains(text(),'Review')]]"
        ).first
        review_tab.click(timeout=8000)
        page.wait_for_selector("div.jftiEf", timeout=4000)

        # networkidle once before sort
        try:
            page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass

        set_reviews_sort_newest(page)
        elapsed = time.perf_counter() - t0
        print(f"opened in {elapsed:.1f}s", flush=True)
        log.info("opened %.1fs", elapsed)
        return True

    except PlaywrightTimeout:
        log.warning("no reviews tab %s", place_id)
        return False
    except Exception as e:
        log.error("open failed %s %s", place_id, e)
        return False


def scroll_and_extract(
    page: Page,
    place_id: str,
    r_name: str,
    on_progress: Optional[Callable[[list], None]] = None,
) -> list:
    # scroll and on_progress saves temp / stop this place past 2y reviews
    collected = []
    seen_texts = set()
    no_new_count = 0
    scroll_count = 0
    first_time_logged = False
    last_saved_at = 0

    try:
        scroll_area = page.locator("div.m6QErb.DxyBCb").first
    except Exception as e:
        log.warning("scroll container missing %s %s", r_name, e)
        return collected

    while True:
        if scroll_count >= MAX_SCROLLS:
            log.warning("max scroll hit %s", r_name)
            break

        if len(collected) >= MAX_REVIEWS_PER_PLACE:
            print(f"hit max {MAX_REVIEWS_PER_PLACE} reviews / next place", flush=True)
            if on_progress and collected and (len(collected) - last_saved_at) > 0:
                on_progress(collected)
                last_saved_at = len(collected)
            break

        scroll_count += 1
        review_cards = page.locator("div.jftiEf").all()
        new_found = 0
        reached_cutoff = False

        for card in review_cards:
            try:
                more_btn = card.locator("button.w8nwRe").first
                if more_btn.is_visible(timeout=MORE_BTN_TIMEOUT):
                    more_btn.click()
                    page.wait_for_timeout(50)
            except Exception:
                pass

            try:
                text_en = card.locator("span.wiI7pd").inner_text(timeout=CARD_PARSE_TIMEOUT) or ""
                user_name = card.locator("div.d4r55").inner_text(timeout=CARD_PARSE_TIMEOUT) or ""
                pt_rating = card.locator("span.kvMYJc").get_attribute("aria-label", timeout=CARD_PARSE_TIMEOUT) or ""
                review_time = card.locator("span.rsqaWe").inner_text(timeout=CARD_PARSE_TIMEOUT) or ""

                years_ago = _years_ago_from_label(review_time)
                if years_ago is not None and years_ago > 2:
                    reached_cutoff = True
                    continue

                if not text_en:
                    continue
                if text_en in seen_texts:
                    continue
                seen_texts.add(text_en)

                if not first_time_logged:
                    print(f"first review time {review_time}", flush=True)
                    first_time_logged = True

                collected.append({
                    "restaurant_id": place_id,
                    "r_name": r_name,
                    "user_name": user_name,
                    "pt_rating": pt_rating,
                    "review_time": review_time,
                    "review_text_en": text_en,
                })
                new_found += 1
                # temp every N plus once right after first grab
                if on_progress and (
                    (len(collected) - last_saved_at) >= SAVE_EVERY_N_REVIEWS
                    or (len(collected) > 0 and last_saved_at == 0)
                ):
                    on_progress(collected)
                    last_saved_at = len(collected)

            except Exception as e:
                log.debug("card parse skipped %s", e)
                continue

        if reached_cutoff:
            print("saw review older than 2y / stopping this place", flush=True)
            if on_progress and collected and (len(collected) - last_saved_at) > 0:
                on_progress(collected)
                last_saved_at = len(collected)
            break

        if new_found == 0:
            no_new_count += 1
        else:
            no_new_count = 0

        if no_new_count >= NO_NEW_LIMIT:
            if on_progress and collected:
                on_progress(collected)
                last_saved_at = len(collected)
            break

        try:
            scroll_area.evaluate(f"el => el.scrollBy(0, {SCROLL_PX})")
        except Exception:
            page.mouse.wheel(0, SCROLL_PX)

        if new_found == 0:
            time.sleep(random.uniform(0.08, 0.18))
        else:
            time.sleep(random.uniform(0.05, 0.12))

    if on_progress and collected and (len(collected) - last_saved_at) > 0:
        on_progress(collected)
    return collected


failed_ids = []

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,  # visible window works better on maps here
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        locale="en-US",
        viewport={"width": 500, "height": 950},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    )
    page = context.new_page()

    # block images for speed / remove this block if the page breaks
    def _block_images(route):
        if route.request.resource_type == "image":
            route.abort()
        else:
            route.continue_()
    page.route("**/*", _block_images)

    def _save_progress(collected_for_place: list, base_reviews: list) -> None:
        if not collected_for_place:
            return
        temp = base_reviews + collected_for_place
        pd.DataFrame(temp).to_csv(TEMP_CSV_PATH, index=False, encoding="utf-8-sig")
        print(f"temp saved {TEMP_CSV_PATH.name} {len(temp)} rows (+{len(collected_for_place)} this place)", flush=True)
        log.info("temp %s %d rows", TEMP_CSV_PATH.name, len(temp))

    for idx, row in enumerate(to_process, start=1):
        place_id = row["restaurant_id"]
        r_name = row["r_name"]

        try:
            success = open_reviews_tab(page, place_id)
            if not success:
                failed_ids.append({"place_id": place_id, "r_name": r_name})
                continue

            base_reviews = list(all_reviews)

            reviews = scroll_and_extract(
                page, place_id, r_name,
                on_progress=lambda c: _save_progress(c, base_reviews),
            )
            all_reviews.extend(reviews)
            print(f"[{idx}/{len(to_process)}] {r_name} / {len(reviews)} reviews", flush=True)
            if idx % SAVE_INTERVAL == 0 and all_reviews:
                print(f"running total {len(all_reviews)} reviews", flush=True)

            time.sleep(random.uniform(0.08, 0.18))

        except Exception as e:
            log.error("row error %s %s %s", place_id, r_name, e)
            failed_ids.append({"place_id": place_id, "r_name": r_name})
            continue

    browser.close()

# write final csv
reviews_df = pd.DataFrame(all_reviews)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_path = OUTPUT_DIR / f"reviews_{REGION}_raw_{timestamp}.csv"
reviews_df.to_csv(output_path, index=False, encoding="utf-8-sig")

# failed places csv if any
if failed_ids:
    pd.DataFrame(failed_ids).to_csv(OUTPUT_DIR / f"failed_{REGION}.csv", index=False, encoding="utf-8-sig")

total_reviews = len(reviews_df)
unique_restaurants = reviews_df["restaurant_id"].nunique() if total_reviews > 0 else 0
avg_reviews_per_restaurant = total_reviews / unique_restaurants if unique_restaurants > 0 else 0

print(
    f"\nfinished {total_reviews} reviews avg {avg_reviews_per_restaurant:.1f} per place "
    f"{len(failed_ids)} failed",
    flush=True,
)
print(f"saved {output_path}", flush=True)
if failed_ids:
    print(f"failed list {OUTPUT_DIR / f'failed_{REGION}.csv'}", flush=True)
