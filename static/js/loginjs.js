document.addEventListener("DOMContentLoaded", function () {
  const loginForm = document.getElementById("loginForm");
  const emailField = document.getElementById("email");
  const rememberMe = document.getElementById("remember-me");
  const emailWarning = document.getElementById("emailWarning");
  const passwordWarning = document.getElementById("passwordWarning");

  let loginAttempts = 0;

  // Form fade-in animation
  document
    .querySelector(".form-container")
    .classList.remove("opacity-0", "translate-y-10");

  document.getElementById("email").value = "";

  // Password Visibility Toggle
  const passwordInput = document.getElementById("password");
  const togglePassword = document.querySelector(".fa-eye");

  togglePassword.addEventListener("click", function () {
    const type =
      passwordInput.getAttribute("type") === "password" ? "text" : "password";
    passwordInput.setAttribute("type", type);
    this.classList.toggle("fa-eye");
    this.classList.toggle("fa-eye-slash");
  });

  // Prevent form resubmission when using back button
  if (window.history.replaceState) {
    window.history.replaceState(null, null, window.location.href);
  }

  (function () {
    if (window.history.replaceState) {
      window.history.replaceState(null, null, window.location.href);
    }

    window.addEventListener("pageshow", function (event) {
      if (event.persisted) {
        window.location.reload(); // Forces reload when navigating back/forward
      }
    });
  })();

  // Force reload on back/forward navigation
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) {
      window.location.reload();
    }
  });

  window.onload = function () {
    if (window.location.search.includes("next=")) {
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  };

  // Ensure email field doesn't autofill
  document.getElementById("email").setAttribute("autocomplete", "on");

  // Email validation
  emailField.addEventListener("input", function () {
    const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    emailWarning.classList.toggle("hidden", emailPattern.test(this.value));
  });

  // Handle login attempts
  loginForm.addEventListener("submit", function (e) {
    if (loginAttempts >= 5) {
      alert("Too many failed attempts. Try again later.");
      e.preventDefault();
      return;
    }

    if (passwordWarning.classList.contains("hidden") === false) {
      alert("Please enter a valid password.");
      e.preventDefault();
    }

    loginAttempts++;
  });

  // Remember Me functionality
  if (localStorage.getItem("rememberedEmail")) {
    emailField.value = localStorage.getItem("rememberedEmail");
    rememberMe.checked = true;
  }

  rememberMe.addEventListener("change", function () {
    if (this.checked) {
      localStorage.setItem("rememberedEmail", emailField.value);
    } else {
      localStorage.removeItem("rememberedEmail");
    }
  });
});
