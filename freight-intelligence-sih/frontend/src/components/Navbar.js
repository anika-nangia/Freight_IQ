/**
 * Navbar & Top Navigation Component
 */
export function createNavbar(user, onOpenLogin, onOpenSidebar) {
  return `
    <header class="bg-white border-b border-slate-200 sticky top-0 z-40">
      <div class="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <button id="sidebarToggleBtn" class="p-2 text-slate-600 hover:bg-slate-100 rounded-lg">☰</button>
          <img src="assets/logo.png" alt="FreightIQ" class="w-9 h-9 rounded-full">
          <span class="text-xl font-bold font-outfit">Freight<span class="text-blue-600">IQ</span></span>
        </div>
      </div>
    </header>
  `;
}
