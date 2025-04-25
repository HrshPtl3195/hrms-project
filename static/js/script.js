// Ensure the page always starts at the top on refresh
window.onload = function () {
  window.scrollTo({ top: 0, behavior: "smooth" });
};

// Handle "Same as Current Phone" checkbox
document
  .getElementById("sameAsCurrentPhone")
  .addEventListener("change", function () {
    const currentPhone = document.getElementById("currentPhone");
    const permanentPhone = document.getElementById("permanentPhone");

    console.log("2");
    if (this.checked) {
      //   alert("This is an alert message!");

      permanentPhone.value = currentPhone.value;
      permanentPhone.setAttribute("readonly", true);
      permanentPhone.classList.remove("bg-gray-300", "border-gray-300");
      permanentPhone.classList.add(
        "bg-gray-400",
        "border-gray-400",
        "cursor-not-allowed"
      );
    } else {
      permanentPhone.value = "";
      permanentPhone.removeAttribute("readonly");
      permanentPhone.classList.remove(
        "bg-gray-400",
        "border-gray-400",
        "cursor-not-allowed"
      );
      permanentPhone.classList.add("bg-gray-300", "border-gray-300");
    }
  });

// Handle "Same as Current Email" checkbox
document
  .getElementById("sameAsCurrentEmail")
  .addEventListener("change", function () {
    const currentEmail = document.getElementById("currentEmail");
    const permanentEmail = document.getElementById("permanentEmail");
    const emailWarningPermanent = document.getElementById(
      "emailWarningPermanent"
    );

    if (this.checked) {
      permanentEmail.value = currentEmail.value;
      permanentEmail.setAttribute("readonly", true);
      permanentEmail.classList.add("bg-gray-400", "cursor-not-allowed");
      emailWarningPermanent.classList.add("hidden"); // Hide warning if checkbox is checked
    } else {
      permanentEmail.value = "";
      permanentEmail.removeAttribute("readonly");
      permanentEmail.classList.remove("bg-gray-400", "cursor-not-allowed");
    }
  });

// Handle "Same as Current Address" checkbox
document
  .getElementById("sameAsCurrentAddress")
  .addEventListener("change", function () {
    const currentAddress = document.getElementById("currentAddress");
    const permanentAddress = document.getElementById("permanentAddress");

    if (this.checked) {
      // Copy current address to permanent address and make it read-only
      permanentAddress.value = currentAddress.value;
      permanentAddress.setAttribute("readonly", true);
      permanentAddress.classList.add("bg-gray-400", "cursor-not-allowed"); // Styling for disabled look
    } else {
      // Clear the permanent address and make it editable again
      permanentAddress.value = "";
      permanentAddress.removeAttribute("readonly");
      permanentAddress.classList.remove("bg-gray-400", "cursor-not-allowed");
    }
  });

function validatePhoneInput(inputElement, warningElement) {
  inputElement.addEventListener("input", function (event) {
    let inputValue = event.target.value;

    // Remove non-numeric characters
    inputValue = inputValue.replace(/\D/g, "");

    // Limit input to exactly 10 digits
    if (inputValue.length > 10) {
      inputValue = inputValue.slice(0, 10);
    }

    // Set cleaned value back to input field
    inputElement.value = inputValue;

    // Show warning if number is less than 10 digits
    if (inputValue.length < 10) {
      warningElement.textContent = "Phone number must be exactly 10 digits!";
      warningElement.classList.remove("hidden");
    } else {
      warningElement.classList.add("hidden");
    }
  });
}

// Apply validation for all phone input fields
validatePhoneInput(
  document.getElementById("currentPhone"),
  document.getElementById("phoneWarningCurrent")
);
validatePhoneInput(
  document.getElementById("permanentPhone"),
  document.getElementById("phoneWarningPermanent")
);
document.querySelectorAll("[id^=referencePhone]").forEach((element) => {
  validatePhoneInput(element, document.getElementById("phoneWarningReference"));
});

function validateEmailInput(inputElement, warningElement) {
  inputElement.addEventListener("input", function () {
    const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    if (!emailPattern.test(inputElement.value) && inputElement.value !== "") {
      warningElement.classList.remove("hidden"); // Show warning
    } else {
      warningElement.classList.add("hidden"); // Hide warning if valid
    }
  });
}

// Apply validation for both email fields
validateEmailInput(
  document.getElementById("currentEmail"),
  document.getElementById("emailWarningCurrent")
);
validateEmailInput(
  document.getElementById("permanentEmail"),
  document.getElementById("emailWarningPermanent")
);
validateEmailInput(
  document.getElementById("referenceEmail"),
  document.getElementById("emailWarningReference")
);

