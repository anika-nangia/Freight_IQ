/**
 * Risk Tier Badge Component (Pillar D)
 */
export function renderRiskBadge(riskTier, reason) {
  const colors = {
    High: "bg-rose-100 text-rose-800 border-rose-200",
    Medium: "bg-amber-100 text-amber-800 border-amber-200",
    Low: "bg-emerald-100 text-emerald-800 border-emerald-200"
  };
  const colorClass = colors[riskTier] || colors.Low;

  return `
    <div class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${colorClass}">
      <span class="w-2 h-2 rounded-full ${riskTier === 'High' ? 'bg-rose-600 animate-ping' : riskTier === 'Medium' ? 'bg-amber-600' : 'bg-emerald-600'}"></span>
      <span>${riskTier} Risk</span>
      <span class="font-normal text-slate-600 ml-1">· ${reason}</span>
    </div>
  `;
}
