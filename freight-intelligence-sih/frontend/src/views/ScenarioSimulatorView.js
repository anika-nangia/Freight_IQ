/**
 * Scenario Simulator View Component
 * Supports Counterfactual analysis & parameter weightage adjustments.
 */
export function renderScenarioSimulator(weights, onUpdateWeights) {
  return `
    <div class="card-elevation p-6 bg-white">
      <h3 class="font-bold text-slate-900 font-outfit text-base mb-1">Market Scenario Simulator</h3>
      <p class="text-xs text-slate-500 mb-4">Simulate how weather disruptions and port waiting queues shift spot charter rates.</p>
      
      <div class="space-y-4 text-xs">
        <div>
          <label class="font-semibold text-slate-700 block mb-1">Weather & Cyclone Stress (IMD Alert)</label>
          <input type="range" min="0.5" max="2.5" step="0.1" value="${weights.weather}" class="w-full accent-blue-600">
        </div>
        <div>
          <label class="font-semibold text-slate-700 block mb-1">Berth Congestion Weight</label>
          <input type="range" min="0.5" max="2.5" step="0.1" value="${weights.congestion}" class="w-full accent-blue-600">
        </div>
      </div>
    </div>
  `;
}