document.addEventListener("DOMContentLoaded", function () {
  const passwordField = document.getElementById("passwordField");
  const confirmPasswordField = document.getElementById("confirmPasswordField");
  const togglePassword = document.getElementById("togglePassword");
  const toggleConfirmPassword = document.getElementById(
    "toggleConfirmPassword"
  );

  // Create Password Criteria Container
  const passwordCriteria = document.createElement("div");
  passwordCriteria.classList.add(
    "text-sm",
    "text-red-400",
    "mt-2",
    "p-2",
    "bg-white",
    "rounded-lg",
    "hidden"
  );
  passwordField.closest(".space-y-2").appendChild(passwordCriteria);

  // Create Paste Restriction Warning for Password Fields
  const passwordPasteWarning = document.createElement("p");
  passwordPasteWarning.id = "passwordPasteWarning";
  passwordPasteWarning.classList.add("text-red-500", "text-sm", "hidden");
  passwordField.closest(".space-y-2").appendChild(passwordPasteWarning);

  const confirmPasswordPasteWarning = document.createElement("p");
  confirmPasswordPasteWarning.id = "confirmPasswordPasteWarning";
  confirmPasswordPasteWarning.classList.add(
    "text-red-500",
    "text-sm",
    "hidden"
  );
  confirmPasswordField
    .closest(".space-y-2")
    .appendChild(confirmPasswordPasteWarning);

  // Password Criteria List
  const criteria = {
    length: "At least 8 characters",
    uppercase: "At least one uppercase letter",
    lowercase: "At least one lowercase letter",
    number: "At least one number",
    special: "At least one special character (!@#$%^&*)",
  };

  // Function to Update Criteria Display
  function updateCriteriaDisplay() {
    const value = passwordField.value;
    const checks = {
      length: value.length >= 8,
      uppercase: /[A-Z]/.test(value),
      lowercase: /[a-z]/.test(value),
      number: /\d/.test(value),
      special: /[!@#$%^&*]/.test(value),
    };

    passwordCriteria.innerHTML = "";
    let isValid = true;

    for (let key in checks) {
      if (!checks[key]) {
        isValid = false;
        passwordCriteria.innerHTML += `<p class="mb-1">• ${criteria[key]}</p>`;
      }
    }

    passwordCriteria.classList.toggle("hidden", isValid);
    return isValid;
  }

  // Prevent Pasting into Password Fields
  function preventPaste(inputField, warningElement) {
    inputField.addEventListener("paste", function (event) {
      event.preventDefault();
      warningElement.textContent =
        "Pasting is not allowed for security reasons.";
      warningElement.classList.remove("hidden");
    });

    // Hide warning when user starts typing
    inputField.addEventListener("input", function () {
      warningElement.classList.add("hidden");
    });
  }

  preventPaste(passwordField, passwordPasteWarning);
  preventPaste(confirmPasswordField, confirmPasswordPasteWarning);

  // Toggle Password Visibility
  togglePassword.addEventListener("click", function () {
    passwordField.type =
      passwordField.type === "password" ? "text" : "password";
    this.innerHTML =
      passwordField.type === "password"
        ? `<i class="fas fa-eye text-lg"></i>`
        : `<i class="fas fa-eye-slash text-lg"></i>`;
  });

  // Toggle Confirm Password Visibility
  toggleConfirmPassword.addEventListener("click", function () {
    if (!confirmPasswordField.disabled) {
      confirmPasswordField.type =
        confirmPasswordField.type === "password" ? "text" : "password";
      this.innerHTML =
        confirmPasswordField.type === "password"
          ? `<i class="fas fa-eye text-lg"></i>`
          : `<i class="fas fa-eye-slash text-lg"></i>`;
    }
  });

  // Enable Confirm Password Field Only When Password is Valid
  passwordField.addEventListener("input", function () {
    const isValid = updateCriteriaDisplay();

    if (isValid) {
      confirmPasswordField.removeAttribute("disabled");
      confirmPasswordField.classList.remove("cursor-not-allowed");
      toggleConfirmPassword.classList.remove("cursor-not-allowed");
    } else {
      confirmPasswordField.setAttribute("disabled", "true");
      confirmPasswordField.classList.add("cursor-not-allowed");
      confirmPasswordField.value = ""; // Clear Confirm Password if Password is invalid
      confirmPasswordField.classList.remove(
        "border-green-500",
        "border-red-500"
      ); // Reset Border
      toggleConfirmPassword.classList.add("cursor-not-allowed");
    }
  });

  // Reset Confirm Password if Password is Changed
  passwordField.addEventListener("input", function () {
    if (confirmPasswordField.value !== "") {
      confirmPasswordField.value = ""; // Clear confirm password if password is changed
      confirmPasswordField.classList.remove(
        "border-green-500",
        "border-red-500"
      ); // Reset Border
    }
  });

  // Confirm Password Validation
  confirmPasswordField.addEventListener("input", function () {
    if (confirmPasswordField.value === "") {
      confirmPasswordField.classList.remove(
        "border-green-500",
        "border-red-500",
        "border-gray-600"
      ); // Reset Border on Empty
      confirmPasswordField.classList.add("border-gray-600");
    } else if (confirmPasswordField.value !== passwordField.value) {
      confirmPasswordField.classList.add("border-red-500");
      confirmPasswordField.classList.remove(
        "border-gray-600",
        "border-green-500"
      );
    } else {
      confirmPasswordField.classList.remove("border-red-500");
      confirmPasswordField.classList.add("border-green-500");
    }
  });
});

document.getElementById("scrollBtn").addEventListener("click", function () {
  if (window.scrollY + window.innerHeight >= document.body.offsetHeight) {
    window.scrollTo({ top: 0, behavior: "smooth" }); // Scroll to Top
    document
      .getElementById("scrollIcon")
      .classList.replace("fa-arrow-up", "fa-arrow-down");
  } else {
    window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }); // Scroll to Bottom
    document
      .getElementById("scrollIcon")
      .classList.replace("fa-arrow-down", "fa-arrow-up");
  }
});

