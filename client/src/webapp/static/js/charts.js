// Hand-rolled SVG charts -- no bundler, no charting library dependency.

function scaleLinear(domain, range) {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  const span = d1 - d0 || 1;
  return (value) => r0 + ((value - d0) / span) * (r1 - r0);
}

export function drawLineChart(svg, series, { color = "#5eb3ff" } = {}) {
  svg.innerHTML = "";
  if (!series.length) return;

  const width = svg.clientWidth || 320;
  const height = svg.clientHeight || 180;
  const padding = 24;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const values = series.map((point) => point.value);
  const xScale = scaleLinear([0, series.length - 1], [padding, width - padding]);
  const yScale = scaleLinear(
    [Math.min(...values), Math.max(...values) || 1],
    [height - padding, padding]
  );

  const points = series.map((point, i) => [xScale(i), yScale(point.value)]);
  const path = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x},${y}`).join(" ");

  const pathEl = document.createElementNS("http://www.w3.org/2000/svg", "path");
  pathEl.setAttribute("d", path);
  pathEl.setAttribute("fill", "none");
  pathEl.setAttribute("stroke", color);
  pathEl.setAttribute("stroke-width", "2");
  svg.appendChild(pathEl);

  points.forEach(([x, y], i) => {
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", x);
    circle.setAttribute("cy", y);
    circle.setAttribute("r", series[i].projected ? 2 : 3);
    circle.setAttribute("fill", series[i].projected ? "#e5686b" : color);
    svg.appendChild(circle);
  });
}

export function drawStackedBars(svg, series) {
  svg.innerHTML = "";
  if (!series.length) return;

  const width = svg.clientWidth || 320;
  const height = svg.clientHeight || 180;
  const padding = 24;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const totals = series.map((point) => point.fat + point.lean);
  const maxTotal = Math.max(...totals) || 1;
  const barWidth = (width - padding * 2) / series.length;

  series.forEach((point, i) => {
    const x = padding + i * barWidth;
    const fatHeight = ((height - padding * 2) * point.fat) / maxTotal;
    const leanHeight = ((height - padding * 2) * point.lean) / maxTotal;

    const lean = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    lean.setAttribute("x", x);
    lean.setAttribute("y", height - padding - leanHeight);
    lean.setAttribute("width", barWidth * 0.7);
    lean.setAttribute("height", leanHeight);
    lean.setAttribute("fill", "#5eb3ff");
    svg.appendChild(lean);

    const fat = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    fat.setAttribute("x", x);
    fat.setAttribute("y", height - padding - leanHeight - fatHeight);
    fat.setAttribute("width", barWidth * 0.7);
    fat.setAttribute("height", fatHeight);
    fat.setAttribute("fill", "#e5686b");
    svg.appendChild(fat);
  });
}
