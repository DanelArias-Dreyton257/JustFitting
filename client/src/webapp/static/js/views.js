// Pure DOM rendering. No fetch, no app state -- everything here is a
// function of the arguments it's given.

export function showView(viewName) {
  document.querySelectorAll(".view").forEach((el) => {
    el.hidden = el.id !== `view-${viewName}`;
  });
  document.querySelectorAll(".nav-link").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === viewName);
  });
}

export function setFormError(formId, message) {
  const el = document.querySelector(`.form-error[data-for="${formId}"]`);
  if (el) el.textContent = message || "";
}

function formatAdherence(adherence) {
  if (!adherence || adherence.mean_intake_diff_kcal == null) {
    return "No real-intake logs yet";
  }
  const value = adherence.mean_intake_diff_kcal;
  return `${value >= 0 ? "+" : ""}${value.toFixed(0)} kcal/day`;
}

export function renderDashboardStats(container, metrics, adherence) {
  if (!metrics) {
    container.innerHTML = `<p class="disclaimer">Log a week to see your stats.</p>`;
    return;
  }
  const tiles = [
    ["Body fat", `${(metrics.body_fat * 100).toFixed(1)}%`],
    ["Fat mass", `${metrics.fat_mass_kg.toFixed(1)} kg`],
    ["Lean mass", `${metrics.lean_mass_kg.toFixed(1)} kg`],
    ["Weight", `${(metrics.fat_mass_kg + metrics.lean_mass_kg).toFixed(1)} kg`],
    ["To target", `${(metrics.above_target * 100).toFixed(1)} pp`],
    ["Weeks to goal", metrics.weeks_to_goal > 0 ? metrics.weeks_to_goal.toFixed(1) : "—"],
  ];
  if (adherence) {
    tiles.push(["Adherence", formatAdherence(adherence)]);
  }
  container.innerHTML = tiles
    .map(
      ([label, value]) => `
      <div class="stat-tile">
        <div class="label">${label}</div>
        <div class="value">${value}</div>
      </div>`
    )
    .join("");
}

export function renderAlerts(container, alerts) {
  if (!alerts || alerts.length === 0) {
    container.innerHTML = "";
    container.hidden = true;
    return;
  }
  container.hidden = false;
  container.innerHTML = alerts
    .map(
      (alert) => `
      <div class="alert-item alert-${alert.severity}" data-type="${alert.type}">
        <span class="alert-date">${alert.date}</span>
        <span class="alert-message">${alert.message}</span>
        <button class="alert-dismiss-btn" data-alert-id="${alert.alert_id}" title="Dismiss">&times;</button>
      </div>`
    )
    .join("");
}

export function renderSexDisclaimer(container, profile) {
  if (!profile || profile.sex !== 0) {
    container.hidden = true;
    container.innerHTML = "";
    return;
  }
  container.hidden = false;
  container.innerHTML =
    "Body-fat % estimates (RFM, U.S. Navy) are calibrated on male-only " +
    "constants; only the Deurenberg estimator adjusts for sex, so accuracy " +
    "may be reduced here. A female-specific U.S. Navy formula needs a hip " +
    "measurement this app doesn't collect yet -- see the README's " +
    '"Known limitations" for details.';
}

export function renderAlertHistory(container, alerts) {
  if (!alerts || alerts.length === 0) {
    container.innerHTML = `<p class="disclaimer">No alerts yet.</p>`;
    return;
  }
  container.innerHTML = alerts
    .map((alert) => {
      const isAcknowledged = !!alert.acknowledged_at;
      const dismissBtn = isAcknowledged
        ? ""
        : `<button class="alert-dismiss-btn" data-alert-id="${alert.alert_id}" title="Dismiss">&times;</button>`;
      return `
      <div class="alert-item alert-${alert.severity}" data-type="${alert.type}">
        <span class="alert-date">${alert.date}</span>
        <span class="alert-message">${alert.message}</span>
        <span class="badge ${isAcknowledged ? "inactive" : "active"}">${
          isAcknowledged ? `acknowledged ${alert.acknowledged_at.slice(0, 10)}` : "active"
        }</span>
        ${dismissBtn}
      </div>`;
    })
    .join("");
}

