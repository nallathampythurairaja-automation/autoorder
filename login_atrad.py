import time
import os

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
)

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


# ===============================
# ⚠️ LOCAL ONLY (do not upload)
# ===============================
USERNAME = "991860568"
PASSWORD = "KalaiMenan@1974"

LOGIN_URL = "https://onlinetrading.firstcapital.lk/atsweb/login"
FULL_SYMBOL = "CITW.N0000(WASKADUWA BEACH RESORT PLC)"
SYMBOL_SHORT = "CITW.N0000"

QTY = "11"
PRICE = "1.9"


def safe_click(driver, element):
    try:
        element.click()
    except Exception:
        driver.execute_script("arguments[0].click();", element)


def wait_for_preloader_to_disappear(driver, timeout=45):
    end = time.time() + timeout
    while time.time() < end:
        try:
            overlays = driver.find_elements(By.ID, "preloader")
            if not overlays or all(not o.is_displayed() for o in overlays):
                return
        except StaleElementReferenceException:
            pass
        time.sleep(0.2)


def find_dojo_combobox_input(driver, wait, base_id):
    for sel in [
        (By.ID, base_id),
        (By.ID, f"{base_id}_input"),
        (By.CSS_SELECTOR, f"#{base_id} input"),
    ]:
        try:
            el = wait.until(EC.visibility_of_element_located(sel))
            if el.tag_name.lower() == "input":
                return el
        except Exception:
            pass
    raise RuntimeError("ComboBox input not found")


def normalize_num_str(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return s
    try:
        f = float(s.replace(",", ""))
        return f"{f:.10f}".rstrip("0").rstrip(".")
    except Exception:
        return s


def get_input_value(el) -> str:
    v = el.get_attribute("value")
    if v is None:
        try:
            v = el.get_property("value")
        except Exception:
            v = ""
    return (v or "").strip()


def js_dispatch_input_events(driver, el):
    driver.execute_script(
        """
        const el = arguments[0];
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.dispatchEvent(new Event('blur', { bubbles: true }));
        """,
        el,
    )


def set_dojo_number_basic(driver, wait, locator, value: str):
    """Basic typing + TAB commit (works for qty)."""
    el = wait.until(EC.visibility_of_element_located(locator))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    time.sleep(0.1)
    safe_click(driver, el)
    el.send_keys(Keys.CONTROL, "a", Keys.DELETE)
    time.sleep(0.05)
    el.send_keys(value)
    el.send_keys(Keys.TAB)
    time.sleep(0.2)
    return get_input_value(el)


def set_price_dojo(driver, wait, price_value: str, retries: int = 5):
    """
    Strong setter for Dojo price widget:
    1) try dijit.byId(id).set('value', number)
    2) fallback: type into input
    3) verify final value, retry if it snaps back
    """
    target = normalize_num_str(price_value)
    loc = (By.ID, "debtorder_0_spnPrice")

    last_seen = ""
    for attempt in range(1, retries + 1):
        wait_for_preloader_to_disappear(driver, timeout=15)
        el = wait.until(EC.visibility_of_element_located(loc))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.15)

        # --- A) Dojo dijit set('value', ...) (best)
        driver.execute_script(
            """
            const id = arguments[0];
            const valStr = arguments[1];
            const valNum = Number(valStr);

            try {
              if (window.dijit && dijit.byId) {
                const w = dijit.byId(id);
                if (w && w.set) {
                  w.set('value', valNum);
                  if (w.focus) w.focus();
                }
              }
            } catch (e) {}

            // Also try direct input value set (some widgets wrap the real <input>)
            try {
              const el = document.getElementById(id);
              if (el) {
                el.focus();
                el.value = valStr;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.blur();
              }
            } catch (e) {}
            """,
            "debtorder_0_spnPrice",
            price_value,
        )

        time.sleep(0.35)

        # --- Verify
        el2 = wait.until(EC.visibility_of_element_located(loc))
        last_seen = get_input_value(el2)
        if normalize_num_str(last_seen) == target:
            return True, last_seen

        # --- B) Fallback: slow type + events
        try:
            safe_click(driver, el2)
            el2.send_keys(Keys.CONTROL, "a", Keys.DELETE)
            time.sleep(0.05)
            for ch in price_value:
                el2.send_keys(ch)
                time.sleep(0.04)
            el2.send_keys(Keys.TAB)
            time.sleep(0.25)
            js_dispatch_input_events(driver, el2)
            time.sleep(0.25)
        except Exception:
            pass

        el3 = wait.until(EC.visibility_of_element_located(loc))
        last_seen = get_input_value(el3)
        if normalize_num_str(last_seen) == target:
            return True, last_seen

        # If it keeps reverting, take a screenshot on final attempt
        if attempt == retries:
            os.makedirs("debug", exist_ok=True)
            driver.save_screenshot("debug/price_reverting.png")

        time.sleep(0.35)

    return False, last_seen


def open_watch_full_watch_equity(driver, wait):
    wait_for_preloader_to_disappear(driver)

    watch_tab = wait.until(
        EC.visibility_of_element_located((By.XPATH, "//span[normalize-space()='Watch']"))
    )
    safe_click(driver, watch_tab)
    time.sleep(1)

    menu_row = wait.until(
        EC.element_to_be_clickable((
            By.XPATH,
            "//*[contains(normalize-space(.),'Full Watch') and contains(normalize-space(.),'Equity')]"
            "/ancestor::*[self::tr or self::div][1]"
        ))
    )
    safe_click(driver, menu_row)
    print("✅ Watch → Full Watch-Equity opened")


