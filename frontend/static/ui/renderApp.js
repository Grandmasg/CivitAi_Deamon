// Main app rendering logic for CivitAI frontend
// Assembles the UI from modular components

import { renderFilters } from './renderFilters.js';
import { renderBatchControls, renderStickyBatchBtn, renderNextBtnBottom } from './batchControls.js';
import { renderResults } from './renderResults.js';
import { flattenModels } from './flattenModels.js';
import { escapeHtml } from './escapeHtml.js';

export function renderApp(state, modelManager) {
  const app = document.getElementById('app');
  app.innerHTML = `
    <div class="container-fluid py-4">
      <div class="row justify-content-center">
        <div class="col-12 col-lg-10">
          <form class="bg-white p-4 rounded shadow-sm" id="searchForm">
            <h4 class="mb-4">🔍 Search Filters</h4>
            ${renderFilters(state)}
          </form>
          ${renderBatchControls(state)}
          <div class="model-results mt-4" style="min-height:300px;">
            ${renderResults(state, flattenModels, escapeHtml, modelManager)}
          </div>
          ${renderNextBtnBottom(state)}
        </div>
      </div>
    </div>
    ${renderStickyBatchBtn(state)}
    <!-- Modal for model details -->
    <div class="modal fade" id="modelDetailModal" tabindex="-1" aria-labelledby="modelDetailModalLabel" aria-hidden="true">
      <div class="modal-dialog modal-lg modal-dialog-centered" style="max-width:80vw;width:80vw;">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="modelDetailModalLabel">Model Details</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body" id="modelDetailModalBody">
            <!-- Content set by JS -->
          </div>
        </div>
      </div>
    </div>
  `;
}
