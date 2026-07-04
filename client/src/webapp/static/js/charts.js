// Hand-rolled SVG charts -- no bundler, no charting library dependency.

const LAYOUT = { top: 12, right: 16, bottom: 26, left: 38 };
const Y_TICK_COUNT = 4;
const X_TICK_COUNT = 4;

function scaleLinear(domain, range) {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  const span = d1 - d0 || 1;
  return (value) => r0 + ((value - d0) / span) * (r1 - r0);
}

function toEpoch(dateStr) {
  return new Date(dateStr).getTime();
}

function formatDateTick(dateStr) {
  return new Date(dateStr).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function buildDateXScale(series, width) {
  const epochs = series.map((row) => toEpoch(row.date));
  return scaleLinear(
    [Math.min(...epochs), Math.max(...epochs)],
    [LAYOUT.left, width - LAYOUT.right]
  );
}

function niceValueTicks(min, max, count) {
  if (min === max) return [min];
  const step = (max - min) / (count - 1);
  return Array.from({ length: count }, (_, i) => min + step * i);
}

function formatValueTick(value) {
  return Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(1);
}

function svgEl(tag, attrs) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attrs).forEach(([key, val]) => el.setAttribute(key, val));
  return el;
}

// `xPositions[i]` is the already-computed pixel x for `series[i]`, so this
// works whether the caller spaced points by date (line/multi-line charts)
// or by index (bar chart).
function drawAxes(svg, { series, xPositions, yScale, yDomain, width, height }) {
  niceValueTicks(yDomain[0], yDomain[1], Y_TICK_COUNT).forEach((tick) => {
    const y = yScale(tick);
    svg.appendChild(
      svgEl("line", {
        x1: LAYOUT.left,
        x2: width - LAYOUT.right,
        y1: y,
        y2: y,
        class: "chart-gridline",
      })
    );
    const label = svgEl("text", { x: 2, y: y + 3, class: "chart-axis-label" });
    label.textContent = formatValueTick(tick);
    svg.appendChild(label);
  });

  const tickIndexes = new Set();
  for (let i = 0; i < X_TICK_COUNT; i++) {
    tickIndexes.add(Math.round((i * (series.length - 1)) / Math.max(X_TICK_COUNT - 1, 1)));
  }
  tickIndexes.forEach((i) => {
    const row = series[i];
    if (!row) return;
    const label = svgEl("text", {
      x: xPositions[i],
      y: height - 6,
      class: "chart-axis-label",
      "text-anchor": "middle",
    });
    label.textContent = formatDateTick(row.date);
    svg.appendChild(label);
  });
}

function ensureTooltip(svg) {
  const card = svg.closest(".chart-card") || svg.parentElement;
  let tip = card.querySelector(".chart-tooltip");
  if (!tip) {
    tip = document.createElement("div");
    tip.className = "chart-tooltip";
    tip.hidden = true;
    card.appendChild(tip);
  }
  return tip;
}

// `points`: [{x, datum}]. Re-attaching on every redraw would pile up
// listeners on the same <svg> element (innerHTML="" clears children, not
// the element's own listeners), so the previous handlers are removed first.
function attachHoverTooltip(svg, points, formatTooltip) {
  const tip = ensureTooltip(svg);
  if (svg._chartMouseMove) svg.removeEventListener("mousemove", svg._chartMouseMove);
  if (svg._chartMouseLeave) svg.removeEventListener("mouseleave", svg._chartMouseLeave);

  if (!points.length) {
    tip.hidden = true;
    return;
  }

  const onMove = (event) => {
    const rect = svg.getBoundingClientRect();
    const viewBoxWidth = (svg.viewBox.baseVal && svg.viewBox.baseVal.width) || rect.width;
    const mouseX = ((event.clientX - rect.left) / rect.width) * viewBoxWidth;
    let nearest = points[0];
    let minDist = Infinity;
    points.forEach((point) => {
      const dist = Math.abs(point.x - mouseX);
      if (dist < minDist) {
        minDist = dist;
        nearest = point;
      }
    });
    tip.innerHTML = formatTooltip(nearest.datum);
    tip.hidden = false;
    tip.style.left = `${event.clientX - rect.left + 12}px`;
    tip.style.top = `${Math.max(0, event.clientY - rect.top - 12)}px`;
  };
  const onLeave = () => {
    tip.hidden = true;
  };
  svg._chartMouseMove = onMove;
  svg._chartMouseLeave = onLeave;
  svg.addEventListener("mousemove", onMove);
  svg.addEventListener("mouseleave", onLeave);
}

