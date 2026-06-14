/* 4LLab shared behaviour: auto footer year, active nav highlight,
   back-to-top button, scroll fade-in animations. No dependencies. */
(function () {
  "use strict";

  // Auto-update copyright year
  document.querySelectorAll(".js-year").forEach(function (el) {
    el.textContent = new Date().getFullYear();
  });

  // Highlight current page in nav (fallback if no .active set manually)
  var page = location.pathname.split("/").pop() || "index.html";
  var links = document.querySelectorAll(".site-header .nav-link");
  var hasActive = false;
  links.forEach(function (a) {
    if (a.classList.contains("active")) hasActive = true;
  });
  if (!hasActive) {
    links.forEach(function (a) {
      if (a.getAttribute("href") === page) {
        a.classList.add("active");
        a.setAttribute("aria-current", "page");
      }
    });
  } else {
    links.forEach(function (a) {
      if (a.classList.contains("active")) a.setAttribute("aria-current", "page");
    });
  }

  // Dark mode toggle (remembered across visits)
  var root = document.documentElement;
  var saved = null;
  try { saved = localStorage.getItem("theme"); } catch (e) {}
  if (saved === "dark" || (saved === null && window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches)) {
    root.setAttribute("data-theme", "dark");
  }
  function syncToggle(btn) {
    var dark = root.getAttribute("data-theme") === "dark";
    btn.innerHTML = dark ? "☀️" : "🌙";
    btn.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
    btn.setAttribute("aria-pressed", dark ? "true" : "false");
  }
  var navContainer = document.querySelector(".site-header .navbar .container-fluid");
  if (navContainer) {
    var toggle = document.createElement("button");
    toggle.id = "themeToggle";
    toggle.type = "button";
    syncToggle(toggle);
    toggle.addEventListener("click", function () {
      var dark = root.getAttribute("data-theme") === "dark";
      if (dark) { root.removeAttribute("data-theme"); }
      else { root.setAttribute("data-theme", "dark"); }
      try { localStorage.setItem("theme", dark ? "light" : "dark"); } catch (e) {}
      syncToggle(toggle);
    });
    navContainer.appendChild(toggle);
  }

  // Back-to-top button
  var btn = document.createElement("button");
  btn.id = "backToTop";
  btn.type = "button";
  btn.setAttribute("aria-label", "Back to top");
  btn.innerHTML = "↑";
  document.body.appendChild(btn);
  btn.addEventListener("click", function () {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
  window.addEventListener("scroll", function () {
    btn.classList.toggle("show", window.scrollY > 400);
  }, { passive: true });

  // Fade-in on scroll
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("visible");
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.08 });
    document.querySelectorAll(".fade-in-up").forEach(function (el) { io.observe(el); });
  } else {
    document.querySelectorAll(".fade-in-up").forEach(function (el) { el.classList.add("visible"); });
  }
})();