document.addEventListener("DOMContentLoaded", function () {
  // Function to toggle required attribute and focus class
  function toggleRequired(checkboxId, inputIds) {
    let checkbox = document.getElementById(checkboxId);
    inputIds.forEach((inputId) => {
      let inputField = document.getElementById(inputId);

      checkbox.addEventListener("change", function () {
        if (this.checked) {
          inputField.setAttribute("required", "true");
          inputField.classList.add("focus:outline-none", "focus:border-custom");
        } else {
          inputField.removeAttribute("required");
          inputField.classList.remove(
            "focus:outline-none",
            "focus:border-custom"
          );
        }
      });

      // Ensure input is not required on page load if checkbox is unchecked
      if (!checkbox.checked) {
        inputField.removeAttribute("required");
        inputField.classList.remove(
          "focus:outline-none",
          "focus:border-custom"
        );
      }
    });
  }

  toggleRequired("prPermitCheckbox", [
    "prNumber",
    "prInforceFrom",
    "prExpiryDate",
    "prFile",
  ]);
  toggleRequired("sinCheckbox", [
    "sinNumber",
    "sinIssueDate",
    "sinExpiryDate",
    "sinFile",
  ]);
  toggleRequired("employmentHistoryCheckbox", [
    "companyName",
    "designationEH",
    "employmentFrom",
    "employmentTo",
  ]);
  toggleRequired("referencesCheckbox", [
    "referenceType",
    "referenceName",
    "referenceEmail",
    "referencePhone",
  ]);
});

