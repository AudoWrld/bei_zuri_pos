let selectedPaymentMethod = "Cash";
let isModalActive = false;

document.addEventListener("DOMContentLoaded", function () {
  const scannerInput = document.getElementById("scannerInput");
  if (isHeld) {
    scannerInput.disabled = true;
    scannerInput.placeholder = "Sale is on hold";
    document.getElementById("holdBtn").classList.add("held");
  } else {
    scannerInput.focus();
  }

  document.querySelectorAll(".payment-btn").forEach((btn) => {
    btn.addEventListener("click", function () {
      document
        .querySelectorAll(".payment-btn")
        .forEach((b) => b.classList.remove("active"));
      this.classList.add("active");
      selectedPaymentMethod = this.getAttribute("data-payment");
    });
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !isModalActive) {
      closeModal();
      closePrinterModal();
      return;
    }

    const activeElement = document.activeElement;
    const isQtyInput =
      activeElement && activeElement.classList.contains("qty-input");

    if (isQtyInput && e.key === "Enter") {
      e.preventDefault();
      updateQuantity(activeElement);
      scannerInput.focus();
      return;
    }

    if (
      e.target.tagName !== "INPUT" &&
      e.target.tagName !== "TEXTAREA" &&
      e.target.tagName !== "SELECT"
    ) {
      if (e.key.length === 1 || e.key === "Backspace") {
        scannerInput.focus();
      }
    }
  });

  document.addEventListener("input", function (e) {
    if (e.target.classList.contains("qty-input")) {
      updateQuantity(e.target);
    }
  });

  scannerInput.addEventListener("keypress", function (e) {
    if (e.key === "Enter") {
      e.preventDefault();
      handleManualScan();
    }
  });

  checkPrinterStatus();

  const completionCloseBtn = document.querySelector(".completion-close");
  if (completionCloseBtn) {
    completionCloseBtn.addEventListener("click", closeModal);
  }

  const deliveryBtn = document.getElementById("deliveryBtn");
  if (deliveryBtn) {
    deliveryBtn.addEventListener("click", openDeliveryModal);
  }

  const deliverySearch = document.getElementById("deliverySearch");
  if (deliverySearch) {
    deliverySearch.addEventListener("input", searchDeliveryGuys);
  }

  const completeSaleForm = document.getElementById("completeSaleForm");
  if (completeSaleForm) {
    completeSaleForm.addEventListener("submit", function (e) {
      e.preventDefault();

      const paymentMethod = document.getElementById(
        "payment_method_hidden"
      ).value;

      if (paymentMethod === "Cash") {
        const moneyReceived =
          parseFloat(document.getElementById("money_received").value) || 0;
        const total = parseFloat(
          document.getElementById("totalValue").textContent
        );

        if (moneyReceived < total) {
          showNotification(
            `Amount received (${moneyReceived.toFixed(
              2
            )}) is less than total (${total.toFixed(2)})`,
            "error"
          );
          return false;
        }
      }

      if (paymentMethod === "Debt") {
        const firstName = document
          .getElementById("customer_first_name")
          .value.trim();
        const secondName = document
          .getElementById("customer_second_name")
          .value.trim();
        const email = document.getElementById("customer_email").value.trim();
        const phone = document.getElementById("customer_phone").value.trim();

        if (!firstName || !secondName || !phone) {
          showNotification("Please fill in all required fields", "error");
          return false;
        }

        if (email && !validateEmail(email)) {
          showNotification("Please enter a valid email address", "error");
          return false;
        }

        if (!validatePhone(phone)) {
          showNotification("Please enter a valid phone number", "error");
          return false;
        }
      }

      submitSaleCompletion();
    });
  }
});