export function drawLineChart(svg, series, { color = "#5eb3ff", label = "Value" } = {}) {
  svg.innerHTML = "";
  if (!series.length) {
    attachHoverTooltip(svg, [], () => "");
    return;
  }

  const width = svg.clientWidth || 320;
  const height = svg.clientHeight || 180;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const values = series.map((point) => point.value);
  const yDomain = [Math.min(...values), Math.max(...values) || 1];
  const xScale = buildDateXScale(series, width);
  const yScale = scaleLinear(yDomain, [height - LAYOUT.bottom, LAYOUT.top]);
  const xPositions = series.map((point) => xScale(toEpoch(point.date)));

  drawAxes(svg, { series, xPositions, yScale, yDomain, width, height });

  const points = series.map((point, i) => [xPositions[i], yScale(point.value)]);
  const path = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x},${y}`).join(" ");

  svg.appendChild(svgEl("path", { d: path, fill: "none", stroke: color, "stroke-width": "2" }));

  points.forEach(([x, y], i) => {
    svg.appendChild(
      svgEl("circle", {
        cx: x,
        cy: y,
        r: series[i].projected ? 2 : 3,
        fill: series[i].projected ? "#e5686b" : color,
      })
    );
  });

  attachHoverTooltip(
    svg,
    series.map((point, i) => ({ x: xPositions[i], datum: point })),
    (point) =>
      `<strong>${formatDateTick(point.date)}</strong><br>${label}: ${point.value.toFixed(1)}` +
      (point.projected ? " (forecast)" : "")
  );
}

export function drawMultiLineChart(svg, series, lines, { isProjected = () => false, markers = [] } = {}) {
  svg.innerHTML = "";
  if (!series.length) {
    attachHoverTooltip(svg, [], () => "");
    return;
  }

  const width = svg.clientWidth || 320;
  const height = svg.clientHeight || 180;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const allValues = lines.flatMap((line) => series.map((row) => line.accessor(row)));
  const yDomain = [Math.min(...allValues), Math.max(...allValues) || 1];
  const xScale = buildDateXScale(series, width);
  const yScale = scaleLinear(yDomain, [height - LAYOUT.bottom, LAYOUT.top]);
  const xPositions = series.map((row) => xScale(toEpoch(row.date)));

  drawAxes(svg, { series, xPositions, yScale, yDomain, width, height });

  lines.forEach((line) => {
    const points = series.map((row, i) => [xPositions[i], yScale(line.accessor(row))]);
    const path = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x},${y}`).join(" ");

    svg.appendChild(
      svgEl("path", {
        d: path,
        fill: "none",
        stroke: line.color,
        "stroke-width": "2",
        ...(line.dashed ? { "stroke-dasharray": "5,4" } : {}),
      })
    );

    points.forEach(([x, y], i) => {
      svg.appendChild(
        svgEl("circle", { cx: x, cy: y, r: isProjected(series[i]) ? 2 : 3, fill: line.color })
      );
    });
  });

  markers.forEach((marker) => {
    const rawX = xScale(toEpoch(marker.date));
    const x = Math.min(Math.max(rawX, LAYOUT.left), width - LAYOUT.right);
    const markerLine = svgEl("line", {
      x1: x,
      x2: x,
      y1: LAYOUT.top,
      y2: height - LAYOUT.bottom,
      class: "chart-marker-line",
    });
    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = marker.label;
    markerLine.appendChild(title);
    svg.appendChild(markerLine);
  });

  attachHoverTooltip(
    svg,
    series.map((row, i) => ({ x: xPositions[i], datum: row })),
    (row) => {
      const linesHtml = lines
        .map(
          (line) =>
            `<span style="color:${line.color}">●</span> ${line.label || ""}: ${line
              .accessor(row)
              .toFixed(1)}`
        )
        .join("<br>");
      return `<strong>${formatDateTick(row.date)}</strong><br>${linesHtml}`;
    }
  );
}

