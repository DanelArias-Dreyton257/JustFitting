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

export function renderDashboardStats(container, metrics) {
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