document.addEventListener("DOMContentLoaded", function () {
  const referencesCheckbox = document.getElementById("referencesCheckbox");
  const referencesSection = document.getElementById("referencesSection");
  const referencesContainer = document.getElementById("referencesContainer");
  const addReferenceBtn = document.getElementById("addReferenceBtn");

  // Initially hide "Add More" button
  addReferenceBtn.style.display = "none";

  // Toggle References Section when Checkbox is Checked
  referencesCheckbox.addEventListener("change", function () {
    referencesSection.classList.toggle("hidden", !this.checked);
    checkAllFieldsFilled(); // Check if we should show "Add More"
  });

  // Function to Check if All Reference Fields are Filled
  function checkAllFieldsFilled() {
    const referenceEntries = document.querySelectorAll(".reference-entry");
    let allFilled = referenceEntries.length > 0; // Ensure at least one reference is present

    referenceEntries.forEach((entry) => {
      const name = entry
        .querySelector("input[name='referenceName[]']")
        .value.trim();
      const email = entry
        .querySelector("input[name='referenceEmail[]']")
        .value.trim();
      const phone = entry
        .querySelector("input[name='referencePhone[]']")
        .value.trim();

      if (name === "" || email === "" || phone === "") {
        allFilled = false; // If any field is empty, prevent adding new references
      }
    });

    // Show or hide the "Add More" button
    addReferenceBtn.style.display = allFilled ? "block" : "none";
  }

  // Attach event listeners to all existing fields
  function attachFieldListeners(entry) {
    entry.querySelectorAll("input").forEach((input) => {
      input.addEventListener("input", checkAllFieldsFilled);
    });
  }

  // Attach validation & listeners to existing reference fields
  document.querySelectorAll(".reference-entry").forEach((entry) => {
    attachFieldListeners(entry);
  });

  // Function to Validate Phone Input
  function validatePhoneInput(inputElement, warningElement) {
    inputElement.addEventListener("input", function () {
      let inputValue = inputElement.value.replace(/\D/g, ""); // Remove non-numeric characters
      inputElement.value = inputValue.slice(0, 10); // Limit to 10 digits

      if (inputValue.length < 10) {
        warningElement.classList.remove("hidden");
      } else {
        warningElement.classList.add("hidden");
      }

      checkAllFieldsFilled(); // Check fields after every input
    });
  }

  // Function to Validate Email Input
  function validateEmailInput(inputElement, warningElement) {
    inputElement.addEventListener("input", function () {
      const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
      if (!emailPattern.test(inputElement.value) && inputElement.value !== "") {
        warningElement.classList.remove("hidden");
      } else {
        warningElement.classList.add("hidden");
      }

      checkAllFieldsFilled(); // Check fields after every input
    });
  }

  // Function to Validate Name Input
  function validateRestrictedInput(
    inputElement,
    warningElement,
    allowedPattern,
    minLength,
    warningMessage,
    invalidCharMessage
  ) {
    inputElement.addEventListener("input", function () {
      let value = inputElement.value;
      let cleanedValue = value.replace(
        new RegExp(`[^${allowedPattern}]`, "g"),
        ""
      );

      if (value !== cleanedValue) {
        warningElement.textContent = invalidCharMessage;
        warningElement.classList.remove("hidden");
      } else if (cleanedValue.length < minLength) {
        warningElement.textContent = warningMessage;
        warningElement.classList.remove("hidden");
      } else {
        warningElement.classList.add("hidden");
      }

      inputElement.value = cleanedValue;
      checkAllFieldsFilled(); // Check fields after every input
    });
  }

  // Attach validation to existing reference fields
  document.querySelectorAll(".reference-entry").forEach((entry) => {
    validateRestrictedInput(
      entry.querySelector("input[name='referenceName[]']"),
      entry.querySelector(".nameWarning"),
      "a-zA-Z\\s",
      2,
      "Reference Name must be at least 2 characters long!",
      "Only letters and spaces are allowed!"
    );

    validateEmailInput(
      entry.querySelector("input[name='referenceEmail[]']"),
      entry.querySelector(".emailWarning")
    );

    validatePhoneInput(
      entry.querySelector("input[name='referencePhone[]']"),
      entry.querySelector(".phoneWarning")
    );
  });

  // Function to Add New Reference Row
  addReferenceBtn.addEventListener("click", function () {
    if (addReferenceBtn.style.display === "none") return; // Prevent adding if button is hidden

    const newReferenceEntry = document.createElement("div");
    newReferenceEntry.classList.add(
      "reference-entry",
      "grid",
      "grid-cols-4",
      "gap-4",
      "mt-4"
    );

    const uniqueId = `ref-${Date.now()}`; // Unique identifier for new fields

    newReferenceEntry.innerHTML = `
          <div class="space-y-2">
              <label class="block text-sm font-medium text-gray-600">Reference Type <span class="text-red-500">*</span></label>
              <select required name="referenceType[]" class="w-full bg-gray-300 border border-gray-300 rounded-lg px-4 py-2">
                  <option>Professional</option>
                  <option>Personal</option>
              </select>
          </div>
          <div class="space-y-2">
              <label class="block text-sm font-medium text-gray-600">Name <span class="text-red-500">*</span></label>
              <input type="text" id="referenceName-${uniqueId}" name="referenceName[]" class="w-full bg-gray-300 border border-gray-300 rounded-lg px-4 py-2">
              <p id="nameWarning-${uniqueId}" class="text-red-500 text-sm hidden"></p>
          </div>
          <div class="space-y-2 relative">
              <label class="block text-sm font-medium text-gray-600">Email <span class="text-red-500">*</span></label>
              <input type="email" id="referenceEmail-${uniqueId}" name="referenceEmail[]" class="w-full bg-gray-300 border border-gray-300 rounded-lg px-4 py-2">
              <p id="emailWarning-${uniqueId}" class="text-red-500 text-sm hidden">Invalid email format!</p>
          </div>
          <div class="space-y-2 relative">
              <label class="block text-sm font-medium text-gray-600">Phone <span class="text-red-500">*</span></label>
              <input type="tel" id="referencePhone-${uniqueId}" name="referencePhone[]" class="w-full bg-gray-300 border border-gray-300 rounded-lg px-4 py-2">
              <p id="phoneWarning-${uniqueId}" class="text-red-500 text-sm hidden">Only numbers are allowed!</p>
              <button type="button" class="removeReferenceBtn absolute top-0 right-0 bg-red-500 text-white px-2 py-1 rounded-lg hover:bg-red-700 text-xs mt-1">x</button>
          </div>
      `;

    referencesContainer.appendChild(newReferenceEntry);

    attachFieldListeners(newReferenceEntry);

    // Attach validation to new inputs
    const newNameInput = document.getElementById(`referenceName-${uniqueId}`);
    const newNameWarning = document.getElementById(`nameWarning-${uniqueId}`);
    validateRestrictedInput(
      newNameInput,
      newNameWarning,
      "a-zA-Z\\s",
      2,
      "Reference Name must be at least 2 characters long!",
      "Only letters and spaces are allowed!"
    );

    const newEmailInput = document.getElementById(`referenceEmail-${uniqueId}`);
    const newEmailWarning = document.getElementById(`emailWarning-${uniqueId}`);
    validateEmailInput(newEmailInput, newEmailWarning);

    const newPhoneInput = document.getElementById(`referencePhone-${uniqueId}`);
    const newPhoneWarning = document.getElementById(`phoneWarning-${uniqueId}`);
    validatePhoneInput(newPhoneInput, newPhoneWarning);

    // Add event listener to remove button
    newReferenceEntry
      .querySelector(".removeReferenceBtn")
      .addEventListener("click", function () {
        newReferenceEntry.remove();
        checkAllFieldsFilled(); // Re-check if all fields are filled after removal
      });

    checkAllFieldsFilled(); // Check fields after adding a new reference
  });

  // Check fields on page load
  checkAllFieldsFilled();
});

