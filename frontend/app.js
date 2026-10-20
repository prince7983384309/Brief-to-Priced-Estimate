// Points at the backend started with `python app/main.py` (see backend/README
// run instructions). Change this if you run the API on a different host/port.
const API_BASE_URL = "http://localhost:8000";

const form = document.getElementById("analyze-form");
const submitBtn = document.getElementById("submit-btn");
const errorMessage = document.getElementById("error-message");
const resultsSection = document.getElementById("results");
const apiBaseLabel = document.getElementById("api-base-label");

apiBaseLabel.textContent = `API: ${API_BASE_URL}`;

function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function badge(level) {
  if (!level) return "";
  const cls = { high: "badge-high", medium: "badge-medium", low: "badge-low" }[level] || "badge-medium";
  return `<span class="badge ${cls}">${escapeHtml(level)}</span>`;
}

function fieldRow(label, value, confidence) {
  const reason = confidence ? `<span class="field-reason">${escapeHtml(confidence.reason)}</span>` : "";
  return `
    <div class="field-row">
      <span class="field-name">${escapeHtml(label)}</span>
      <span class="field-value-group">
        <span class="field-value">${escapeHtml(value)}</span>${confidence ? badge(confidence.level) : ""}
        ${reason}
      </span>
    </div>`;
}

function renderReviewBanner(data) {
  if (data.review_required) {
    const reasons = data.review_reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join("");
    return `
      <div class="review-banner required">
        Human review recommended
        <ul>${reasons}</ul>
      </div>`;
  }
  return `<div class="review-banner not-required">No review flags raised</div>`;
}

function renderExtractedSpec(data) {
  const spec = data.extracted_spec;
  const fc = data.field_confidence;
  const sizeText =
    spec.dimensions.size !== null && spec.dimensions.size !== undefined
      ? `${spec.dimensions.size}${spec.dimensions.unit ? " " + spec.dimensions.unit : ""}`
      : "--";

  return `
    <div class="card">
      <h2>Extracted spec <span class="field-reason">(${escapeHtml(data.extraction_method)})</span></h2>
      ${fieldRow("Product type", spec.product_type, fc.product_type)}
      ${fieldRow("Material", spec.material, fc.material)}
      ${fieldRow("Gem count (from brief)", spec.gem_count, fc.gem_count)}
      ${fieldRow("Size", sizeText, fc.dimensions)}
      ${fieldRow("Budget", spec.budget !== null ? spec.budget : "--")}
      ${fieldRow("Notes", spec.notes || "--")}
    </div>`;
}

function renderMatches(data) {
  if (!data.top_matches || data.top_matches.length === 0) {
    return `<div class="card"><h2>Inventory matches</h2><p>No candidates found.</p></div>`;
  }
  const rows = data.top_matches
    .map(
      (m, i) => `
      <tr class="${i === 0 ? "top-pick" : ""}">
        <td>${escapeHtml(m.sku)}</td>
        <td>${m.score.toFixed(2)}</td>
        <td>${escapeHtml(m.product_type)}</td>
        <td>${escapeHtml(m.material)}</td>
        <td>${m.gem_count}</td>
        <td>$${m.price.toFixed(2)}</td>
      </tr>`
    )
    .join("");

  return `
    <div class="card">
      <h2>Top inventory matches</h2>
      <table>
        <thead>
          <tr><th>SKU</th><th>Score</th><th>Type</th><th>Material</th><th>Gems</th><th>Price</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function renderCvEstimate(data) {
  const cv = data.cv_estimate;
  if (!cv) return "";
  const visionRow =
    cv.vision_llm_estimate !== null && cv.vision_llm_estimate !== undefined
      ? fieldRow("Vision-LLM estimate", cv.vision_llm_estimate, { level: null, reason: cv.vision_llm_reason })
      : "";

  return `
    <div class="card">
      <h2>Image-based gem count</h2>
      ${fieldRow("Classical CV estimate", cv.estimated_gem_count ?? "--", cv.confidence)}
      <p class="field-reason">method: ${escapeHtml(cv.method)}</p>
      ${visionRow}
    </div>`;
}

function renderPriceEstimate(data) {
  const price = data.price_estimate;
  if (!price) return "";
  return `
    <div class="card">
      <h2>Priced estimate</h2>
      <p class="price">$${price.estimated_price.toFixed(2)} ${badge(price.confidence.level)}</p>
      <p class="field-reason">based on ${escapeHtml(price.based_on_sku)} -- ${escapeHtml(price.reason)}</p>
    </div>`;
}

function renderResults(data) {
  resultsSection.innerHTML =
    renderReviewBanner(data) +
    renderExtractedSpec(data) +
    renderMatches(data) +
    renderCvEstimate(data) +
    renderPriceEstimate(data);
  resultsSection.classList.remove("hidden");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorMessage.classList.add("hidden");
  resultsSection.classList.add("hidden");
  submitBtn.disabled = true;
  submitBtn.textContent = "Analyzing...";

  try {
    const formData = new FormData();
    formData.append("brief", document.getElementById("brief").value);
    const imageFile = document.getElementById("image").files[0];
    if (imageFile) formData.append("image", imageFile);

    const response = await fetch(`${API_BASE_URL}/analyze`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Server returned ${response.status}: ${text}`);
    }

    const data = await response.json();
    renderResults(data);
  } catch (err) {
    errorMessage.textContent = `Request failed: ${err.message}. Is the backend running at ${API_BASE_URL}?`;
    errorMessage.classList.remove("hidden");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Analyze";
  }
});
