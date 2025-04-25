document.addEventListener("DOMContentLoaded", function () {
    const themeToggle = document.getElementById("input");
    const body = document.body;

    // Define theme styles
    const lightTheme = {
        "--bg-primary": "#ffffff",
        "--border-color": "#e2e8f0",
        "--text-primary": "#1a202c",
        "--text-secondary": "#4a5568",
        "--input-bg": "#f1f5f9",
        "--placeholder-color": "#6b7280",
        "--hover-bg": "#e2e8f0"
    };

    const darkTheme = {
        "--bg-primary": "#1a202c",
        "--border-color": "#4a5568",
        "--text-primary": "#ffffff",
        "--text-secondary": "#cbd5e0",
        "--input-bg": "#2d3748",
        "--placeholder-color": "#a0aec0",
        "--hover-bg": "#4a5568"
    };

    function applyTheme(isDark) {
        const theme = isDark ? darkTheme : lightTheme;
        Object.keys(theme).forEach(property => {
            document.documentElement.style.setProperty(property, theme[property]);
        });

        if (isDark) {
            body.classList.add("dark-mode");
            themeToggle.checked = true;
        } else {
            body.classList.remove("dark-mode");
            themeToggle.checked = false;
        }
    }

    // Load saved theme preference
    const isDark = localStorage.getItem("darkTheme") === "true";
    applyTheme(isDark);

    // Listen for toggle changes
    themeToggle.addEventListener("change", function () {
        const isDarkMode = this.checked;
        applyTheme(isDarkMode);
        localStorage.setItem("darkTheme", isDarkMode);
    });
});