function validateEmail(email) {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

function validatePhone(phone) {
  const phoneRegex = /^[0-9]{10,15}$/;
  return phoneRegex.test(phone.replace(/[\s\-\(\)]/g, ""));
}

function handleManualScan() {
  const input = document.getElementById("scannerInput");
  const value = input.value.trim();

  if (!value) return;

  scanBarcode(value);
  input.value = "";
  input.focus();
}

function scanBarcode(barcode) {
  if (isHeld) {
    showNotification("Sale is on hold", "error");
    return;
  }

  const formData = new FormData();
  formData.append("csrfmiddlewaretoken", csrfToken);
  formData.append("action", "scan_barcode");
  formData.append("barcode", barcode);

  fetch(window.location.href, {
    method: "POST",
    body: formData,
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        updateCartUI(data);
      } else {
        showNotification(data.error || "Product not found", "error");
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("Error scanning barcode", "error");
    });
}

function updateCartUI(data) {
  const tbody = document.getElementById("saleItemsTable");
  const emptyRow = document.getElementById("emptyCartRow");

  if (emptyRow) {
    emptyRow.remove();
  }

  let existingRow = tbody.querySelector(
    `tr[data-product-id="${data.product.id}"]`
  );

  if (existingRow) {
    const qtyInput = existingRow.querySelector(".qty-input");
    qtyInput.value = data.product.quantity;
    qtyInput.setAttribute("data-unit-price", data.product.price);
    qtyInput.setAttribute("data-original-value", data.product.quantity);
    qtyInput.setAttribute("data-product-name", data.product.name);
    existingRow.querySelectorAll(".item-price-cell")[1].textContent =
      parseFloat(data.product.total).toFixed(2);

    qtyInput.classList.add("highlight");
    setTimeout(() => qtyInput.classList.remove("highlight"), 300);

    const wrapper = document.querySelector(".sale-items-wrapper");
    const rowTop = existingRow.offsetTop;
    const rowHeight = existingRow.offsetHeight;
    const wrapperHeight = wrapper.clientHeight;
    const currentScroll = wrapper.scrollTop;

    if (
      rowTop < currentScroll ||
      rowTop + rowHeight > currentScroll + wrapperHeight
    ) {
      wrapper.scrollTop = rowTop - wrapperHeight / 2 + rowHeight / 2;
    }
  } else {
    const newRow = document.createElement("tr");
    newRow.setAttribute("data-product-id", data.product.id);
    newRow.setAttribute("data-item-id", data.item_id);
    newRow.innerHTML = `
            <td class="item-name">${data.product.name}</td>
            <td class="item-qty-cell">
                <input type="number"
                       class="qty-input"
                       value="${data.product.quantity}"
                       min="1"
                       data-item-id="${data.item_id}"
                       data-unit-price="${data.product.price}"
                       data-original-value="${data.product.quantity}"
                       data-product-name="${data.product.name}">
            </td>
            <td class="item-price-cell">${parseFloat(
              data.product.price
            ).toFixed(2)}</td>
            <td class="item-price-cell">${parseFloat(
              data.product.total
            ).toFixed(2)}</td>
            <td style="text-align: center;">
                <button type="button" class="btn-remove" onclick="removeItem(${
                  data.item_id
                })">
                    <i class='bx bx-x'></i>
                </button>
            </td>
        `;
    tbody.appendChild(newRow);

    const wrapper = document.querySelector(".sale-items-wrapper");
    wrapper.scrollTop = wrapper.scrollHeight;
  }

  document.getElementById("subtotalValue").textContent = parseFloat(
    data.totals.subtotal
  ).toFixed(2);
  document.getElementById("totalValue").textContent = parseFloat(
    data.totals.total
  ).toFixed(2);

  const completeBtn = document.getElementById("completeSaleBtn");
  if (completeBtn.disabled) {
    completeBtn.disabled = false;
  }
}

function updateQuantity(input) {
  if (!input.value.trim()) return;

  if (isHeld) {
    showNotification("Sale is on hold", "error");
    return;
  }

  const itemId = input.getAttribute("data-item-id");
  const newQty = parseInt(input.value);
  const originalValue = parseInt(input.getAttribute("data-original-value"));
  const productName = input.getAttribute("data-product-name");

  if (isNaN(newQty) || newQty < 1) {
    input.value = originalValue;
    showNotification(`${productName}: Quantity must be at least 1`, "error");
    return;
  }

  if (newQty === originalValue) {
    return;
  }

  const formData = new FormData();
  formData.append("csrfmiddlewaretoken", csrfToken);
  formData.append("action", "update_quantity");
  formData.append("item_id", itemId);
  formData.append("quantity", newQty);

  fetch(window.location.href, {
    method: "POST",
    body: formData,
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        const row = input.closest("tr");
        row.querySelectorAll(".item-price-cell")[1].textContent = parseFloat(
          data.item_total
        ).toFixed(2);
        input.setAttribute("data-original-value", newQty);

        document.getElementById("subtotalValue").textContent = parseFloat(
          data.totals.subtotal
        ).toFixed(2);
        document.getElementById("totalValue").textContent = parseFloat(
          data.totals.total
        ).toFixed(2);
      } else {
        input.value = originalValue;
        showNotification(
          data.error || `${productName}: Error updating quantity`,
          "error"
        );
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      input.value = originalValue;
      showNotification(`${productName}: Error updating quantity`, "error");
    });
}

function removeItem(itemId) {
  if (!confirm("Remove this item from sale?")) return;

  if (isHeld) {
    showNotification("Sale is on hold", "error");
    return;
  }

  const formData = new FormData();
  formData.append("csrfmiddlewaretoken", csrfToken);
  formData.append("action", "remove_item");
  formData.append("item_id", itemId);

  fetch(window.location.href, {
    method: "POST",
    body: formData,
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        const row = document.querySelector(`tr[data-item-id="${itemId}"]`);
        if (row) row.remove();

        document.getElementById("subtotalValue").textContent = parseFloat(
          data.totals.subtotal
        ).toFixed(2);
        document.getElementById("totalValue").textContent = parseFloat(
          data.totals.total
        ).toFixed(2);

        const tbody = document.getElementById("saleItemsTable");
        if (tbody.children.length === 0) {
          tbody.innerHTML = `
                    <tr id="emptyCartRow">
                        <td colspan="5">
                            <div class="empty-cart">
                                <i class='bx bx-cart'></i>
                                <p>No items</p>
                                <p style="font-size: 13px; color: #868e96;">Add products to receipt using barcode.</p>
                            </div>
                        </td>
                    </tr>
                `;
          document.getElementById("completeSaleBtn").disabled = true;
        }
      } else {
        showNotification(data.error || "Error removing item", "error");
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("Error removing item", "error");
    });
}

function cancelSale() {
  if (!confirm("Cancel this sale and start a new one?")) return;

  window.location.href = "/sales/new/";
}

function completeSale() {
  if (selectedPaymentMethod === "PayBill") {
    document.getElementById("paybillConfirmModal").classList.add("active");
    return;
  }
  document.getElementById("payment_method_hidden").value =
    selectedPaymentMethod;
  updateModalFields(selectedPaymentMethod);
  updateModalTitle(selectedPaymentMethod);
  document.getElementById("completeSaleModal").style.display = "flex";
}

function closeModal() {
  if (isModalActive) return;
  document.getElementById("completeSaleModal").style.display = "none";
}

function closePrinterModal() {
  if (isModalActive) return;
  document.getElementById("printerModal").classList.remove("active");
}

function submitSaleCompletion() {
  const formData = new FormData(document.getElementById("completeSaleForm"));
  formData.append("action", "complete_sale");

  closeModal();

  const paymentMethod = document.getElementById("payment_method_hidden").value;

  if (paymentMethod === "M-Pesa") {
    isModalActive = true;
    document.getElementById("paymentCheckModal").classList.add("active");

    const statusEl = document.getElementById("paymentCheckStatus");
    const messageEl = document.getElementById("paymentCheckMessage");
    const actionsEl = document.getElementById("paymentActions");

    statusEl.textContent = "Initiating Payment";
    statusEl.style.color = "#f39c12";
    messageEl.textContent = "Please wait while we process your request...";
    actionsEl.classList.remove("visible");
  } else {
    isModalActive = true;
    document.getElementById("printerModal").classList.add("active");

    const statusEl = document.getElementById("printerStatus");
    const messageEl = document.getElementById("printerMessage");

    statusEl.textContent = "Sending print request...";
    statusEl.style.color = "#f39c12";
    messageEl.textContent = "Please wait while we print your receipt";
  }

  fetch(window.location.href, {
    method: "POST",
    body: formData,
    headers: {
      "X-Requested-With": "XMLHttpRequest",
    },
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success && data.payment_initiated) {
        const statusEl = document.getElementById("paymentCheckStatus");
        const messageEl = document.getElementById("paymentCheckMessage");

        statusEl.textContent = "Payment Initiated";
        statusEl.style.color = "#f39c12";
        messageEl.textContent =
          "Please check your phone and complete the M-PESA payment";

        pollPaymentStatus(data.transaction_reference);
      } else if (data.success) {
        const statusEl = document.getElementById("printerStatus");
        const messageEl = document.getElementById("printerMessage");

        statusEl.textContent = "Receipt Printed Successfully!";
        statusEl.style.color = "#27ae60";
        messageEl.textContent = `Sale ${data.sale_number} completed successfully`;

        document.querySelector(".printer-icon-large").style.animation = "none";

        setTimeout(() => {
          isModalActive = false;
          window.location.href = "/sales/new/";
        }, 3000);
      } else {
        if (paymentMethod === "M-Pesa") {
          const statusEl = document.getElementById("paymentCheckStatus");
          const messageEl = document.getElementById("paymentCheckMessage");
          const actionsEl = document.getElementById("paymentActions");

          statusEl.textContent = "Error";
          statusEl.style.color = "#e74c3c";
          messageEl.textContent =
            data.error || "An error occurred while initiating payment";

          actionsEl.classList.add("visible");
          document.querySelector(".payment-icon-large").style.animation =
            "none";
        } else {
          const statusEl = document.getElementById("printerStatus");
          const messageEl = document.getElementById("printerMessage");

          statusEl.textContent = "Error";
          statusEl.style.color = "#e74c3c";
          messageEl.textContent =
            data.error || "An error occurred while completing the sale";

          document.querySelector(".printer-icon-large").style.animation =
            "none";

          setTimeout(() => {
            isModalActive = false;
            window.location.href = "/sales/new/";
          }, 3000);
        }
      }
    })
    .catch((error) => {
      console.error("Error:", error);

      if (paymentMethod === "M-Pesa") {
        document.getElementById("paymentCheckStatus").textContent = "Error";
        document.getElementById("paymentCheckStatus").style.color = "#e74c3c";
        document.getElementById("paymentCheckMessage").textContent =
          "An error occurred while initiating payment";

        document.getElementById("paymentActions").classList.add("visible");
        document.querySelector(".payment-icon-large").style.animation = "none";
      } else {
        document.getElementById("printerStatus").textContent = "Error";
        document.getElementById("printerStatus").style.color = "#e74c3c";
        document.getElementById("printerMessage").textContent =
          "An error occurred while completing the sale";

        document.querySelector(".printer-icon-large").style.animation = "none";

        setTimeout(() => {
          isModalActive = false;
          window.location.href = "/sales/new/";
        }, 3000);
      }
    });
}

