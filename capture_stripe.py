from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from playwright.async_api import Error, Frame, Locator, Page, async_playwright


OUTPUT_DIR = Path("stripe_assets")
VIEWPORT = {"width": 1440, "height": 900}
COOKIE_BUTTON_PATTERNS = (
    "Accept",
    "Zustimmen",
    "Accept all",
    "Alle akzeptieren",
    "Allow all",
    "Akzeptieren",
)


def reset_output_dir(output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


async def dismiss_cookie_banners(page: Page) -> None:
    async def click_accept(root: Page | Frame | Locator) -> bool:
        for pattern in COOKIE_BUTTON_PATTERNS:
            locator = root.get_by_role("button", name=pattern, exact=False)
            try:
                if await locator.count():
                    await locator.first.wait_for(state="visible", timeout=1_000)
                    await locator.first.click()
                    await page.wait_for_timeout(400)
                    return True
            except Error:
                continue

        fallback = root.locator(
            "button:has-text('Accept'), "
            "button:has-text('Zustimmen'), "
            "button:has-text('Accept all'), "
            "button:has-text('Alle akzeptieren'), "
            "button:has-text('Allow all'), "
            "button:has-text('Akzeptieren')"
        )
        try:
            if await fallback.count():
                await fallback.first.wait_for(state="visible", timeout=1_000)
                await fallback.first.click()
                await page.wait_for_timeout(400)
                return True
        except Error:
            return False
        return False

    if await click_accept(page):
        return

    for frame in page.frames:
        try:
            if await click_accept(frame):
                return
        except Error:
            continue


async def install_capture_controls(page: Page) -> None:
    await page.evaluate(
        """
        () => {
          const existing = window.__stripeCapture;
          if (existing?.keyHandler) {
            window.removeEventListener("keydown", existing.keyHandler, true);
          }
          existing?.panel?.remove();

          const phases = ["pre_hover", "hover", "post_hover"];
          const panel = document.createElement("div");
          panel.id = "stripe-capture-controls";
          panel.style.position = "fixed";
          panel.style.top = "20px";
          panel.style.right = "20px";
          panel.style.zIndex = "2147483647";
          panel.style.width = "300px";
          panel.style.padding = "14px";
          panel.style.borderRadius = "14px";
          panel.style.background = "rgba(12, 16, 24, 0.92)";
          panel.style.color = "#f5f7fb";
          panel.style.boxShadow = "0 18px 60px rgba(0, 0, 0, 0.35)";
          panel.style.fontFamily = "ui-sans-serif, system-ui, sans-serif";
          panel.style.backdropFilter = "blur(12px)";

          const title = document.createElement("div");
          title.textContent = "Stripe DOM Capture";
          title.style.fontSize = "14px";
          title.style.fontWeight = "700";
          title.style.marginBottom = "8px";

          const status = document.createElement("div");
          status.textContent = "Ready for pre hover. Click the button to save the first DOM state.";
          status.style.fontSize = "12px";
          status.style.lineHeight = "1.45";
          status.style.opacity = "0.88";
          status.style.marginBottom = "10px";

          const button = document.createElement("button");
          button.type = "button";
          button.textContent = "Capture Pre Hover";
          button.style.width = "100%";
          button.style.border = "0";
          button.style.borderRadius = "999px";
          button.style.padding = "10px 12px";
          button.style.background = "#00d4a6";
          button.style.color = "#031323";
          button.style.fontWeight = "700";
          button.style.cursor = "pointer";

          const hint = document.createElement("div");
          hint.textContent = "You can also press Enter to advance to the next capture step.";
          hint.style.fontSize = "11px";
          hint.style.opacity = "0.72";
          hint.style.marginTop = "8px";

          const advance = () => {
            const capture = window.__stripeCapture;
            if (!capture || capture.step >= phases.length) {
              return;
            }

            capture.step += 1;
            capture.phase = phases[capture.step - 1];

            if (capture.step === 1) {
              status.textContent = "Pre hover saved. Move to the hover state, then click again.";
              button.textContent = "Capture Hover";
              return;
            }

            if (capture.step === 2) {
              status.textContent = "Hover saved. Move to the post hover state, then click again.";
              button.textContent = "Capture Post Hover";
              return;
            }

            status.textContent = "Post hover saved. Capture is complete.";
            button.textContent = "Capture Complete";
            button.disabled = true;
            button.style.background = "#7a8699";
            button.style.color = "#f5f7fb";
            button.style.cursor = "default";
          };

          button.addEventListener("click", advance);

          const keyHandler = (event) => {
            if (event.key === "Enter") {
              advance();
            }
          };

          panel.appendChild(title);
          panel.appendChild(status);
          panel.appendChild(button);
          panel.appendChild(hint);
          document.body.appendChild(panel);

          window.__stripeCapture = {
            step: 0,
            phase: null,
            keyHandler,
            panel,
          };

          window.addEventListener("keydown", keyHandler, true);
        }
        """
    )


async def wait_for_step(page: Page, step: int) -> None:
    await page.wait_for_function(
        """
        (expectedStep) => {
          const capture = window.__stripeCapture;
          return Boolean(capture && capture.step >= expectedStep);
        }
        """,
        arg=step,
        timeout=0,
    )


async def set_capture_controls_hidden(page: Page, hidden: bool) -> None:
    await page.evaluate(
        """
        (shouldHide) => {
          const panel = document.querySelector("#stripe-capture-controls");
          if (!panel) {
            return;
          }
          panel.style.visibility = shouldHide ? "hidden" : "visible";
          panel.style.pointerEvents = shouldHide ? "none" : "auto";
        }
        """,
        hidden,
    )


async def save_dom_snapshot(page: Page, destination: Path) -> None:
    html = await page.evaluate(
        """
        () => {
          const clone = document.documentElement.cloneNode(true);
          clone.querySelector("#stripe-capture-controls")?.remove();
          return "<!DOCTYPE html>\\n" + clone.outerHTML;
        }
        """
    )
    destination.write_text(html, encoding="utf-8")


async def save_element_outer_html(locator: Locator, destination: Path) -> bool:
    try:
        await locator.wait_for(state="attached", timeout=2_000)
        html = await locator.evaluate("(node) => node.outerHTML")
    except Error:
        return False

    destination.write_text(html, encoding="utf-8")
    return True


async def save_json_snapshot(page: Page, destination: Path) -> None:
    snapshot = await page.evaluate(
        """
        () => {
          const styleProps = [
            "display",
            "position",
            "top",
            "right",
            "bottom",
            "left",
            "zIndex",
            "width",
            "height",
            "margin",
            "padding",
            "color",
            "background",
            "backgroundColor",
            "opacity",
            "visibility",
            "pointerEvents",
            "transform",
            "transition",
            "boxShadow",
            "border",
            "borderRadius",
            "font",
            "fontSize",
            "fontWeight",
            "lineHeight",
          ];

          const attrsToObject = (element) => {
            if (!element) {
              return null;
            }
            return Object.fromEntries(Array.from(element.attributes).map((attr) => [attr.name, attr.value]));
          };

          const rectToObject = (rect) => ({
            x: Number(rect.x.toFixed(2)),
            y: Number(rect.y.toFixed(2)),
            width: Number(rect.width.toFixed(2)),
            height: Number(rect.height.toFixed(2)),
            top: Number(rect.top.toFixed(2)),
            right: Number(rect.right.toFixed(2)),
            bottom: Number(rect.bottom.toFixed(2)),
            left: Number(rect.left.toFixed(2)),
          });

          const inspectElement = (selector) => {
            const element = document.querySelector(selector);
            if (!element) {
              return null;
            }

            const style = window.getComputedStyle(element);
            const styles = Object.fromEntries(styleProps.map((prop) => [prop, style[prop]]));
            const rect = rectToObject(element.getBoundingClientRect());

            return {
              selector,
              tagName: element.tagName,
              id: element.id,
              className: element.className,
              text: (element.textContent || "").trim().slice(0, 500),
              attributes: attrsToObject(element),
              rect,
              styles,
              childElementCount: element.childElementCount,
              outerHTMLSnippet: element.outerHTML.slice(0, 1000),
            };
          };

          const navLinks = Array.from(
            document.querySelectorAll("header nav a, header nav button")
          ).map((element) => ({
            tagName: element.tagName,
            text: (element.textContent || "").trim(),
            href: element.getAttribute("href"),
            ariaExpanded: element.getAttribute("aria-expanded"),
            ariaLabel: element.getAttribute("aria-label"),
            className: element.className,
          }));

          const stylesheetRefs = Array.from(document.querySelectorAll("link[rel='stylesheet'], style")).map(
            (node) => ({
              tagName: node.tagName,
              href: node.tagName === "LINK" ? node.getAttribute("href") : null,
              media: node.getAttribute("media"),
              textLength: node.tagName === "STYLE" ? (node.textContent || "").length : null,
            })
          );

          const dialogs = Array.from(document.querySelectorAll("dialog, [role='dialog'], [aria-modal='true']")).map(
            (element) => ({
              tagName: element.tagName,
              className: element.className,
              id: element.id,
              text: (element.textContent || "").trim().slice(0, 400),
              rect: rectToObject(element.getBoundingClientRect()),
            })
          );

          const active = document.activeElement;

          return {
            capturedAtIso: new Date().toISOString(),
            location: {
              href: window.location.href,
              origin: window.location.origin,
              pathname: window.location.pathname,
            },
            document: {
              title: document.title,
              lang: document.documentElement.lang,
              dir: document.documentElement.dir,
              readyState: document.readyState,
              visibilityState: document.visibilityState,
            },
            viewport: {
              innerWidth: window.innerWidth,
              innerHeight: window.innerHeight,
              outerWidth: window.outerWidth,
              outerHeight: window.outerHeight,
              devicePixelRatio: window.devicePixelRatio,
            },
            scroll: {
              x: window.scrollX,
              y: window.scrollY,
            },
            body: {
              className: document.body.className,
              childElementCount: document.body.childElementCount,
            },
            activeElement: active
              ? {
                  tagName: active.tagName,
                  id: active.id,
                  className: active.className,
                  ariaLabel: active.getAttribute("aria-label"),
                  text: (active.textContent || "").trim().slice(0, 200),
                }
              : null,
            counts: {
              links: document.links.length,
              buttons: document.querySelectorAll("button").length,
              images: document.images.length,
              forms: document.forms.length,
              iframes: document.querySelectorAll("iframe").length,
              dialogs: dialogs.length,
              styleSheets: document.styleSheets.length,
            },
            targets: {
              header: inspectElement("header"),
              nav: inspectElement("header nav#navigation-menu"),
              productsTrigger: inspectElement("[data-testid='header-products-nav-item'] > button"),
              solutionsTrigger: inspectElement("[data-testid='header-solutions-nav-item'] > button"),
              menuContent: inspectElement(".navigation-menu-content"),
              menuOverflow: inspectElement(".navigation-menu-overflow"),
            },
            navLinks,
            dialogs,
            stylesheetRefs,
          };
        }
        """
    )
    destination.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")


async def capture_phase_bundle(page: Page, phase_name: str) -> None:
    phase_dir = OUTPUT_DIR / phase_name
    ensure_dir(phase_dir)

    await set_capture_controls_hidden(page, True)
    await page.wait_for_timeout(100)

    try:
        await save_dom_snapshot(page, phase_dir / "page.html")
        await save_json_snapshot(page, phase_dir / "snapshot.json")
        await page.screenshot(path=str(phase_dir / "page.png"))

        nav = page.locator("header nav#navigation-menu").first
        await save_element_outer_html(nav, phase_dir / "nav.html")
    finally:
        await set_capture_controls_hidden(page, False)


async def remove_capture_controls(page: Page) -> None:
    await page.evaluate(
        """
        () => {
          const capture = window.__stripeCapture;
          if (!capture) {
            return;
          }
          if (capture.keyHandler) {
            window.removeEventListener("keydown", capture.keyHandler, true);
          }
          capture.panel?.remove();
        }
        """
    )


async def main() -> None:
    reset_output_dir(OUTPUT_DIR)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(viewport=VIEWPORT)
        page = await context.new_page()

        await page.goto("https://stripe.com/en-de", wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle")
        await dismiss_cookie_banners(page)
        await page.bring_to_front()
        await install_capture_controls(page)

        print("Stripe is open.")
        print("Use the in-browser button three times:")
        print("1. Capture pre hover")
        print("2. Capture hover")
        print("3. Capture post hover")

        await wait_for_step(page, 1)
        await capture_phase_bundle(page, "pre_hover")
        print("Saved stripe_assets/pre_hover/")

        await wait_for_step(page, 2)
        await capture_phase_bundle(page, "hover")
        print("Saved stripe_assets/hover/")

        await wait_for_step(page, 3)
        await capture_phase_bundle(page, "post_hover")
        print("Saved stripe_assets/post_hover/")

        await remove_capture_controls(page)
        print("Capture complete.")

        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
