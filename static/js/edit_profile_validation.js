document.addEventListener("DOMContentLoaded", function () {
    // 🔹 Email Validation
    function validateEmailInput(inputId, warningId) {
      const input = document.getElementById(inputId);
      const warning = document.getElementById(warningId);
      if (!input || !warning) return;
  
      input.addEventListener("input", function () {
        const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        if (!emailPattern.test(input.value) && input.value !== "") {
          warning.classList.remove("hidden");
        } else {
          warning.classList.add("hidden");
        }
      });
    }
  
    validateEmailInput("current_email", "emailWarningCurrent");
    validateEmailInput("permanent_email", "emailWarningPermanent");
    validateEmailInput("professional_ref_email", "emailWarningReference");
  
    // 🔹 Phone Validation
    function validatePhoneInput(inputId, warningId) {
      const input = document.getElementById(inputId);
      const warning = document.getElementById(warningId);
      if (!input || !warning) return;
  
      input.addEventListener("input", function () {
        let cleaned = input.value.replace(/\D/g, "");
        if (cleaned.length > 10) cleaned = cleaned.slice(0, 10);
        input.value = cleaned;
  
        if (cleaned.length < 10) {
          warning.textContent = "Phone number must be exactly 10 digits!";
          warning.classList.remove("hidden");
        } else {
          warning.classList.add("hidden");
        }
      });
    }
  
    validatePhoneInput("current_phone", "phoneWarningCurrent");
    validatePhoneInput("permanent_phone", "phoneWarningPermanent");
    validatePhoneInput("professional_ref_contact", "phoneWarningReference");
  
    // 🔹 Restricted Input (Names, Address)
    function validateRestrictedInput(id, warningId, pattern, minLen, msgShort, msgInvalid) {
      const input = document.getElementById(id);
      const warning = document.getElementById(warningId);
      if (!input || !warning) return;
  
      input.addEventListener("input", function () {
        let raw = input.value;
        let clean = raw.replace(new RegExp(`[^${pattern}]`, "g"), "");
        input.value = clean;
  
        if (raw !== clean) {
          warning.textContent = msgInvalid;
          warning.classList.remove("hidden");
        } else if (clean.length < minLen) {
          warning.textContent = msgShort;
          warning.classList.remove("hidden");
        } else {
          warning.classList.add("hidden");
        }
      });
    }
  
    validateRestrictedInput(
      "middle_name",
      "nameWarningMiddle",
      "a-zA-Z\\s",
      2,
      "Name must be at least 2 characters long!",
      "Only letters and spaces are allowed!"
    );
  
    validateRestrictedInput(
      "professional_ref_name",
      "nameWarningReference",
      "a-zA-Z\\s",
      2,
      "Reference name must be at least 2 characters long!",
      "Only letters and spaces are allowed!"
    );
  
    validateRestrictedInput(
      "current_address",
      "addressWarningCurrent",
      "a-zA-Z0-9\\s.,-",
      10,
      "Address must be at least 10 characters long!",
      "Only letters, numbers, spaces, commas, periods, and dashes are allowed!"
    );
  
    validateRestrictedInput(
      "permanent_address",
      "addressWarningPermanent",
      "a-zA-Z0-9\\s.,-",
      10,
      "Address must be at least 10 characters long!",
      "Only letters, numbers, spaces, commas, periods, and dashes are allowed!"
    );
  
    // 🔹 Expiry Date Validations
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const sixMonthsLater = new Date(today);
    sixMonthsLater.setMonth(sixMonthsLater.getMonth() + 6);
  
    function validateExpiryDate(issueId, expiryId, requireSixMonths = false, msg = "Expiry must be after issue date.") {
      const issueInput = document.getElementById(issueId);
      const expiryInput = document.getElementById(expiryId);
      if (!issueInput || !expiryInput) return;
  
      const warning = document.createElement("p");
      warning.className = "text-red-500 text-sm mt-1";
      warning.classList.add("hidden");
      expiryInput.parentNode.appendChild(warning);
  
      function check() {
        const issue = new Date(issueInput.value);
        const expiry = new Date(expiryInput.value);
      
        if (!issueInput.value || !expiryInput.value) return warning.classList.add("hidden");
      
        // Strip time from both dates
        const issueDateOnly = new Date(issue.getFullYear(), issue.getMonth(), issue.getDate());
        const expiryDateOnly = new Date(expiry.getFullYear(), expiry.getMonth(), expiry.getDate());
      
        if (expiryDateOnly <= issueDateOnly) {
          warning.textContent = msg;
          warning.classList.remove("hidden");
          expiryInput.value = "";
        } else if (expiryDateOnly <= today) {
          warning.textContent = "Expiry must be a future date.";
          warning.classList.remove("hidden");
          expiryInput.value = "";
        } else if (requireSixMonths && expiryDateOnly <= sixMonthsLater) {
          warning.textContent = "Passport must be valid for at least 6 more months.";
          warning.classList.remove("hidden");
          expiryInput.value = "";
        } else {
          warning.classList.add("hidden");
        }
      }      
  
      issueInput.addEventListener("change", check);
      expiryInput.addEventListener("change", check);
    }
  
    validateExpiryDate("passport_issue_date", "passport_expiry_date", true);
    validateExpiryDate("sin_issue_date", "sin_expiry_date");
    validateExpiryDate("work_permit_issue_date", "work_permit_expiry_date");
    validateExpiryDate("license_issue_date", "license_expiry_date");
  });
  