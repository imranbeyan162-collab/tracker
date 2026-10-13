/**
 * Partner Tracker Frontend Logic
 * Modal management, Read-only permission guard, and Interactive utilities
 */

document.addEventListener("DOMContentLoaded", () => {
  // Modal handlers
  setupModalTriggers();
  setupDeleteConfirmations();
});

function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add("active");
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove("active");
  }
}

// Close modal when clicking outside modal box
window.addEventListener("click", (event) => {
  if (event.target.classList.contains("modal-overlay")) {
    event.target.classList.remove("active");
  }
});

function setupModalTriggers() {
  // Any element with data-open-modal="modal-id"
  document.querySelectorAll("[data-open-modal]").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const targetId = btn.getAttribute("data-open-modal");
      openModal(targetId);
    });
  });

  // Any element with data-close-modal="modal-id"
  document.querySelectorAll("[data-close-modal]").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const targetId = btn.getAttribute("data-close-modal");
      closeModal(targetId);
    });
  });
}

function setupDeleteConfirmations() {
  document.querySelectorAll(".delete-confirm-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const msg = btn.getAttribute("data-confirm-msg") || "Are you sure you want to delete this item? This action cannot be undone.";
      if (!confirm(msg)) {
        e.preventDefault();
      }
    });
  });
}

/**
 * Pre-populates and opens the Edit Money Transaction modal
 */
function openEditTransactionModal(id, date, type, category, amount, currency, note) {
  const modal = document.getElementById("editTransactionModal");
  if (!modal) return;
  
  document.getElementById("edit_txn_id").value = id;
  document.getElementById("edit_txn_date").value = date;
  document.getElementById("edit_txn_type").value = type;
  document.getElementById("edit_txn_category").value = category;
  document.getElementById("edit_txn_amount").value = amount;
  document.getElementById("edit_txn_currency").value = currency;
  document.getElementById("edit_txn_note").value = note || "";
  
  openModal("editTransactionModal");
}

/**
 * Pre-populates and opens the Edit Investment modal
 */
function openEditInvestmentModal(id, assetName, amountInvested, currentValue, notes) {
  const modal = document.getElementById("editInvestmentModal");
  if (!modal) return;

  document.getElementById("edit_inv_id").value = id;
  document.getElementById("edit_inv_asset").value = assetName;
  document.getElementById("edit_inv_invested").value = amountInvested;
  document.getElementById("edit_inv_current").value = currentValue;
  document.getElementById("edit_inv_notes").value = notes || "";

  openModal("editInvestmentModal");
}

/**
 * Helper to prompt unauthenticated user with partner login modal
 */
function promptPartnerLogin(partnerId) {
  const select = document.getElementById("login_partner_select");
  if (select && partnerId) {
    select.value = partnerId;
  }
  openModal("loginModal");
}
