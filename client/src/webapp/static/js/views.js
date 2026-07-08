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

function formatAdherence(adherence, withPerDay = true) {
  if (!adherence || adherence.mean_intake_diff_kcal == null) {
    return "No real-intake logs yet";
  }
  const value = adherence.mean_intake_diff_kcal;
  return `${value >= 0 ? "+" : ""}${value.toFixed(0)} kcal${withPerDay ? "/day" : ""}`;
}

function formatDelta(value, unit, decimals = 1) {
  if (value == null || Number.isNaN(value)) return "";
  const arrow = value > 0 ? "▲" : value < 0 ? "▼" : "–";
  const sign = value > 0 ? "+" : "";
  return `<span class="delta">${arrow} ${sign}${value.toFixed(decimals)} ${unit}</span>`;
}

// Like formatDelta, but for "how far is the current value from a target"
// rather than "how much did this change since last week" -- appends a
// trailing "to goal" and lets the caller bake a leading space into `unit`
// (or not, for "%") instead of always inserting one. Normalizing through
// toFixed first avoids a stray "-0.0" once a goal is essentially reached.
function formatGoalDelta(remaining, unit) {
  if (remaining == null || Number.isNaN(remaining)) return "";
  const rounded = Number(remaining.toFixed(1));
  const arrow = rounded > 0 ? "▲" : rounded < 0 ? "▼" : "–";
  const sign = rounded > 0 ? "+" : "";
  return `<span class="delta">${arrow} ${sign}${rounded.toFixed(1)}${unit} to goal</span>`;
}

function statTile(label, value, delta = "") {
  return `
      <div class="stat-tile">
        <div class="label">${label}</div>
        <div class="value">${value}</div>
        ${delta}
      </div>`;
}

function badgeDelta(text, ok) {
  return `<span class="delta"><span class="badge ${ok ? "active" : "inactive"}">${text}</span></span>`;
}

export function renderWeightSummary(container, latest, previousMetrics, gainQualityLatest) {
  if (!latest) {
    container.innerHTML = `<p class="disclaimer">Log a week to see your stats.</p>`;
    return;
  }
  const bodyFatDeltaPp = previousMetrics ? (latest.body_fat - previousMetrics.body_fat) * 100 : null;
  container.innerHTML = [
    statTile(
      "Weight",
      `${(latest.fat_mass_kg + latest.lean_mass_kg).toFixed(1)} kg`,
      formatDelta(latest.weight_delta_kg, "kg")
    ),
    statTile(
      "Body fat",
      `${(latest.body_fat * 100).toFixed(1)}%`,
      formatDelta(bodyFatDeltaPp, "pp")
    ),
    statTile(
      "Lean mass",
      `${latest.lean_mass_kg.toFixed(1)} kg`,
      formatDelta(gainQualityLatest ? gainQualityLatest.delta_lean_kg : null, "kg", 2)
    ),
  ].join("");
}

export function renderCaloriesSummary(container, latest, adherence, latestRealLog) {
  if (!latest) {
    container.innerHTML = `<p class="disclaimer">Log a week to see your stats.</p>`;
    return;
  }
  container.innerHTML = [
    statTile(
      "Target calories",
      `${latest.target_calories.toFixed(0)} kcal`,
      `<span class="delta tile-subtitle">what to eat</span>`
    ),
    statTile(
      "TDEE",
      `${latest.tdee.toFixed(0)} kcal`,
      `<span class="delta tile-subtitle">estimated calories burned</span>`
    ),
    statTile(
      "This week's intake",
      latestRealLog && latestRealLog.intake_kcal != null ? `${latestRealLog.intake_kcal} kcal` : "—",
      `<span class="delta tile-subtitle">most recently logged intake</span>`
    ),
    statTile(
      "Adherence",
      formatAdherence(adherence, false),
      `<span class="delta tile-subtitle">actual vs target/day</span>`
    ),
  ].join("");
}

export function renderGoalSummary(container, latest, profile) {
  if (!latest) {
    container.innerHTML = `<p class="disclaimer">Log a week to see your goal progress.</p>`;
    return;
  }
  const isBulk = profile && profile.direction === "bulk";
  const hasTarget = profile && profile.target_bf != null;
  const targetBodyFatValue = hasTarget
    ? `${(profile.target_bf * 100).toFixed(1)}%`
    : `${(latest.body_fat * 100).toFixed(1)}%`;
  const targetBodyFatDelta = hasTarget
    ? formatGoalDelta((profile.target_bf - latest.body_fat) * 100, "%")
    : "";
  const currentWeightKg = latest.fat_mass_kg + latest.lean_mass_kg;
  const tiles = [
    statTile("Target body fat", targetBodyFatValue, targetBodyFatDelta),
    statTile(
      "Target weight (keep lean)",
      `${latest.final_weight_kg.toFixed(1)} kg`,
      formatGoalDelta(latest.final_weight_kg - currentWeightKg, " kg")
    ),
    statTile("Weeks to goal", metricsWeeksToGoal(latest)),
  ];
  if (profile && profile.direction) {
    tiles.push(statTile("Direction", isBulk ? "Bulk" : "Cut"));
  }
  container.innerHTML = tiles.join("");
}