// Two 100%-comparable columns ("Target" vs "Actual"), each stacked by
// macronutrient (protein/fat/carbs kcal) -- a 2px surface-color gap
// separates touching segments, same convention as any other stacked mark.
// `bars`: [{ label, segments: [{ label, value, color }] }].
export function drawMacroSplitBars(svg, bars) {
  svg.innerHTML = "";
  if (!bars.length) {
    attachHoverTooltip(svg, [], () => "");
    return;
  }

  const width = svg.clientWidth || 320;
  const height = svg.clientHeight || 180;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const SEGMENT_GAP = 2;
  const totals = bars.map((bar) => bar.segments.reduce((sum, seg) => sum + seg.value, 0));
  const maxTotal = Math.max(...totals) || 1;
  const yScale = scaleLinear([0, maxTotal], [height - LAYOUT.bottom, LAYOUT.top]);
  const slotWidth = (width - LAYOUT.left - LAYOUT.right) / bars.length;
  const barWidth = Math.min(64, slotWidth * 0.5);
  const xPositions = bars.map((_, i) => LAYOUT.left + i * slotWidth + slotWidth / 2);

  niceValueTicks(0, maxTotal, Y_TICK_COUNT).forEach((tick) => {
    const y = yScale(tick);
    svg.appendChild(
      svgEl("line", {
        x1: LAYOUT.left,
        x2: width - LAYOUT.right,
        y1: y,
        y2: y,
        class: "chart-gridline",
      })
    );
    const label = svgEl("text", { x: 2, y: y + 3, class: "chart-axis-label" });
    label.textContent = formatValueTick(tick);
    svg.appendChild(label);
  });

  const hoverPoints = [];
  bars.forEach((bar, i) => {
    const x = xPositions[i] - barWidth / 2;
    let cumulative = 0;
    bar.segments.forEach((segment, segIndex) => {
      const yTop = yScale(cumulative + segment.value);
      const yBottom = yScale(cumulative);
      const gapTop = segIndex < bar.segments.length - 1 ? SEGMENT_GAP / 2 : 0;
      const gapBottom = segIndex > 0 ? SEGMENT_GAP / 2 : 0;
      svg.appendChild(
        svgEl("rect", {
          x,
          y: yTop + gapTop,
          width: barWidth,
          height: Math.max(0, yBottom - yTop - gapTop - gapBottom),
          fill: segment.color,
        })
      );
      cumulative += segment.value;
    });

    const label = svgEl("text", {
      x: xPositions[i],
      y: height - 6,
      class: "chart-axis-label",
      "text-anchor": "middle",
    });
    label.textContent = bar.label;
    svg.appendChild(label);

    hoverPoints.push({ x: xPositions[i], datum: bar });
  });

  attachHoverTooltip(svg, hoverPoints, (bar) => {
    const total = bar.segments.reduce((sum, seg) => sum + seg.value, 0) || 1;
    const rows = bar.segments
      .map(
        (seg) =>
          `<span style="color:${seg.color}">●</span> ${seg.label}: ${seg.value.toFixed(
            0
          )} kcal (${((seg.value / total) * 100).toFixed(0)}%)`
      )
      .join("<br>");
    return `<strong>${bar.label}</strong><br>${rows}<br>Total: ${total.toFixed(0)} kcal`;
  });
}