document.addEventListener("DOMContentLoaded", function () {
  // Ensure the page always starts at the top on refresh
  window.scrollTo({ top: 0, behavior: "smooth" });

  const form = document.querySelector("form");

  if (form) {
    form.style.opacity = "0"; // Hide the form before resetting
    form.reset(); // Reset form immediately
    setTimeout(() => {
      form.style.opacity = "1"; // Show the form after resetting
    }, 10); // Short delay ensures the reset happens before the user sees the page
  }

  // Floating Scroll Button
  const scrollBtn = document.getElementById("scrollBtn");
  if (scrollBtn) {
    scrollBtn.addEventListener("click", function () {
      if (window.scrollY + window.innerHeight >= document.body.offsetHeight) {
        window.scrollTo({ top: 0, behavior: "smooth" });
        document
          .getElementById("scrollIcon")
          .classList.replace("fa-arrow-up", "fa-arrow-down");
      } else {
        window.scrollTo({
          top: document.body.scrollHeight,
          behavior: "smooth",
        });
        document
          .getElementById("scrollIcon")
          .classList.replace("fa-arrow-down", "fa-arrow-up");
      }
    });
  }
});

window.addEventListener("pageshow", function (event) {
  if (event.persisted) {
    document.forms[0].reset(); // Reset the form completely
    localStorage.removeItem("form_data"); // Remove cached form data
  }
});

//===============================================================================================

function validateRestrictedInput(
  inputElement,
  warningElement,
  allowedPattern,
  minLength,
  warningMessage,
  invalidCharMessage
) {
  inputElement.addEventListener("input", function () {
    let value = inputElement.value;

    // Remove disallowed characters in real-time
    let cleanedValue = value.replace(
      new RegExp(`[^${allowedPattern}]`, "g"),
      ""
    );

    // Show a warning if invalid characters were removed
    if (value !== cleanedValue) {
      warningElement.textContent = invalidCharMessage;
      warningElement.classList.remove("hidden");
    } else if (cleanedValue.length < minLength) {
      warningElement.textContent = warningMessage;
      warningElement.classList.remove("hidden");
    } else {
      warningElement.classList.add("hidden");
    }

    // Update the field with cleaned value
    inputElement.value = cleanedValue;
  });
}

// Apply validation to fields requiring only letters and spaces
document.addEventListener("DOMContentLoaded", function () {
  validateRestrictedInput(
    document.getElementById("firstName"),
    document.getElementById("nameWarningFirst"),
    "a-zA-Z\\s",
    2,
    "Name must be at least 2 characters long!",
    "Only letters and spaces are allowed!"
  );

  validateRestrictedInput(
    document.getElementById("lastName"),
    document.getElementById("nameWarningLast"),
    "a-zA-Z\\s",
    2,
    "Name must be at least 2 characters long!",
    "Only letters and spaces are allowed!"
  );

  validateRestrictedInput(
    document.getElementById("middleName"),
    document.getElementById("nameWarningMiddle"),
    "a-zA-Z\\s",
    2,
    "Name must be at least 2 characters long!",
    "Only letters and spaces are allowed!"
  );

  validateRestrictedInput(
    document.getElementById("designation"),
    document.getElementById("nameWarningDesignation"),
    "a-zA-Z\\s",
    2,
    "Designation must be at least 2 characters long!",
    "Only letters and spaces are allowed!"
  );

  validateRestrictedInput(
    document.getElementById("designationEH"),
    document.getElementById("nameWarningDesignationEH"),
    "a-zA-Z\\s",
    2,
    "Designation must be at least 2 characters long!",
    "Only letters and spaces are allowed!"
  );

  validateRestrictedInput(
    document.getElementById("referenceName"),
    document.getElementById("nameWarningReference"),
    "a-zA-Z\\s",
    2,
    "Reference Name must be at least 2 characters long!",
    "Only letters and spaces are allowed!"
  );

  validateRestrictedInput(
    document.getElementById("placeOfBirth"),
    document.getElementById("POBWarning"),
    "a-zA-Z\\s",
    2,
    "Place of Birth must be at least 2 characters long!",
    "Only letters and spaces are allowed!"
  );

  validateRestrictedInput(
    document.getElementById("nationality"),
    document.getElementById("nationalityWarning"),
    "a-zA-Z\\s",
    2,
    "Nationality must be at least 2 characters long!",
    "Only letters and spaces are allowed!"
  );

  validateRestrictedInput(
    document.getElementById("currentAddress"),
    document.getElementById("addressWarningCurrent"),
    "a-zA-Z0-9\\s.,-",
    10,
    "Address must be at least 10 characters long!",
    "Only letters, numbers, spaces, commas, periods, and dashes are allowed!"
  );

  validateRestrictedInput(
    document.getElementById("permanentAddress"),
    document.getElementById("addressWarningPermanent"),
    "a-zA-Z0-9\\s.,-",
    10,
    "Address must be at least 10 characters long!",
    "Only letters, numbers, spaces, commas, periods, and dashes are allowed!"
  );
});