export function fillSettingsForm(form, dto) {
  form.tef_pct.value = (dto.tef * 100).toFixed(2);
  form.kcal_per_kg_fat.value = dto.kcal_per_kg_fat;
  form.neat_step_factor.value = dto.neat_step_factor;
  form.implausible_pct.value = (dto.implausible_weekly_change_pct * 100).toFixed(1);
  form.stagnation_weeks.value = dto.stagnation_weeks;
  form.stagnation_threshold_kg.value = dto.stagnation_threshold_kg;
  form.lean_loss_window_weeks.value = dto.lean_loss_window_weeks;
  form.max_lean_loss_pct.value = (dto.max_lean_mass_loss_share * 100).toFixed(0);
  form.significant_deviation_kg.value = dto.significant_deviation_kg;
}

export function renderSettingsStatus(container, dto) {
  container.textContent = dto.is_default
    ? "Using default engine constants (no overrides saved yet)."
    : `Custom settings active since ${dto.start_date}.`;
}

export function renderSettingsHistory(tbody, history) {
  tbody.innerHTML = history
    .map(
      (row) => `
      <tr>
        <td>${row.start_date}</td>
        <td>${(row.tef * 100).toFixed(2)}%</td>
        <td>${row.kcal_per_kg_fat}</td>
        <td>${row.stagnation_weeks}</td>
        <td>${(row.max_lean_mass_loss_share * 100).toFixed(0)}%</td>
        <td><span class="badge ${row.active ? "active" : "inactive"}">${
          row.active ? "active" : "past"
        }</span></td>
      </tr>`
    )
    .join("");
}

export function renderGoalHistory(tbody, goals) {
  tbody.innerHTML = goals
    .map(
      (goal) => `
      <tr>
        <td>${goal.start_date}</td>
        <td>${(goal.target_bf * 100).toFixed(1)}%</td>
        <td>${(goal.weekly_rate * 100).toFixed(2)}%</td>
        <td><span class="badge ${goal.active ? "active" : "inactive"}">${
          goal.active ? "active" : "past"
        }</span></td>
      </tr>`
    )
    .join("");
}

export function renderLogTable(tbody, logs) {
  tbody.innerHTML = logs
    .map(
      (log) => `
      <tr data-log-id="${log.log_id}">
        <td>${log.date}</td>
        <td>${log.weight_kg}</td>
        <td>${log.waist_cm}</td>
        <td>${log.neck_cm}</td>
        <td>${log.intake_kcal}</td>
        <td>${log.steps}</td>
        <td><span class="badge ${log.source}">${log.source}</span></td>
        <td><button class="delete-log-btn" data-log-id="${log.log_id}">Delete</button></td>
      </tr>`
    )
    .join("");
}

export function renderProjectionTable(tbody, rows) {
  tbody.innerHTML = rows
    .map(
      (row) => `
      <tr>
        <td>${row.date}</td>
        <td>${(row.fat_mass_kg + row.lean_mass_kg).toFixed(1)}</td>
        <td>${(row.body_fat * 100).toFixed(1)}%</td>
        <td>${row.target_calories.toFixed(0)}</td>
        <td><span class="badge projected">forecast</span></td>
      </tr>`
    )
    .join("");
}

export function fillProfileForm(form, profile) {
  form.height_cm.value = profile.height_cm;
  form.sex.value = String(profile.sex);
  form.birthdate.value = profile.birthdate;
  form.target_bf_pct.value = (profile.target_bf * 100).toFixed(1);
  form.weekly_rate_pct.value = (profile.weekly_rate * 100).toFixed(2);
}

export function showWizardStep(form, step, totalSteps) {
  form.querySelectorAll(".wizard-step").forEach((el) => {
    el.hidden = Number(el.dataset.step) !== step;
  });
  form.querySelectorAll(".wizard-step-label").forEach((el) => {
    const labelStep = Number(el.dataset.step);
    el.classList.toggle("active", labelStep === step);
    el.classList.toggle("done", labelStep < step);
  });
  form.querySelector("#log-back").hidden = step === 1;
  form.querySelector("#log-next").hidden = step === totalSteps;
  form.querySelector("#log-save").hidden = step !== totalSteps;
}

export function renderLogReview(container, values) {
  const rows = [
    ["Date", values.date],
    ["Weight", values.weight_kg && `${values.weight_kg} kg`],
    ["Waist", values.waist_cm && `${values.waist_cm} cm`],
    ["Neck", values.neck_cm && `${values.neck_cm} cm`],
    ["Intake", values.intake_kcal && `${values.intake_kcal} kcal`],
    ["Steps", values.steps],
  ];
  container.innerHTML = rows
    .map(([label, value]) => `<dt>${label}</dt><dd>${value || "—"}</dd>`)
    .join("");
}