window.onclick = function (event) {
  if (isModalActive) return;

  const completeModal = document.getElementById("completeSaleModal");
  const printerModal = document.getElementById("printerModal");
  const paybillModal = document.getElementById("paybillConfirmModal");

  if (event.target === completeModal) {
    closeModal();
  }

  if (event.target === printerModal) {
    return;
  }

  if (event.target === paybillModal) {
    closePaybillModal();
  }
};

function checkPrinterStatus() {
  fetch("/sales/printer-status/")
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        updatePrinterStatusUI(data.printer_ready, data.printer_message);
      }
    })
    .catch((error) => {
      console.error("Error checking printer:", error);
      updatePrinterStatusUI(false, "Unable to check printer status");
    });
}

function updatePrinterStatusUI(ready, message) {
  const indicator = document.querySelector(".printer-indicator");
  const statusText = document.querySelector(".printer-status-text span");

  if (ready) {
    indicator.classList.add("connected");
    indicator.classList.remove("disconnected");
    statusText.textContent = message || "Printer Ready";
  } else {
    indicator.classList.add("disconnected");
    indicator.classList.remove("connected");
    statusText.textContent = message || "Printer Offline";
  }
}

function showNotification(message, type = "info") {
  const container = document.querySelector(".messages-container");

  const messageDiv = document.createElement("div");
  messageDiv.className = `notification ${type}`;
  messageDiv.innerHTML = `<span>${message}</span>`;
  container.appendChild(messageDiv);
  setTimeout(() => {
    messageDiv.style.opacity = "0";
    messageDiv.style.marginRight = "-100px";
    setTimeout(() => {
      if (messageDiv.parentElement) {
        messageDiv.remove();
      }
    }, 300);
  }, 5000);
}

