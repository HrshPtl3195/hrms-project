// In HTML remove checked="darkTheme"

// In css handle the dark theme:
// body.dark-theme {...}

document.addEventListener("DOMContentLoaded", function () {
  const themeToggle = document.getElementById("input");

  // Load saved theme preference
  if (localStorage.getItem("darkTheme") === "true") {
    themeToggle.checked = true;
    document.body.classList.add("dark-theme");
  } else {
    themeToggle.checked = false;
    document.body.classList.remove("dark-theme");
  }

  // Listen for toggle changes
  themeToggle.addEventListener("change", function () {
    if (this.checked) {
      document.body.classList.add("dark-theme");
      localStorage.setItem("darkTheme", "true");
    } else {
      document.body.classList.remove("dark-theme");
      localStorage.setItem("darkTheme", "false");
    }
  });
});


document.addEventListener("DOMContentLoaded", function () {
  const themeToggle = document.getElementById("input");

  function applyTheme(isDark) {
      if (isDark) {
          document.body.classList.add("dark-theme");
          document.body.style.backgroundColor = "#222";  // Ensure background updates
          document.body.style.color = "#fff"; // Ensure text updates
      } else {
          document.body.classList.remove("dark-theme");
          document.body.style.backgroundColor = "#fff";  // Ensure background updates
          document.body.style.color = "#000"; // Ensure text updates
      }
  }

  // Load saved theme preference
  const isDark = localStorage.getItem("darkTheme") === "true";
  themeToggle.checked = isDark;
  applyTheme(isDark);

  // Listen for toggle changes
  themeToggle.addEventListener("change", function () {
      const isDarkMode = this.checked;
      applyTheme(isDarkMode);
      localStorage.setItem("darkTheme", isDarkMode);
  });
});
