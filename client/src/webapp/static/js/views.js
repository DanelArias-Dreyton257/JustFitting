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

export function renderDashboardStats(
  container,
  metrics,
  adherence,
  gainQualityLatest,
  energyBalanceLatest,
  incrementAnalyticsLatest
) {
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
  if (metrics.tef_kcal != null) {
    tiles.push([
      "TEF (this week)",
      `${metrics.tef_kcal.toFixed(0)} kcal <span class="badge ${
        metrics.tef_mode === "macros" ? "active" : "inactive"
      }">${metrics.tef_mode}</span>`,
    ]);
  }
  if (gainQualityLatest && gainQualityLatest.fat_ratio_cumulative != null) {
    const pct = gainQualityLatest.fat_ratio_cumulative * 100;
    const idealPct = gainQualityLatest.fat_ratio_ideal * 100;
    const clean = pct <= idealPct;
    tiles.push([
      "Cumulative fat ratio",
      `<span class="badge ${clean ? "active" : "inactive"}">${pct.toFixed(0)}% (ideal ≤${idealPct.toFixed(0)}%)</span>`,
    ]);
  }
  if (energyBalanceLatest && energyBalanceLatest.error_rolling_mean_kcal != null) {
    const err = energyBalanceLatest.error_rolling_mean_kcal;
    const overThreshold = err > energyBalanceLatest.error_threshold_kcal;
    tiles.push([
      "Energy-balance error (rolling)",
      `<span class="badge ${overThreshold ? "inactive" : "active"}">${err.toFixed(0)} kcal/day</span>`,
    ]);
  }
  if (incrementAnalyticsLatest) {
    tiles.push([
      "Avg weekly increment",
      `${(incrementAnalyticsLatest.incr_real_mean_pct * 100).toFixed(2)}% (goal ${(
        incrementAnalyticsLatest.goal_weekly_rate * 100
      ).toFixed(2)}%)`,
    ]);
    if (incrementAnalyticsLatest.deviation_pct != null) {
      tiles.push([
        "Deviation from goal rate",
        `${(incrementAnalyticsLatest.deviation_pct * 100).toFixed(0)}%`,
      ]);
    }
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
  form.bmr_model.value = dto.bmr_model;
  form.w_rfm.value = dto.w_rfm;
  form.w_navy.value = dto.w_navy;
  form.w_deur.value = dto.w_deur;
  form.delta_pct.value = (dto.delta * 100).toFixed(1);
  form.ffmi_coef.value = dto.ffmi_coef;
  form.lean_tissue_kcal_per_kg.value = dto.lean_tissue_kcal_per_kg;
  form.fat_ratio_ideal_pct.value = (dto.fat_ratio_ideal * 100).toFixed(0);
  form.reconciliation_error_threshold_kcal.value = dto.reconciliation_error_threshold_kcal;
  form.tef_mode.value = dto.tef_mode;
  form.kappa_carbs.value = dto.kappa_carbs;
  form.kappa_fat.value = dto.kappa_fat;
  form.kappa_protein.value = dto.kappa_protein;
  form.macro_mismatch_pct.value = (dto.macro_kcal_mismatch_pct * 100).toFixed(0);
  form.protein_target_g_per_kg.value = dto.protein_target_g_per_kg;
  form.fat_target_g_per_kg.value = dto.fat_target_g_per_kg;
  form.macro_target_deviation_pct.value = (dto.macro_target_deviation_pct * 100).toFixed(0);
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
        <td>${row.bmr_model}</td>
        <td><span class="badge ${row.tef_mode === "macros" ? "active" : "inactive"}">${row.tef_mode}</span></td>
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
        <td><span class="badge ${goal.direction === "bulk" ? "active" : "inactive"}">${
          goal.direction
        }</span></td>
        <td><span class="badge ${goal.active ? "active" : "inactive"}">${
          goal.active ? "active" : "past"
        }</span></td>
      </tr>`
    )
    .join("");
}

function formatMacros(log) {
  if (log.carbs_g == null || log.fat_g == null || log.protein_g == null) return "—";
  return `${log.carbs_g}/${log.fat_g}/${log.protein_g}`;
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
        <td>${log.cardio_kcal}</td>
        <td>${formatMacros(log)}</td>
        <td><span class="badge ${log.source}">${log.source}</span></td>
        <td><span class="badge ${log.granularity}">${log.granularity}</span></td>
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
    ["Granularity", values.granularity],
    ["Weight", values.weight_kg && `${values.weight_kg} kg`],
    ["Waist", values.waist_cm && `${values.waist_cm} cm`],
    ["Neck", values.neck_cm && `${values.neck_cm} cm`],
    ["Intake", values.intake_kcal && `${values.intake_kcal} kcal`],
    ["Steps", values.steps],
    ["Cardio", values.cardio_kcal && `${values.cardio_kcal} kcal`],
    ["Carbs", values.carbs_g && `${values.carbs_g} g`],
    ["Fat", values.fat_g && `${values.fat_g} g`],
    ["Protein", values.protein_g && `${values.protein_g} g`],
  ];
  container.innerHTML = rows
    .map(([label, value]) => `<dt>${label}</dt><dd>${value || "—"}</dd>`)
    .join("");
}

export function renderPlanStats(container, metrics, direction) {
  if (!metrics) {
    container.innerHTML = `<p class="disclaimer">Log a week to preview a plan.</p>`;
    return;
  }
  // A bulk goal's Pi_i/daily_deficit_kcal goes negative by construction
  // (composition_spec.md's "Formula reconciliation") -- same computed
  // figure, sign-flipped and relabeled "surplus" for display (Phase 3, F1).
  const isBulk = direction === "bulk";
  const tiles = [
    ["Target calories", `${metrics.target_calories.toFixed(0)} kcal`],
    [
      isBulk ? "Daily surplus" : "Daily deficit",
      `${Math.abs(metrics.daily_deficit_kcal).toFixed(0)} kcal`,
    ],
    ["Weeks to goal", metrics.weeks_to_goal > 0 ? metrics.weeks_to_goal.toFixed(1) : "—"],
    ["Goal weight", `${metrics.final_weight_kg.toFixed(1)} kg`],
  ];
  if (direction) {
    tiles.push(["Direction", isBulk ? "Bulk" : "Cut"]);
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

export function renderReport(container, report) {
  const {
    profile,
    latest_metrics,
    adherence,
    goal_history,
    series,
    alerts,
    gain_quality,
    energy_balance,
    increment_analytics,
    tef,
    macro_targets,
    generated_at,
  } = report;

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
        <td>${goal.direction}</td>
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

  const fmt = (value, digits = 1) => (value == null ? "—" : value.toFixed(digits));

  const gainQualityRows = (gain_quality || [])
    .map(
      (row) => `
      <tr>
        <td>${row.date}</td>
        <td>${fmt(row.delta_lean_kg, 2)}</td>
        <td>${fmt(row.delta_fat_kg, 2)}</td>
        <td>${row.fat_ratio == null ? "—" : `${(row.fat_ratio * 100).toFixed(0)}%`}</td>
      </tr>`
    )
    .join("");

  const energyBalanceRows = (energy_balance || [])
    .map(
      (row) => `
      <tr>
        <td>${row.date}</td>
        <td>${fmt(row.surplus_ingested_kcal, 0)}</td>
        <td>${fmt(row.surplus_tissue_kcal, 0)}</td>
        <td>${fmt(row.error_kcal, 0)}</td>
      </tr>`
    )
    .join("");

  const incrementRows = (increment_analytics || [])
    .map(
      (row) => `
      <tr>
        <td>${row.date}</td>
        <td>${(row.incr_real_pct * 100).toFixed(2)}%</td>
        <td>${(row.goal_weekly_rate * 100).toFixed(2)}%</td>
        <td>${row.deviation_pct == null ? "—" : `${(row.deviation_pct * 100).toFixed(0)}%`}</td>
      </tr>`
    )
    .join("");

  const tefRows = (tef || [])
    .map(
      (row) => `
      <tr>
        <td>${row.date}</td>
        <td>${row.tef_kcal_flat.toFixed(0)}</td>
        <td>${fmt(row.tef_kcal_macros, 0)}</td>
        <td><span class="badge ${row.tef_mode_used === "macros" ? "active" : "inactive"}">${row.tef_mode_used}</span></td>
      </tr>`
    )
    .join("");

  const macroTargetRows = (macro_targets || [])
    .map(
      (row) => `
      <tr>
        <td>${row.date}</td>
        <td>${row.protein_target_g.toFixed(0)} / ${fmt(row.protein_actual_g, 0)}</td>
        <td>${row.fat_target_g.toFixed(0)} / ${fmt(row.fat_actual_g, 0)}</td>
        <td>${row.carbs_target_g.toFixed(0)} / ${fmt(row.carbs_actual_g, 0)}</td>
      </tr>`
    )
    .join("");

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
      <thead><tr><th>Start date</th><th>Target BF</th><th>Weekly rate</th><th>Direction</th><th>Status</th></tr></thead>
      <tbody>${goalRows}</tbody>
    </table>

    <h2>Weekly series</h2>
    <table class="data-table">
      <thead><tr><th>Date</th><th>Weight</th><th>Body fat %</th><th>Target kcal</th><th>Source</th></tr></thead>
      <tbody>${seriesRows}</tbody>
    </table>

    <h2>Gain quality (lean vs fat change)</h2>
    ${
      gainQualityRows
        ? `<table class="data-table">
      <thead><tr><th>Date</th><th>Lean Δ (kg)</th><th>Fat Δ (kg)</th><th>Fat ratio</th></tr></thead>
      <tbody>${gainQualityRows}</tbody>
    </table>`
        : '<p class="disclaimer">No data yet.</p>'
    }

    <h2>Energy reconciliation (ingested vs tissue surplus, kcal/day)</h2>
    ${
      energyBalanceRows
        ? `<table class="data-table">
      <thead><tr><th>Date</th><th>Ingested</th><th>Tissue</th><th>Error</th></tr></thead>
      <tbody>${energyBalanceRows}</tbody>
    </table>`
        : '<p class="disclaimer">No data yet.</p>'
    }

    <h2>Real increment vs goal rate</h2>
    ${
      incrementRows
        ? `<table class="data-table">
      <thead><tr><th>Date</th><th>Actual</th><th>Goal rate</th><th>Deviation</th></tr></thead>
      <tbody>${incrementRows}</tbody>
    </table>`
        : '<p class="disclaimer">No data yet.</p>'
    }

    <h2>TEF: flat estimate vs macros (kcal/day)</h2>
    ${
      tefRows
        ? `<table class="data-table">
      <thead><tr><th>Date</th><th>Flat</th><th>From macros</th><th>Mode used</th></tr></thead>
      <tbody>${tefRows}</tbody>
    </table>`
        : '<p class="disclaimer">No data yet.</p>'
    }

    <h2>Macro targets (target / actual, g)</h2>
    ${
      macroTargetRows
        ? `<table class="data-table">
      <thead><tr><th>Date</th><th>Protein</th><th>Fat</th><th>Carbs</th></tr></thead>
      <tbody>${macroTargetRows}</tbody>
    </table>`
        : '<p class="disclaimer">No data yet.</p>'
    }

    <h2>Open alerts</h2>
    <div class="alerts-panel">${alertRows}</div>
  `;
}