setInterval(checkPrinterStatus, 30000);

function updateModalFields(paymentMethod) {
  const container = document.getElementById("paymentFields");
  container.innerHTML = "";

  if (paymentMethod === "Cash") {
    container.innerHTML = `
            <div class="form-group">
                <label for="money_received">Money Received (KSh):</label>
                <input type="number" id="money_received" name="money_received" min="0" step="0.01" required>
            </div>
            <div class="form-group">
                <label>Change:</label>
                <div class="change-display" id="changeAmount">KSh 0.00</div>
            </div>
        `;
    document
      .getElementById("money_received")
      .addEventListener("input", calculateChange);
  } else if (paymentMethod === "M-Pesa" || paymentMethod === "Airtel") {
    container.innerHTML = `
            <div class="form-group">
                <label for="mobile_number">Mobile Number:</label>
                <input type="text" id="mobile_number" name="mobile_number" required>
            </div>
        `;
  } else if (paymentMethod === "Debt") {
    container.innerHTML = `
            <div class="form-group">
                <label for="customer_first_name">First Name <span style="color: red;">*</span></label>
                <input type="text" id="customer_first_name" name="customer_first_name" required>
            </div>
            <div class="form-group">
                <label for="customer_second_name">Second Name <span style="color: red;">*</span></label>
                <input type="text" id="customer_second_name" name="customer_second_name" required>
            </div>
            <div class="form-group">
                <label for="customer_email">Email</label>
                <input type="email" id="customer_email" name="customer_email">
            </div>
            <div class="form-group">
                <label for="customer_phone">Phone Number <span style="color: red;">*</span></label>
                <input type="text" id="customer_phone" name="customer_phone" required>
            </div>
        `;
  }
}