export function renderPlanStats(container, metrics) {
  if (!metrics) {
    container.innerHTML = `<p class="disclaimer">Log a week to preview a plan.</p>`;
    return;
  }
  const tiles = [
    ["Target calories", `${metrics.target_calories.toFixed(0)} kcal`],
    ["Daily deficit", `${metrics.daily_deficit_kcal.toFixed(0)} kcal`],
    ["Weeks to goal", metrics.weeks_to_goal > 0 ? metrics.weeks_to_goal.toFixed(1) : "—"],
    ["Goal weight", `${metrics.final_weight_kg.toFixed(1)} kg`],
  ];
  container.innerHTML = tiles
    .map(
      ([label, value]) => `
      <div class="stat-tile">
        <div class="label">${label}</div>
        <div class="value">${value}</div>
      </div>`
    )
    .join("");
}

export function renderReport(container, report) {
  const { profile, latest_metrics, adherence, goal_history, series, alerts, generated_at } = report;

  const profileRows = [
    ["Height", `${profile.height_cm} cm`],
    ["Sex", profile.sex === 1 ? "Male" : "Female"],
    ["Birthdate", profile.birthdate],
    [
      "Target body fat",
      profile.target_bf != null ? `${(profile.target_bf * 100).toFixed(1)}%` : "—",
    ],
    [
      "Weekly rate",
      profile.weekly_rate != null ? `${(profile.weekly_rate * 100).toFixed(2)}%` : "—",
    ],
  ];

  const latestTiles = latest_metrics
    ? [
        ["Body fat", `${(latest_metrics.body_fat * 100).toFixed(1)}%`],
        ["Fat mass", `${latest_metrics.fat_mass_kg.toFixed(1)} kg`],
        ["Lean mass", `${latest_metrics.lean_mass_kg.toFixed(1)} kg`],
        [
          "Weeks to goal",
          latest_metrics.weeks_to_goal > 0 ? latest_metrics.weeks_to_goal.toFixed(1) : "—",
        ],
      ]
    : [];

  const seriesRows = series
    .map(
      (row) => `
      <tr>
        <td>${row.date}</td>
        <td>${(row.fat_mass_kg + row.lean_mass_kg).toFixed(1)}</td>
        <td>${(row.body_fat * 100).toFixed(1)}%</td>
        <td>${row.target_calories.toFixed(0)}</td>
        <td><span class="badge ${row.source}">${row.source}</span></td>
      </tr>`
    )
    .join("");

  const goalRows = goal_history
    .map(
      (goal) => `
      <tr>
        <td>${goal.start_date}</td>
        <td>${(goal.target_bf * 100).toFixed(1)}%</td>
        <td>${(goal.weekly_rate * 100).toFixed(2)}%</td>
        <td><span class="badge ${goal.active ? "active" : "inactive"}">${
          goal.active ? "active" : "past"
        }</span></td>
      </tr>`
    )
    .join("");

  const alertRows = alerts.length
    ? alerts
        .map(
          (alert) => `
          <div class="alert-item alert-${alert.severity}">
            <span class="alert-date">${alert.date}</span>
            <span class="alert-message">${alert.message}</span>
          </div>`
        )
        .join("")
    : `<p class="disclaimer">No open alerts.</p>`;

  container.innerHTML = `
    <p class="disclaimer">Generated ${new Date(generated_at).toLocaleString()}</p>

    <h2>Profile</h2>
    <dl class="wizard-review">
      ${profileRows.map(([label, value]) => `<dt>${label}</dt><dd>${value}</dd>`).join("")}
    </dl>

    <h2>Latest snapshot</h2>
    <div class="stat-row">
      ${
        latestTiles
          .map(
            ([label, value]) => `
          <div class="stat-tile">
            <div class="label">${label}</div>
            <div class="value">${value}</div>
          </div>`
          )
          .join("") || '<p class="disclaimer">No logs yet.</p>'
      }
    </div>

    <h2>Adherence</h2>
    <p>${formatAdherence(adherence)} (${adherence.real_log_count} real-intake logs)</p>

    <h2>Goal history</h2>
    <table class="data-table">
      <thead><tr><th>Start date</th><th>Target BF</th><th>Weekly rate</th><th>Status</th></tr></thead>
      <tbody>${goalRows}</tbody>
    </table>

    <h2>Weekly series</h2>
    <table class="data-table">
      <thead><tr><th>Date</th><th>Weight</th><th>Body fat %</th><th>Target kcal</th><th>Source</th></tr></thead>
      <tbody>${seriesRows}</tbody>
    </table>

    <h2>Open alerts</h2>
    <div class="alerts-panel">${alertRows}</div>
  `;
}