document.addEventListener("DOMContentLoaded", function () {
  const today = new Date();
  today.setHours(0, 0, 0, 0); // Remove time portion for accurate comparison

  const minAgeLimit = 17;
  const minDOB = new Date();
  minDOB.setFullYear(minDOB.getFullYear() - minAgeLimit); // Employee must be at least 17 years old

  // Calculate 6 months from today
  const sixMonthsLater = new Date();
  sixMonthsLater.setMonth(sixMonthsLater.getMonth() + 6);

  // List of date fields with specific rules
  const dateFields = [
    {
      id: "dateOfBirth",
      maxDate: minDOB,
      message: `Employee must be at least ${minAgeLimit} years old.`,
    },
    {
      id: "licenseIssueDate",
      maxDate: today,
      message: "License issue date cannot be in the future.",
    },
    {
      id: "passportIssueDate",
      maxDate: today,
      message: "Passport issue date cannot be in the future.",
    },
    {
      id: "sinIssueDate",
      maxDate: today,
      message: "SIN issue date cannot be in the future.",
    },
    {
      id: "prInforceFrom",
      maxDate: today,
      message: "PR/Work Permit inforce date cannot be in the future.",
    },
    {
      id: "employmentFrom",
      maxDate: today,
      message: "Employment start date cannot be in the future.",
    },
  ];

  // Attach event listener to validate dates dynamically
  dateFields.forEach(({ id, maxDate, message }) => {
    const field = document.getElementById(id);
    if (field) {
      const warning = document.createElement("p");
      warning.id = `${id}Warning`;
      warning.classList.add("text-red-500", "text-sm", "hidden");
      field.closest(".space-y-2")?.appendChild(warning);

      field.addEventListener("input", function () {
        const dateValue = new Date(field.value);
        if (dateValue > maxDate) {
          warning.textContent = message;
          warning.classList.remove("hidden");
          field.value = ""; // Auto-clear invalid date
        } else {
          warning.classList.add("hidden");
        }
      });

      // Restrict invalid manual input (prevent non-date characters)
      field.addEventListener("keydown", function (event) {
        if (
          !/[0-9\-]/.test(event.key) &&
          event.key !== "Backspace" &&
          event.key !== "Tab"
        ) {
          event.preventDefault();
        }
      });
    }
  });

  // Function to validate issue & expiry dates
  function validateExpiryDate(issueFieldId, expiryFieldId, warningMessage, requireSixMonths = false) {
    const issueField = document.getElementById(issueFieldId);
    const expiryField = document.getElementById(expiryFieldId);

    if (issueField && expiryField) {
      const warning = document.createElement("p");
      warning.id = `${expiryFieldId}Warning`;
      warning.classList.add("text-red-500", "text-sm", "hidden");
      expiryField.closest(".space-y-2")?.appendChild(warning);

      function checkValidity() {
        const issueDate = new Date(issueField.value);
        const expiryDate = new Date(expiryField.value);

        if (expiryField.value) { // Only validate if expiry date is entered
          if (!issueField.value) {
            warning.textContent = "Issue date can't be empty.";
            warning.classList.remove("hidden");
            expiryField.value = ""; // Auto-clear expiry date
          } else if (expiryDate <= issueDate) {
            warning.textContent = warningMessage;
            warning.classList.remove("hidden");
            expiryField.value = ""; // Auto-clear invalid expiry date
          } else if (expiryDate <= today) {
            warning.textContent = "Expiry date must be after today.";
            warning.classList.remove("hidden");
            expiryField.value = ""; // Auto-clear invalid expiry date
          } else if (requireSixMonths && expiryDate <= sixMonthsLater) {
            warning.textContent = "Passport expiry must be at least 6 months from today.";
            warning.classList.remove("hidden");
            expiryField.value = ""; // Auto-clear invalid expiry date
          } else {
            warning.classList.add("hidden");
          }
        } else {
          warning.classList.add("hidden"); // Hide warning if expiry date is not touched
        }
      }

      expiryField.addEventListener("input", checkValidity);
      issueField.addEventListener("input", checkValidity);
    }
  }

  // Validate expiry dates
  validateExpiryDate(
    "licenseIssueDate",
    "licenseExpiryDate",
    "License expiry date must be after issue date."
  );
  validateExpiryDate(
    "passportIssueDate",
    "passportExpiryDate",
    "Passport expiry date must be after issue date.",
    true // Passport must be valid for at least 6 months
  );
  validateExpiryDate(
    "sinIssueDate",
    "sinExpiryDate",
    "SIN expiry date must be after issue date."
  );
  validateExpiryDate(
    "prInforceFrom",
    "prExpiryDate",
    "PR/Work Permit expiry date must be after inforce date."
  );

  // **Disable Employment History Until Current Job Details Are Provided**
  function toggleEmploymentHistory() {
    const dateOfJoining = document.getElementById("dateOfJoining");
    const designation = document.getElementById("designation");
    const employmentFrom = document.getElementById("employmentFrom");
    const employmentTo = document.getElementById("employmentTo");

    if (!dateOfJoining.value || !designation.value.trim()) {
      employmentFrom.setAttribute("disabled", "true");
      employmentTo.setAttribute("disabled", "true");
      employmentFrom.classList.add("bg-gray-400", "cursor-not-allowed");
      employmentTo.classList.add("bg-gray-400", "cursor-not-allowed");
      employmentFrom.value = "";
      employmentTo.value = "";
    } else {
      employmentFrom.removeAttribute("disabled");
      employmentTo.removeAttribute("disabled");
      employmentFrom.classList.remove("bg-gray-400", "cursor-not-allowed");
      employmentTo.classList.remove("bg-gray-400", "cursor-not-allowed");
    }
  }

  document.getElementById("dateOfJoining").addEventListener("input", toggleEmploymentHistory);
  document.getElementById("designation").addEventListener("input", toggleEmploymentHistory);

  // **Validate Employment History (dateOfJoining is final)**
  function validateEmploymentDates(prevStartId, prevEndId, newJoinId, warningMessage) {
    const prevStartField = document.getElementById(prevStartId);
    const prevEndField = document.getElementById(prevEndId);
    const newJoinField = document.getElementById(newJoinId);

    if (prevStartField && prevEndField && newJoinField) {
      const prevEndWarning = document.createElement("p");
      prevEndWarning.id = `${prevEndId}Warning`;
      prevEndWarning.classList.add("text-red-500", "text-sm", "hidden");
      prevEndField.closest(".space-y-2")?.appendChild(prevEndWarning);

      function checkValidity() {
        const prevStartDate = new Date(prevStartField.value);
        const prevEndDate = new Date(prevEndField.value);
        const newJoinDate = new Date(newJoinField.value);

        if (!prevStartField.value && prevEndField.value) {
          prevEndWarning.textContent = "Employment start date is required.";
          prevEndWarning.classList.remove("hidden");
          prevEndField.value = ""; // Auto-clear employmentTo
          return;
        } else {
          prevEndWarning.classList.add("hidden");
        }

        if (prevStartField.value && prevEndField.value) {
          if (prevEndDate <= prevStartDate) {
            prevEndWarning.textContent = "Employment end date must be after start date.";
            prevEndWarning.classList.remove("hidden");
            prevEndField.value = "";
          } else if (prevEndDate >= newJoinDate) {
            prevEndWarning.textContent = warningMessage;
            prevEndWarning.classList.remove("hidden");
            prevEndField.value = "";
          } else {
            prevEndWarning.classList.add("hidden");
          }
        }
      }

      prevEndField.addEventListener("input", checkValidity);
      prevStartField.addEventListener("input", checkValidity);
      newJoinField.addEventListener("input", checkValidity);
    }
  }

  validateEmploymentDates("employmentFrom", "employmentTo", "dateOfJoining", "Employment end date must be before joining date.");
});
;