function metricsWeeksToGoal(metrics) {
  return metrics.weeks_to_goal > 0 ? metrics.weeks_to_goal.toFixed(1) : "—";
}

export function renderDashboardStats(
  container,
  metrics,
  gainQualityLatest,
  energyBalanceLatest,
  incrementAnalyticsLatest
) {
  const tiles = [];
  if (metrics && metrics.tef_kcal != null) {
    tiles.push(
      statTile(
        "TEF (this week)",
        `${metrics.tef_kcal.toFixed(0)} kcal`,
        badgeDelta(metrics.tef_mode, metrics.tef_mode === "macros")
      )
    );
  }
  if (gainQualityLatest && gainQualityLatest.fat_ratio_cumulative != null) {
    const pct = gainQualityLatest.fat_ratio_cumulative * 100;
    const idealPct = gainQualityLatest.fat_ratio_ideal * 100;
    tiles.push(
      statTile(
        "Cumulative fat ratio",
        `${pct.toFixed(0)}%`,
        `<span class="delta">ideal ≤${idealPct.toFixed(0)}%</span>`
      )
    );
  }
  if (energyBalanceLatest && energyBalanceLatest.error_rolling_mean_kcal != null) {
    const err = energyBalanceLatest.error_rolling_mean_kcal;
    const threshold = energyBalanceLatest.error_threshold_kcal;
    tiles.push(
      statTile(
        "Energy-balance error (rolling)",
        `${err.toFixed(0)} kcal/day`,
        `<span class="delta">threshold ${threshold.toFixed(0)} kcal/day</span>`
      )
    );
  }
  if (incrementAnalyticsLatest) {
    tiles.push(
      statTile(
        "Avg weekly increment",
        `${(incrementAnalyticsLatest.incr_real_mean_pct * 100).toFixed(2)}%`,
        `<span class="delta">goal ${(incrementAnalyticsLatest.goal_weekly_rate * 100).toFixed(2)}%</span>`
      )
    );
    if (incrementAnalyticsLatest.deviation_pct != null) {
      tiles.push(
        statTile(
          "Deviation from goal rate",
          `${(incrementAnalyticsLatest.deviation_pct * 100).toFixed(0)}%`
        )
      );
    }
  }
  if (tiles.length === 0) {
    container.innerHTML = `<p class="disclaimer">No advanced stats yet.</p>`;
    return;
  }
  container.innerHTML = tiles.join("");
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

function dash(value) {
  return value == null ? "—" : value;
}

// Phase 4.5: a projected row (app.js's projectedLogRow(), log_id always null
// since it's never persisted) reuses this exact table -- same columns, same
// "projected" badge style real persisted-projection rows already used --
// rather than a separate preview widget; it just has no known intake/steps/
// cardio/macros/granularity to show (dashed) and no Delete button.
export function renderLogTable(tbody, logs) {
  tbody.innerHTML = logs
    .map(
      (log) => `
      <tr ${log.log_id != null ? `data-log-id="${log.log_id}"` : ""} class="${log.log_id == null ? "log-row-projected" : ""}">
        <td>${log.date}</td>
        <td>${log.weight_kg}</td>
        <td>${log.waist_cm}</td>
        <td>${log.neck_cm}</td>
        <td>${dash(log.intake_kcal)}</td>
        <td>${dash(log.steps)}</td>
        <td>${dash(log.cardio_kcal)}</td>
        <td>${formatMacros(log)}</td>
        <td><span class="badge ${log.source}">${log.source}</span></td>
        <td>${log.granularity ? `<span class="badge ${log.granularity}">${log.granularity}</span>` : "—"}</td>
        <td>${
          log.log_id != null
            ? `<button class="edit-log-btn" data-log-id="${log.log_id}">Edit</button> `
              + `<button class="delete-log-btn" data-log-id="${log.log_id}">Delete</button>`
            : ""
        }</td>
      </tr>`
    )
    .join("");
}

export function fillProfileForm(form, profile) {
  form.height_cm.value = profile.height_cm;
  form.sex.value = String(profile.sex);
  form.birthdate.value = profile.birthdate;
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