function updateModalTitle(paymentMethod) {
  const titleElement = document.getElementById("completionModalTitle");

  if (paymentMethod === "Cash") {
    titleElement.textContent = "Complete Cash Sale";
  } else if (paymentMethod === "M-Pesa" || paymentMethod === "Airtel") {
    titleElement.textContent = "Complete Sale by providing M-PESA Number";
  } else if (paymentMethod === "Debt") {
    titleElement.textContent =
      "Complete Debt Sale by inserting customer details";
  } else {
    titleElement.textContent = "Complete Sale";
  }
}

function calculateChange() {
  const received =
    parseFloat(document.getElementById("money_received").value) || 0;
  const total = parseFloat(document.getElementById("totalValue").textContent);
  const change = received - total;
  document.getElementById("changeAmount").textContent =
    "KSh " + change.toFixed(2);
}

function updateCurrentTime() {
  const now = new Date();
  const timeString = now.toLocaleTimeString();
  document.getElementById("currentTime").textContent = timeString;
}

updateCurrentTime();
setInterval(updateCurrentTime, 1000);

function holdSale() {
  const formData = new FormData();
  formData.append("csrfmiddlewaretoken", csrfToken);
  formData.append("action", "hold_sale");

  fetch(window.location.href, {
    method: "POST",
    body: formData,
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        isHeld = true;
        document.getElementById("scannerInput").disabled = true;
        document.getElementById("scannerInput").placeholder = "Sale is on hold";
        document.getElementById("holdBtn").classList.add("held");
        showNotification(data.message, "success");
      } else {
        showNotification(data.error || "Error holding sale", "error");
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("Error holding sale", "error");
    });
}