document.addEventListener("DOMContentLoaded", function () {
  /** ✅ 1. Ensure User Uploads a Valid Profile Image **/
  function validateImageUpload(inputId) {
    const fileInput = document.getElementById(inputId);
    if (fileInput) {
      const warning = document.createElement("p");
      warning.id = `${inputId}Warning`;
      warning.classList.add("text-red-500", "text-sm", "hidden");
      fileInput.closest(".space-y-2")?.appendChild(warning);

      fileInput.addEventListener("change", function () {
        const file = fileInput.files[0];
        if (file) {
          const allowedExtensions = ["image/jpeg", "image/png", "image/jpg"];
          const maxSize = 5 * 1024 * 1024; // 5MB

          if (!allowedExtensions.includes(file.type)) {
            warning.textContent =
              "Invalid file type! Only JPG, JPEG, and PNG are allowed.";
            warning.classList.remove("hidden");
            fileInput.value = ""; // Clear file input
          } else if (file.size > maxSize) {
            warning.textContent = "File size exceeds 5MB limit.";
            warning.classList.remove("hidden");
            fileInput.value = ""; // Clear file input
          } else {
            warning.classList.add("hidden");
          }
        }
      });
    }
  }

  // Apply image validation
  validateImageUpload("profileImage");

  /** ✅ 2. Prevent Temporary or Disposable Emails **/
  function validateDisposableEmail(inputId) {
    const inputField = document.getElementById(inputId);
    if (inputField) {
      const warning = document.createElement("p");
      warning.id = `${inputId}Warning`;
      warning.classList.add("text-red-500", "text-sm", "hidden");
      inputField.closest(".space-y-2")?.appendChild(warning);

      const disposableDomains = [
        "mailinator.com",
        "tempmail.com",
        "10minutemail.com",
        "throwawaymail.com",
        "guerrillamail.com",
        "yopmail.com",
      ];

      inputField.addEventListener("input", function () {
        const email = inputField.value.trim().toLowerCase();
        const domain = email.split("@")[1];

        if (domain && disposableDomains.includes(domain)) {
          warning.textContent = "Disposable email addresses are not allowed.";
          warning.classList.remove("hidden");
        } else {
          warning.classList.add("hidden");
        }
      });
    }
  }

  // Apply disposable email validation
  validateDisposableEmail("currentEmail");
  validateDisposableEmail("permanentEmail");
  validateDisposableEmail("referenceEmail");

  /** ✅ 3. Ensure References Are Different **/
  function validateUniqueReferences() {
    const referencesContainer = document.getElementById("referencesContainer");

    function checkDuplicates() {
      const referenceEntries =
        referencesContainer.querySelectorAll(".reference-entry");
      const emails = new Set();
      const phones = new Set();
      let hasDuplicate = false;

      referenceEntries.forEach((entry) => {
        const emailField = entry.querySelector("[name='referenceEmail[]']");
        const phoneField = entry.querySelector("[name='referencePhone[]']");

        let emailWarning = entry.querySelector(".emailWarning");
        let phoneWarning = entry.querySelector(".phoneWarning");

        // Create warning elements if they don't exist
        if (!emailWarning) {
          emailWarning = document.createElement("p");
          emailWarning.classList.add(
            "text-red-500",
            "text-sm",
            "hidden",
            "emailWarning"
          );
          emailField.closest(".space-y-2").appendChild(emailWarning);
        }
        if (!phoneWarning) {
          phoneWarning = document.createElement("p");
          phoneWarning.classList.add(
            "text-red-500",
            "text-sm",
            "hidden",
            "phoneWarning"
          );
          phoneField.closest(".space-y-2").appendChild(phoneWarning);
        }

        // Validate duplicate emails
        if (emailField && emailWarning) {
          const emailValue = emailField.value.trim().toLowerCase();
          if (emailValue && emails.has(emailValue)) {
            emailWarning.textContent = "Reference emails must be unique.";
            emailWarning.classList.remove("hidden");
            emailField.value = ""; // Auto-clear duplicate entry
            hasDuplicate = true;
          } else {
            emails.add(emailValue);
            emailWarning.classList.add("hidden");
          }
        }

        // Validate duplicate phone numbers
        if (phoneField && phoneWarning) {
          const phoneValue = phoneField.value.trim();
          if (phoneValue && phones.has(phoneValue)) {
            phoneWarning.textContent =
              "Reference phone numbers must be unique.";
            phoneWarning.classList.remove("hidden");
            phoneField.value = ""; // Auto-clear duplicate entry
            hasDuplicate = true;
          } else {
            phones.add(phoneValue);
            phoneWarning.classList.add("hidden");
          }
        }
      });

      return !hasDuplicate;
    }

    referencesContainer.addEventListener("input", checkDuplicates);
  }

  // Apply reference uniqueness validation
  validateUniqueReferences();

  /** ✅ 4. Loading Spinner on Form Submission **/
  const form = document.querySelector("form");
  const submitBtn = document.getElementById("submitBtn");

  if (form && submitBtn) {
    form.addEventListener("submit", function (event) {
      event.preventDefault(); // Prevent default immediate submission

      // Disable the button and add spinner
      submitBtn.disabled = true;
      submitBtn.classList.add("cursor-not-allowed", "opacity-50");
      submitBtn.innerHTML = `
        <div class="flex items-center justify-center">
          <svg class="animate-spin h-5 w-5 mr-2 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
          </svg>
          Processing...
        </div>
      `;

      // Simulate delay and then submit form
      setTimeout(() => form.submit(), 2000);
    });
  }
});
