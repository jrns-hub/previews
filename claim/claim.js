/* Claim bar: turns a preview into something an owner can say yes to.
   Works today over text, upgrades to a checkout link the moment one exists.

   To turn on card payment: paste your Square or Wave payment link into
   CONFIG.checkout below. Nothing else changes. Until then, every button
   opens a text message with the business name already filled in. */

(function () {
  "use strict";

  var CONFIG = {
    price: 150,
    phone: "+18287400010",
    phoneDisplay: "828-740-0010",
    checkout: "", // <- paste the PayPal $150 payment link here
    message: "Yes, make my preview live. My business is ",
    headline: "", // optional: "... {name} ... {price} ..."
    sub: "",
    label: "",
    name: ""
  };

  // A page can override the offer before this script loads:
  //   <script>window.BT_CLAIM={price:150,label:"Book my 20 minutes",headline:"..."}</script>
  if (window.BT_CLAIM) {
    for (var k in window.BT_CLAIM) {
      if (Object.prototype.hasOwnProperty.call(window.BT_CLAIM, k)) CONFIG[k] = window.BT_CLAIM[k];
    }
  }

  function slug() {
    var parts = location.pathname.replace(/\/+$/, "").split("/");
    return parts[parts.length - 1] || "preview";
  }

  // The preview's <title> is "<Business> · <headline>".
  function bizName() {
    var t = (document.title || "").split("·")[0].trim();
    return t || "my business";
  }

  function smsHref(name) {
    // ?&body= is the form that works on both iOS and Android.
    return "sms:" + CONFIG.phone + "?&body=" + encodeURIComponent(CONFIG.message + name + ".");
  }

  function payHref() {
    return CONFIG.checkout || smsHref(bizName());
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    return n;
  }

  function close(bar) {
    bar.remove();
    document.body.classList.remove("bt-claim-on");
    document.documentElement.style.removeProperty("--bt-claim-h");
    try { localStorage.setItem("bt-claim-hidden:" + slug(), "1"); } catch (e) {}
  }

  function build() {
    var name = CONFIG.name || bizName();
    var bar = el("div", "");
    bar.id = "bt-claim";
    bar.setAttribute("role", "region");
    bar.setAttribute("aria-label", "This preview is yours");

    var wrap = el("div", "bt-in");

    var txt = el("div", "bt-txt");
    var line = document.createElement("span");
    if (CONFIG.headline) {
      line.textContent = CONFIG.headline
        .replace(/\{name\}/g, name)
        .replace(/\{price\}/g, "$" + CONFIG.price);
    } else {
      var b = el("b", "", "$" + CONFIG.price);
      line.appendChild(document.createTextNode("This is your site, " + name + ". It goes live for "));
      line.appendChild(b);
      line.appendChild(document.createTextNode(", in your name."));
    }
    txt.appendChild(line);
    txt.appendChild(el("span", "bt-sub", CONFIG.sub || "No contract. Your photos, your reviews, your accounts. Cancel the care plan anytime."));

    var acts = el("div", "bt-acts");
    var go = el("a", "bt-go", CONFIG.label || (CONFIG.checkout ? "Pay " + "$" + CONFIG.price : "Yes, make it live"));
    go.href = payHref();
    var say = el("a", "bt-say", "Text me");
    say.href = smsHref(name);
    acts.appendChild(go);
    acts.appendChild(say);

    var x = el("button", "bt-x", "\u00d7");
    x.type = "button";
    x.setAttribute("aria-label", "Hide this bar");
    x.addEventListener("click", function () { close(bar); });

    wrap.appendChild(txt);
    wrap.appendChild(acts);
    wrap.appendChild(x);
    bar.appendChild(wrap);
    document.body.insertBefore(bar, document.body.firstChild);
    document.body.classList.add("bt-claim-on");

    // Reserve exactly the height of the bar so it never covers the page.
    var setH = function () {
      document.documentElement.style.setProperty("--bt-claim-h", bar.offsetHeight + "px");
    };
    setH();
    window.addEventListener("resize", setH, { passive: true });
    if (window.ResizeObserver) new ResizeObserver(setH).observe(bar);
  }

  // Google photo links expire (403). Swap the first broken photo for a name card, hide the rest.
  function fixPhotos() {
    var imgs = document.querySelectorAll('img[src*="googleusercontent"]');
    var hero = imgs[0]; // the card always goes where the first photo is, in page order
    function swap(img) {
      if (img.dataset.btFixed) return;
      img.dataset.btFixed = "1";
      var unit = img.closest("picture") || img;
      if (img === hero) {
        var w = img.getAttribute("width"), h = img.getAttribute("height");
        var card = el("div", "", bizName());
        card.style.cssText = "box-sizing:border-box;display:flex;align-items:center;justify-content:center;text-align:center;padding:24px;" +
          "width:100%;height:100%;border-radius:inherit;background:linear-gradient(135deg,#efe7d6,#d9cdb4);" +
          "color:#2b2418;font:600 clamp(1.4rem,3.5vw,2.4rem)/1.15 Georgia,serif;" +
          (w && h ? "aspect-ratio:" + w + "/" + h + ";max-height:70vh;" : "min-height:280px;");
        unit.replaceWith(card);
      } else {
        var box = unit.closest("figure, li") || unit.closest("a") || unit;
        box.style.display = "none";
        // Hide a gallery grid once every item in it is hidden, so no empty padding is left.
        var grid = box.parentElement;
        if (grid && grid !== document.body) {
          var kids = grid.children, shown = 0;
          for (var j = 0; j < kids.length; j++) if (kids[j].style.display !== "none") shown++;
          if (!shown) grid.style.display = "none";
        }
      }
    }
    for (var i = 0; i < imgs.length; i++) {
      (function (img) {
        if (img.complete && img.naturalWidth === 0) swap(img);
        else img.addEventListener("error", function () { swap(img); });
      })(imgs[i]);
    }
  }

  function start() {
    fixPhotos();
    var hidden = false;
    try { hidden = localStorage.getItem("bt-claim-hidden:" + slug()) === "1"; } catch (e) {}
    if (hidden) return;
    // Never render on the main previews list or the claim page itself.
    if (/\/previews\/?$/.test(location.pathname)) return;
    if (location.pathname.indexOf("/claim/") !== -1) return;
    // The grant calendar is not a business preview.
    if (/\/grants\/(index\.html)?$/.test(location.pathname)) return;
    build();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