function recallSale() {
  const formData = new FormData();
  formData.append("csrfmiddlewaretoken", csrfToken);
  formData.append("action", "recall_sale");

  fetch(window.location.href, {
    method: "POST",
    body: formData,
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        isHeld = false;
        const scannerInput = document.getElementById("scannerInput");
        scannerInput.disabled = false;
        scannerInput.placeholder = "Search products by barcode or sku";
        scannerInput.focus();
        document.getElementById("holdBtn").classList.remove("held");
        showNotification(data.message, "success");
      } else {
        showNotification(data.error || "Error recalling sale", "error");
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("Error recalling sale", "error");
    });
}

function pollPaymentStatus(transactionReference) {
  const statusEl = document.getElementById("paymentCheckStatus");
  const messageEl = document.getElementById("paymentCheckMessage");
  const actionsEl = document.getElementById("paymentActions");

  let attempts = 0;
  const maxAttempts = 60;

  const poll = () => {
    attempts++;

    fetch(
      `/payments/check-payment-status/?transaction_reference=${transactionReference}`
    )
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "SUCCESS") {
          statusEl.textContent = "Payment Received!";
          statusEl.style.color = "#27ae60";
          messageEl.textContent = "Completing sale and printing receipt...";

          setTimeout(() => {
            document
              .getElementById("paymentCheckModal")
              .classList.remove("active");

            isModalActive = true;
            document.getElementById("printerModal").classList.add("active");

            document.getElementById("printerStatus").textContent =
              "Printing Receipt";
            document.getElementById("printerStatus").style.color = "#f39c12";
            document.getElementById("printerMessage").textContent =
              "Please wait while we print your receipt...";

            completeSaleAfterPayment(transactionReference);
          }, 2000);
        } else if (data.status === "FAILED") {
          statusEl.textContent = "Payment Failed";
          statusEl.style.color = "#e74c3c";
          messageEl.textContent = data.message || "Payment was not successful";

          actionsEl.classList.add("visible");
          document.querySelector(".payment-icon-large").style.animation =
            "none";
        } else if (attempts >= maxAttempts) {
          statusEl.textContent = "Payment Timeout";
          statusEl.style.color = "#e74c3c";
          messageEl.textContent =
            "Payment verification timed out. Please try again.";

          actionsEl.classList.add("visible");
          document.querySelector(".payment-icon-large").style.animation =
            "none";
        } else {
          statusEl.textContent = "Waiting for Payment";
          messageEl.textContent = `Checking payment status... (${attempts}/${maxAttempts})`;
          setTimeout(poll, 5000);
        }
      })
      .catch((error) => {
        console.error("Error checking payment status:", error);
        if (attempts >= maxAttempts) {
          statusEl.textContent = "Error";
          statusEl.style.color = "#e74c3c";
          messageEl.textContent = "Error checking payment status";

          actionsEl.classList.add("visible");
          document.querySelector(".payment-icon-large").style.animation =
            "none";
        } else {
          setTimeout(poll, 5000);
        }
      });
  };

  poll();
}

function retryPayment() {
  document.getElementById("paymentActions").classList.remove("visible");
  document.querySelector(".payment-icon-large").style.animation = "";

  submitSaleCompletion();
}

function closePaymentModal() {
  isModalActive = false;
  document.getElementById("paymentCheckModal").classList.remove("active");
  document.getElementById("completeSaleModal").style.display = "flex";
}

