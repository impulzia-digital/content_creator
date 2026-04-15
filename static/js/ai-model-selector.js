/**
 * AI Model Selector — Dynamic binding between provider and model selects.
 *
 * Expects `window.__MODEL_CATALOG__` to be set (JSON dict keyed by provider→capability→[models]).
 * Looks for `.ai-provider-select[data-capability]` and `.ai-model-select[data-capability]`.
 */
(function () {
  "use strict";

  const catalog = window.__MODEL_CATALOG__;
  if (!catalog) return;

  const TIER_ORDER = { Potente: 0, Balanceado: 1, Eficiente: 2 };

  function buildOptions(models) {
    if (!models || !models.length) return [];
    const sorted = models.slice().sort(
      (a, b) => (TIER_ORDER[a.tier] ?? 99) - (TIER_ORDER[b.tier] ?? 99)
    );
    return sorted.map(function (m) {
      let label = m.label + " \u2014 " + m.tier;
      const badges = [];
      if (m.is_preview) badges.push("Preview");
      if (m.is_recommended) badges.push("\u2605");
      if (badges.length) label += " (" + badges.join(", ") + ")";
      return { value: m.value, label: label, description: m.description };
    });
  }

  function populateModelSelect(selectEl, provider, capability) {
    // Save current value to try to preserve it
    const current = selectEl.value;

    // Clear everything except the default and custom options
    while (selectEl.options.length > 0) selectEl.remove(0);

    // Add default option
    const defOpt = document.createElement("option");
    defOpt.value = "";
    defOpt.textContent = "\u2014 Usar default \u2014";
    selectEl.appendChild(defOpt);

    // Add catalog models for this provider+capability
    if (provider && catalog[provider] && catalog[provider][capability]) {
      const options = buildOptions(catalog[provider][capability]);
      options.forEach(function (o) {
        const opt = document.createElement("option");
        opt.value = o.value;
        opt.textContent = o.label;
        if (o.description) opt.title = o.description;
        selectEl.appendChild(opt);
      });
    }

    // Add custom option at the end
    const customOpt = document.createElement("option");
    customOpt.value = "__custom__";
    customOpt.textContent = "\u270f\ufe0f Modelo personalizado\u2026";
    selectEl.appendChild(customOpt);

    // Try to restore previous selection
    if (current && Array.from(selectEl.options).some(function (o) { return o.value === current; })) {
      selectEl.value = current;
    } else {
      selectEl.value = "";
    }
  }

  function toggleCustomInput(container, show) {
    const customDiv = container.querySelector(".ai-custom-model");
    if (customDiv) {
      customDiv.classList.toggle("hidden", !show);
    }
  }

  // Initialize for each capability block
  document.querySelectorAll(".ai-provider-select").forEach(function (providerSelect) {
    const capability = providerSelect.dataset.capability;
    const container = providerSelect.closest("div[data-capability]");
    const modelSelect = container.querySelector(".ai-model-select");
    if (!modelSelect) return;

    // On provider change → repopulate models
    providerSelect.addEventListener("change", function () {
      populateModelSelect(modelSelect, providerSelect.value, capability);
      toggleCustomInput(container, false);
    });

    // On model change → toggle custom input
    modelSelect.addEventListener("change", function () {
      toggleCustomInput(container, modelSelect.value === "__custom__");
    });

    // Initial population if a provider is already selected
    if (providerSelect.value) {
      populateModelSelect(modelSelect, providerSelect.value, capability);
    }
  });
})();
