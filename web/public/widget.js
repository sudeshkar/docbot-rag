/* DocBot embeddable widget: <script src=".../widget.js" data-key="pk_..." async></script> */
(function () {
  var script = document.currentScript;
  if (!script || window.__docbotLoaded) return;
  window.__docbotLoaded = true;

  var key = script.getAttribute("data-key");
  if (!key) return console.warn("[DocBot] missing data-key on the widget script tag");
  var appOrigin = new URL(script.src).origin;
  var color = script.getAttribute("data-color") || "#2a78d6";

  var button = document.createElement("button");
  button.type = "button";
  button.setAttribute("aria-label", "Open help chat");
  button.innerHTML =
    '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
  Object.assign(button.style, {
    position: "fixed", right: "20px", bottom: "20px", width: "56px", height: "56px",
    borderRadius: "50%", border: "none", background: color, cursor: "pointer",
    boxShadow: "0 6px 20px rgba(0,0,0,.2)", zIndex: "2147483646",
    display: "flex", alignItems: "center", justifyContent: "center",
  });

  var frame = null;
  function open() {
    if (!frame) {
      frame = document.createElement("iframe");
      // The host page's origin goes to the iframe, which sends it to the API for the allowlist check.
      frame.src = appOrigin + "/embed/" + encodeURIComponent(key) + "?origin=" + encodeURIComponent(location.origin);
      frame.title = "Help chat";
      frame.setAttribute("allow", "clipboard-write");
      Object.assign(frame.style, {
        position: "fixed", right: "20px", bottom: "88px", width: "380px", height: "560px",
        maxWidth: "calc(100vw - 40px)", maxHeight: "calc(100vh - 120px)",
        border: "1px solid rgba(0,0,0,.1)", borderRadius: "16px",
        boxShadow: "0 12px 40px rgba(0,0,0,.25)", zIndex: "2147483647", background: "#fff",
      });
      document.body.appendChild(frame);
    }
    frame.style.display = "block";
    button.setAttribute("aria-expanded", "true");
  }
  function close() {
    if (frame) frame.style.display = "none";
    button.setAttribute("aria-expanded", "false");
  }

  button.addEventListener("click", function () {
    frame && frame.style.display !== "none" ? close() : open();
  });
  window.addEventListener("message", function (e) {
    // Only trust close requests from our own iframe origin.
    if (e.origin === appOrigin && e.data && e.data.type === "docbot:close") close();
  });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { document.body.appendChild(button); });
  else document.body.appendChild(button);
})();