export function drawStackedBars(svg, series) {
  svg.innerHTML = "";
  if (!series.length) {
    attachHoverTooltip(svg, [], () => "");
    return;
  }

  const width = svg.clientWidth || 320;
  const height = svg.clientHeight || 180;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const totals = series.map((point) => point.fat + point.lean);
  const maxTotal = Math.max(...totals) || 1;
  const yDomain = [0, maxTotal];
  const yScale = scaleLinear(yDomain, [height - LAYOUT.bottom, LAYOUT.top]);
  const barWidth = (width - LAYOUT.left - LAYOUT.right) / series.length;
  const xPositions = series.map((_, i) => LAYOUT.left + i * barWidth + (barWidth * 0.7) / 2);

  drawAxes(svg, { series, xPositions, yScale, yDomain, width, height });

  const plotTop = LAYOUT.top;
  const plotBottom = height - LAYOUT.bottom;

  series.forEach((point, i) => {
    const x = LAYOUT.left + i * barWidth;
    const fatHeight = ((plotBottom - plotTop) * point.fat) / maxTotal;
    const leanHeight = ((plotBottom - plotTop) * point.lean) / maxTotal;

    svg.appendChild(
      svgEl("rect", {
        x,
        y: plotBottom - leanHeight,
        width: barWidth * 0.7,
        height: leanHeight,
        fill: "#5eb3ff",
      })
    );
    svg.appendChild(
      svgEl("rect", {
        x,
        y: plotBottom - leanHeight - fatHeight,
        width: barWidth * 0.7,
        height: fatHeight,
        fill: "#e5686b",
      })
    );
  });

  attachHoverTooltip(
    svg,
    series.map((point, i) => ({ x: xPositions[i], datum: point })),
    (point) =>
      `<strong>${formatDateTick(point.date)}</strong><br>Fat: ${point.fat.toFixed(1)} kg<br>Lean: ${point.lean.toFixed(1)} kg`
  );
}

// Like drawStackedBars, but each of `fat`/`lean` can be negative (a loss
// week) -- segments stack outward from a zero baseline instead of always
// upward from the bottom, so a lean gain alongside a fat loss in the same
// week renders as two bars on opposite sides of zero, not one merged into
// the other's sign.
export function drawDivergingBars(svg, series) {
  svg.innerHTML = "";
  if (!series.length) {
    attachHoverTooltip(svg, [], () => "");
    return;
  }

  const width = svg.clientWidth || 320;
  const height = svg.clientHeight || 180;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const maxPositive = Math.max(0, ...series.map((p) => Math.max(p.fat, 0) + Math.max(p.lean, 0)));
  const minNegative = Math.min(0, ...series.map((p) => Math.min(p.fat, 0) + Math.min(p.lean, 0)));
  const yDomain = [minNegative, maxPositive];
  const yScale = scaleLinear(yDomain, [height - LAYOUT.bottom, LAYOUT.top]);
  const barWidth = (width - LAYOUT.left - LAYOUT.right) / series.length;
  const xPositions = series.map((_, i) => LAYOUT.left + i * barWidth + (barWidth * 0.7) / 2);

  drawAxes(svg, { series, xPositions, yScale, yDomain, width, height });

  const zeroY = yScale(0);
  svg.appendChild(
    svgEl("line", {
      x1: LAYOUT.left,
      x2: width - LAYOUT.right,
      y1: zeroY,
      y2: zeroY,
      class: "chart-gridline",
    })
  );

  series.forEach((point, i) => {
    const x = LAYOUT.left + i * barWidth;
    let posOffset = 0;
    let negOffset = 0;
    [
      { value: point.lean, color: "#5eb3ff" },
      { value: point.fat, color: "#e5686b" },
    ].forEach(({ value, color }) => {
      if (value === 0) return;
      if (value > 0) {
        const y = yScale(posOffset + value);
        const barHeight = yScale(posOffset) - y;
        svg.appendChild(
          svgEl("rect", { x, y, width: barWidth * 0.7, height: barHeight, fill: color })
        );
        posOffset += value;
      } else {
        const y = yScale(negOffset);
        const barHeight = yScale(negOffset + value) - y;
        svg.appendChild(
          svgEl("rect", { x, y, width: barWidth * 0.7, height: barHeight, fill: color })
        );
        negOffset += value;
      }
    });
  });

  attachHoverTooltip(
    svg,
    series.map((point, i) => ({ x: xPositions[i], datum: point })),
    (point) =>
      `<strong>${formatDateTick(point.date)}</strong><br>Lean: ${point.lean.toFixed(2)} kg<br>Fat: ${point.fat.toFixed(2)} kg`
  );
}
