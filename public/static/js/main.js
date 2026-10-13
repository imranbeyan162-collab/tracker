/**
 * Executive Management Frontend Logic
 * Modal management, Desktop Notification Scheduler, and Distraction Accountability
 */

document.addEventListener("DOMContentLoaded", () => {
  setupModalTriggers();
  setupDeleteConfirmations();
  initGoalNotificationEngine();
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

window.addEventListener("click", (event) => {
  if (event.target.classList.contains("modal-overlay")) {
    event.target.classList.remove("active");
  }
});

function setupModalTriggers() {
  document.querySelectorAll("[data-open-modal]").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const targetId = btn.getAttribute("data-open-modal");
      openModal(targetId);
    });
  });

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
      const msg = btn.getAttribute("data-confirm-msg") || "Confirm deletion of this entry?";
      if (!confirm(msg)) {
        e.preventDefault();
      }
    });
  });
}

function openEditTransactionModal(id, date, type, category, amount, currency, note) {
  const modal = document.getElementById("editTransactionModal");
  if (!modal) return;
  document.getElementById("edit_txn_id").value = id;
  document.getElementById("edit_txn_date").value = date;
  document.getElementById("edit_txn_type").value = type;
  document.getElementById("edit_txn_category").value = category;
  document.getElementById("edit_txn_amount").value = amount;
  document.getElementById("edit_txn_note").value = note || "";
  openModal("editTransactionModal");
}

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
 * Audio Chime Synthesizer using Web Audio API
 */
function playChime(type = "alert") {
  try {
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain);
    gain.connect(audioCtx.destination);

    if (type === "urgent") {
      osc.frequency.setValueAtTime(880, audioCtx.currentTime); // A5
      osc.frequency.setValueAtTime(440, audioCtx.currentTime + 0.15); // A4
      gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.4);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.4);
    } else {
      osc.frequency.setValueAtTime(587.33, audioCtx.currentTime); // D5
      osc.frequency.setValueAtTime(880, audioCtx.currentTime + 0.1); // A5
      gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.35);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.35);
    }
  } catch (e) {
    console.warn("Audio chime unavailable:", e);
  }
}

/**
 * Goal & Focus Notification Engine
 */
function initGoalNotificationEngine() {
  // Request Notification permission if supported
  if ("Notification" in window && Notification.permission === "default") {
    // Permission can be requested via button
    const reqBtn = document.getElementById("requestNotificationBtn");
    if (reqBtn) {
      reqBtn.addEventListener("click", () => {
        Notification.requestPermission().then(perm => {
          if (perm === "granted") {
            new Notification("Notifications Enabled", {
              body: "Goal deadline reminders and focus check-ins are active."
            });
            playChime();
          }
        });
      });
    }
  }

  // Periodic Reminder Checker
  setInterval(checkGoalReminders, 30000); // Check every 30 seconds
  checkGoalReminders();
}

const triggeredReminders = new Set();

function checkGoalReminders() {
  const goalItems = document.querySelectorAll("[data-goal-time]");
  if (!goalItems.length) return;

  const now = new Date();
  const currentHours = String(now.getHours()).padStart(2, "0");
  const currentMinutes = String(now.getMinutes()).padStart(2, "0");
  const currentTimeStr = `${currentHours}:${currentMinutes}`;
  const todayStr = now.toISOString().split("T")[0];

  goalItems.forEach(el => {
    const goalId = el.getAttribute("data-goal-id");
    const targetTime = el.getAttribute("data-goal-time");
    const targetDate = el.getAttribute("data-goal-date");
    const title = el.getAttribute("data-goal-title");
    const isCompleted = el.getAttribute("data-goal-completed") === "1";

    if (isCompleted || !targetTime) return;

    // Check if target date matches today or is open
    if (targetDate && targetDate !== todayStr) return;

    const triggerKey = `${goalId}-${todayStr}-${targetTime}`;
    if (triggeredReminders.has(triggerKey)) return;

    // Trigger within 5 minutes or exact match
    if (currentTimeStr === targetTime) {
      triggeredReminders.add(triggerKey);
      triggerGoalAlert(title, targetTime);
    }
  });
}

function triggerGoalAlert(title, time) {
  playChime("urgent");

  // System notification
  if ("Notification" in window && Notification.permission === "granted") {
    new Notification("Goal Accountability Check-In", {
      body: `Target time reached (${time}): Have you finished '${title}'? Stop distractions and complete it now!`,
      requireInteraction: true
    });
  }

  // Display Focus Screen Alert Modal
  const modal = document.getElementById("focusAlertModal");
  if (modal) {
    const msgEl = document.getElementById("focusAlertMessage");
    if (msgEl) {
      msgEl.innerText = `Scheduled checkpoint (${time}): Have you finished "${title}"? Stop scrolling and finish your commitments!`;
    }
    openModal("focusAlertModal");
  }
}
