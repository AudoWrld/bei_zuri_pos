(function () {
  const sidebar = document.getElementById("sidebar");
  const footer = document.getElementById("footer");
  const html = document.documentElement;

  if (
    window.innerWidth > 768 &&
    localStorage.getItem("sidebarCollapsed") === "true"
  ) {
    sidebar.classList.add("collapsed");
    footer.classList.add("collapsed");
    html.classList.add("sidebar-collapsed");
  }
})();

function toggleSidebar() {
  const sidebar = document.getElementById("sidebar");
  const footer = document.getElementById("footer");
  const html = document.documentElement;

  if (window.innerWidth > 768) {
    sidebar.classList.toggle("collapsed");
    footer.classList.toggle("collapsed");
    html.classList.toggle("sidebar-collapsed");
    const isCollapsed = sidebar.classList.contains("collapsed");
    localStorage.setItem("sidebarCollapsed", isCollapsed);
    document.documentElement.style.setProperty(
      "--sidebar-width",
      isCollapsed ? "70px" : "250px"
    );
  } else {
    sidebar.classList.toggle("mobile-open");
  }
}

document.addEventListener("click", function (event) {
  if (window.innerWidth <= 768) {
    const sidebar = document.getElementById("sidebar");
    const menuToggle = document.querySelector(".menu-toggle");

    if (!sidebar.contains(event.target) && !menuToggle.contains(event.target)) {
      sidebar.classList.remove("mobile-open");
    }
  }
});

setTimeout(function () {
  const messages = document.querySelector(".messages");
  if (messages) {
    messages.style.opacity = "0";
    messages.style.transition = "opacity 0.5s ease-out";
    setTimeout(function () {
      messages.style.display = "none";
    }, 500);
  }
}, 5000);

window.addEventListener("resize", function () {
  const sidebar = document.getElementById("sidebar");
  const footer = document.getElementById("footer");
  const html = document.documentElement;

  if (window.innerWidth > 768) {
    sidebar.classList.remove("mobile-open");
    const isCollapsed = localStorage.getItem("sidebarCollapsed") === "true";
    if (isCollapsed) {
      sidebar.classList.add("collapsed");
      footer.classList.add("collapsed");
      html.classList.add("sidebar-collapsed");
      document.documentElement.style.setProperty("--sidebar-width", "70px");
    } else {
      sidebar.classList.remove("collapsed");
      footer.classList.remove("collapsed");
      html.classList.remove("sidebar-collapsed");
      document.documentElement.style.setProperty("--sidebar-width", "250px");
    }
  }
});