function completeSaleAfterPayment(transactionReference) {
  const formData = new FormData();
  formData.append("csrfmiddlewaretoken", csrfToken);
  formData.append("action", "complete_sale");
  formData.append("payment_method", "M-PESA");
  formData.append("transaction_reference", transactionReference);

  fetch(window.location.href, {
    method: "POST",
    body: formData,
    headers: {
      "X-Requested-With": "XMLHttpRequest",
    },
  })
    .then((response) => response.json())
    .then((data) => {
      const statusEl = document.getElementById("printerStatus");
      const messageEl = document.getElementById("printerMessage");

      if (data.success) {
        statusEl.textContent = "Receipt Printed Successfully!";
        statusEl.style.color = "#27ae60";
        messageEl.textContent = `Sale ${data.sale_number} completed successfully`;

        document.querySelector(".printer-icon-large").style.animation = "none";
        setTimeout(() => {
          isModalActive = false;
          window.location.href = "/sales/new/";
        }, 3000);
      } else {
        statusEl.textContent = "Sale Completed";
        statusEl.style.color = "#f39c12";
        messageEl.textContent = data.print_success
          ? "Sale completed but printing may have failed"
          : "Sale completed successfully";
        document.querySelector(".printer-icon-large").style.animation = "none";
        setTimeout(() => {
          isModalActive = false;
          window.location.href = "/sales/new/";
        }, 3000);
      }
    })
    .catch((error) => {
      console.error("Error completing sale after payment:", error);
      const statusEl = document.getElementById("printerStatus");
      const messageEl = document.getElementById("printerMessage");

      statusEl.textContent = "Error";
      statusEl.style.color = "#e74c3c";
      messageEl.textContent = "An error occurred while completing the sale";

      document.querySelector(".printer-icon-large").style.animation = "none";

      setTimeout(() => {
        isModalActive = false;
        window.location.href = "/sales/new/";
      }, 3000);
    });
  }

  function closePaybillModal() {
    document.getElementById("paybillConfirmModal").classList.remove("active");
  }

  function openDeliveryModal() {
    if (isHeld) {
      showNotification("Sale is on hold", "error");
      return;
    }

    const items = document.querySelectorAll("#saleItemsTable tr[data-item-id]");
    if (items.length === 0) {
      showNotification("Cannot assign delivery for empty sale", "error");
      return;
    }

    document.getElementById("deliveryModal").style.display = "flex";
    loadDeliveryGuys();
  }

  function closeDeliveryModal() {
    document.getElementById("deliveryModal").style.display = "none";
    document.getElementById("deliverySearch").value = "";
    document.getElementById("deliveryFormSection").style.display = "none";
    document.getElementById("assignDeliveryBtn").disabled = true;
    document.getElementById("selectedDeliveryGuyId").value = "";
    document.querySelectorAll(".delivery-guy-item").forEach((item) => {
      item.classList.remove("selected");
    });
  }

  function loadDeliveryGuys() {
    const listContainer = document.getElementById("deliveryGuysList");
    listContainer.innerHTML = '<div class="delivery-loading">Loading delivery guys...</div>';

    fetch("/sales/api/delivery-guys/")
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          renderDeliveryGuys(data.delivery_guys);
        } else {
          listContainer.innerHTML = '<div class="delivery-error">Error loading delivery guys</div>';
        }
      })
      .catch((error) => {
        console.error("Error loading delivery guys:", error);
        listContainer.innerHTML = '<div class="delivery-error">Error loading delivery guys</div>';
      });
  }

  function renderDeliveryGuys(deliveryGuys) {
    const listContainer = document.getElementById("deliveryGuysList");

    if (deliveryGuys.length === 0) {
      listContainer.innerHTML = '<div class="delivery-no-results">No delivery guys found</div>';
      return;
    }

    let html = "";
    deliveryGuys.forEach((guy) => {
      const activeDelivery = guy.active_delivery ? " (Busy)" : "";
      html += `
        <div class="delivery-guy-item ${guy.active_delivery ? "busy" : ""}" data-id="${guy.id}" onclick="selectDeliveryGuy(${guy.id}, '${guy.name}', ${guy.active_delivery || false})">
          <div class="delivery-guy-info">
            <div class="delivery-guy-name">${guy.name}</div>
            <div class="delivery-guy-phone">${guy.phone || "No phone"}</div>
          </div>
          <div class="delivery-guy-status">
            ${guy.active_delivery ? '<span class="status-busy">Busy</span>' : '<span class="status-available">Available</span>'}
          </div>
        </div>
      `;
    });

    listContainer.innerHTML = html;
  }

  function selectDeliveryGuy(id, name, isBusy) {
    if (isBusy) {
      showNotification("This delivery guy is currently busy with another delivery", "error");
      return;
    }

    document.querySelectorAll(".delivery-guy-item").forEach((item) => {
      item.classList.remove("selected");
    });

    const selectedItem = document.querySelector(`.delivery-guy-item[data-id="${id}"]`);
    selectedItem.classList.add("selected");

    document.getElementById("selectedDeliveryGuyId").value = id;
    document.getElementById("deliveryFormSection").style.display = "block";
    document.getElementById("assignDeliveryBtn").disabled = false;

    showNotification(`Selected: ${name}`, "info");
  }

  function searchDeliveryGuys() {
    const searchTerm = document.getElementById("deliverySearch").value.toLowerCase();

    fetch(`/sales/api/delivery-guys/?search=${encodeURIComponent(searchTerm)}`)
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          renderDeliveryGuys(data.delivery_guys);
        }
      })
      .catch((error) => {
        console.error("Error searching delivery guys:", error);
      });
  }

  function assignDelivery() {
    const deliveryGuyId = document.getElementById("selectedDeliveryGuyId").value;
    const deliveryAddress = document.getElementById("deliveryAddress").value.trim();
    const deliveryNotes = document.getElementById("deliveryNotes").value.trim();

    if (!deliveryGuyId) {
      showNotification("Please select a delivery guy", "error");
      return;
    }

    if (!deliveryAddress) {
      showNotification("Please enter delivery address", "error");
      return;
    }

    const formData = new FormData();
    formData.append("csrfmiddlewaretoken", csrfToken);
    formData.append("action", "assign_delivery");
    formData.append("delivery_guy_id", deliveryGuyId);
    formData.append("delivery_address", deliveryAddress);
    formData.append("notes", deliveryNotes);

    document.getElementById("assignDeliveryBtn").disabled = true;
    document.getElementById("assignDeliveryBtn").textContent = "Assigning...";

    fetch(window.location.href, {
      method: "POST",
      body: formData,
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          closeDeliveryModal();

          isModalActive = true;
          document.getElementById("printerModal").classList.add("active");

          const statusEl = document.getElementById("printerStatus");
          const messageEl = document.getElementById("printerMessage");

          statusEl.textContent = "Printing Receipt";
          statusEl.style.color = "#f39c12";
          messageEl.textContent = "Completing delivery assignment and printing receipt...";

          setTimeout(() => {
            statusEl.textContent = "Receipt Printed Successfully!";
            statusEl.style.color = "#27ae60";
            messageEl.textContent = `Delivery assigned and sale ${data.sale_number} completed successfully`;

            document.querySelector(".printer-icon-large").style.animation = "none";

            setTimeout(() => {
              isModalActive = false;
              window.location.href = "/sales/new/";
            }, 3000);
          }, 2000);
        } else {
          showNotification(data.error || "Error assigning delivery", "error");
          document.getElementById("assignDeliveryBtn").disabled = false;
          document.getElementById("assignDeliveryBtn").textContent = "Assign Delivery";
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        showNotification("Error assigning delivery", "error");
        document.getElementById("assignDeliveryBtn").disabled = false;
        document.getElementById("assignDeliveryBtn").textContent = "Assign Delivery";
      });
  }