def search_exact_symbol(driver, wait):
    wait_for_preloader_to_disappear(driver)

    box = find_dojo_combobox_input(driver, wait, "cmbSecurityHome")
    box.click()
    box.send_keys(Keys.CONTROL, "a", Keys.BACKSPACE)
    box.send_keys(FULL_SYMBOL)
    time.sleep(1)
    box.send_keys(Keys.ENTER)
    time.sleep(0.3)
    box.send_keys(Keys.ARROW_DOWN, Keys.ENTER)
    print("✅ Symbol selected")


def js_context_click(driver, el):
    driver.execute_script(
        """
        const el = arguments[0];
        const rect = el.getBoundingClientRect();
        const x = rect.left + Math.min(10, rect.width - 1);
        const y = rect.top + Math.min(10, rect.height - 1);
        const evt = new MouseEvent('contextmenu', {
          bubbles: true, cancelable: true, view: window,
          clientX: x, clientY: y, button: 2
        });
        el.dispatchEvent(evt);
        """,
        el,
    )


def right_click_and_open_buy(driver, wait):
    wait_for_preloader_to_disappear(driver)

    stock_xpath = f"//td[contains(normalize-space(.),'{SYMBOL_SHORT}')]"
    last_err = None

    for _ in range(8):
        try:
            stock = wait.until(EC.presence_of_element_located((By.XPATH, stock_xpath)))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", stock)
            time.sleep(0.25)

            try:
                ActionChains(driver).move_to_element(stock).pause(0.05).context_click(stock).perform()
            except Exception:
                js_context_click(driver, stock)

            buy = wait.until(EC.presence_of_element_located((By.ID, "rightClickmenuBuy1_text")))
            safe_click(driver, buy)
            print("✅ Buy window opened")
            return

        except (StaleElementReferenceException, TimeoutException) as e:
            last_err = e
            time.sleep(0.35)

    os.makedirs("debug", exist_ok=True)
    driver.save_screenshot("debug/right_click_failed.png")
    raise TimeoutException(f"Right-click failed. Last error: {last_err}")


def set_qty_and_price(driver, wait):
    final_qty = set_dojo_number_basic(driver, wait, (By.ID, "debtorder_0_spnQuantity"), QTY)

    ok_price, final_price = set_price_dojo(driver, wait, PRICE, retries=5)
    if not ok_price:
        raise TimeoutException(
            f"Price keeps reverting. Wanted {PRICE}, saw '{final_price}'. "
            f"Screenshot saved: debug/price_reverting.png"
        )

    print(f"✅ Quantity set: {final_qty} | ✅ Price set: {final_price}")


def click_buy_submit(driver, wait):
    wait_for_preloader_to_disappear(driver)

    buy_btn = wait.until(
        EC.element_to_be_clickable((
            By.XPATH,
            "//span[@id='debtorder_0_btnSubmit']/ancestor::span[contains(@class,'dijitButtonNode')]"
        ))
    )
    safe_click(driver, buy_btn)
    print("✅ Buy clicked (confirmation dialog should open)")


def _try_click_yes_in_context(driver, wait) -> bool:
    candidates = [
        (By.ID, "yesButton"),
        (By.CSS_SELECTOR, "#yesButton"),
        (By.CSS_SELECTOR, "#yesButton .dijitButtonNode"),
        (By.XPATH, "//*[@id='yesButton']/ancestor-or-self::*[self::span or self::button][1]"),
        (By.XPATH, "//*[normalize-space()='Yes' or normalize-space()='YES']/ancestor::span[contains(@class,'dijitButton')][1]"),
        (By.XPATH, "//*[normalize-space()='Yes' or normalize-space()='YES']/ancestor::button[1]"),
    ]
    for loc in candidates:
        try:
            wait_for_preloader_to_disappear(driver, timeout=10)
            el = WebDriverWait(driver, 10).until(EC.presence_of_element_located(loc))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            time.sleep(0.15)
            safe_click(driver, el)
            return True
        except Exception:
            pass
    return False


def click_yes_button(driver, wait):
    wait_for_preloader_to_disappear(driver, timeout=20)

    if _try_click_yes_in_context(driver, wait):
        print("🚀 YES clicked")
        return

    frames = driver.find_elements(By.TAG_NAME, "iframe")
    for i, frame in enumerate(frames):
        try:
            driver.switch_to.frame(frame)
            if _try_click_yes_in_context(driver, wait):
                print(f"🚀 YES clicked (iframe #{i})")
                driver.switch_to.default_content()
                return
        except Exception:
            pass
        finally:
            driver.switch_to.default_content()

    os.makedirs("debug", exist_ok=True)
    driver.save_screenshot("debug/yes_not_found.png")
    raise TimeoutException("YES button not found/clickable. Screenshot saved: debug/yes_not_found.png")


def main():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    wait = WebDriverWait(driver, 45)

    try:
        driver.get(LOGIN_URL)

        wait.until(EC.visibility_of_element_located((By.ID, "txtUserName"))).send_keys(USERNAME)
        wait.until(EC.visibility_of_element_located((By.ID, "txtPassword"))).send_keys(PASSWORD)
        wait.until(EC.element_to_be_clickable((By.ID, "btnSubmit"))).click()

        wait.until(EC.url_contains("showHome"))
        print("✅ Logged in")

        open_watch_full_watch_equity(driver, wait)
        search_exact_symbol(driver, wait)
        right_click_and_open_buy(driver, wait)

        set_qty_and_price(driver, wait)

        click_buy_submit(driver, wait)
        click_yes_button(driver, wait)

        print("✅ DONE")
        time.sleep(2)

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
