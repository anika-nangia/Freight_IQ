/**
 * FreightIQ Frontend Master Application Script
 * Pure Vanilla JavaScript (ES6+), HTML5, and Tailwind CSS.
 * Bulk Carrier Maritime Decision Support System (Ministry of Steel / SAIL)
 */

// Global State
const state = {
  user: null,
  activeTab: "dashboard", // "dashboard" | "dual-forecast" | "recommendations" | "idle-analysis" | "port-map" | "model-analysis"
  hasCalculatedPrice: false,
  selectedForecastPort: "vizag",
  modelHistory: [],
  modelHistoryFilter: { search: "", vessel: "all", category: "all" },
  query: {
    origin: "Indian East Coast Ports, India",
    originCountry: "India",
    destination: "Australia \u2014 Newcastle - Kooragang",
    destinationState: "New South Wales",
    vesselType: "Supramax",
    unit: "$/Ton"
  },
  scenarioWeights: {
    weather: 1.0,
    congestion: 1.0,
    fuel: 1.0,
    fx: 1.0
  },
  portsIndia: [
    {
      id: "vizag",
      name: "Visakhapatnam (Vizag)",
      state: "Andhra Pradesh",
      lat: 17.686,
      lng: 83.280,
      maxDraft: 18.0,
      maxLoa: 320,
      berths: 26,
      status: "congested",
      congestion: 72,
      waiting: 6,
      description: "Vital gateway for metallurgical and coking coal. Acts as a primary entry point for Mozambican coking coal (destined for Indian steel giants like SAIL) as well as Australian coking coal."
    },
    {
      id: "gangavaram",
      name: "Gangavaram Port",
      state: "Andhra Pradesh",
      lat: 17.633,
      lng: 83.221,
      maxDraft: 21.0,
      maxLoa: 350,
      berths: 10,
      status: "operational",
      congestion: 44,
      waiting: 2,
      description: "Crucial deep-water gateway on India's east coast (deepest draft in India at 21m). Plays a significant role in receiving Capesize bulk imports: metallurgical/coking coal, thermal coal, and raw minerals from Australia, Indonesia, and Russia."
    },
    {
      id: "gopalpur",
      name: "Gopalpur Port",
      state: "Odisha",
      lat: 19.267,
      lng: 84.900,
      maxDraft: 12.5,
      maxLoa: 225,
      berths: 4,
      status: "operational",
      congestion: 30,
      waiting: 1,
      description: "Strategic deep-water gateway on the Odisha coast receiving bulk imports of metallurgical/coking coal and raw minerals from Australia, Indonesia, and Russia."
    },
    {
      id: "paradip",
      name: "Paradip Port",
      state: "Odisha",
      lat: 20.270,
      lng: 86.670,
      maxDraft: 14.5,
      maxLoa: 295,
      berths: 18,
      status: "congested",
      congestion: 68,
      waiting: 5,
      description: "Major deep-water port with dedicated mechanized coal import and iron ore export handling systems. Heavy volume handling point for SAIL steel plants."
    },
    {
      id: "dhamra",
      name: "Dhamra Port",
      state: "Odisha",
      lat: 20.762,
      lng: 86.903,
      maxDraft: 17.0,
      maxLoa: 300,
      berths: 8,
      status: "operational",
      congestion: 38,
      waiting: 2,
      description: "All-weather deep-water bulk port capable of handling Capesize vessels with direct rail connectivity to Odisha and Jharkhand steel/coal belts."
    },
    {
      id: "sagar-sandheads",
      name: "Sagar-Sandheads",
      state: "West Bengal",
      lat: 21.300,
      lng: 88.150,
      maxDraft: 14.0,
      maxLoa: 260,
      berths: 6,
      status: "operational",
      congestion: 42,
      waiting: 3,
      description: "Critically linked maritime locations in the Bay of Bengal serving as mandatory maritime staging gates, anchorage points, and pilotage stations for Kolkata Port and Haldia. Large merchant vessels must lighter or anchor here before entering the shallow, treacherous Hooghly river channel."
    },
    {
      id: "haldia",
      name: "Haldia Dock Complex",
      state: "West Bengal",
      lat: 22.028,
      lng: 88.068,
      maxDraft: 8.5,
      maxLoa: 210,
      berths: 24,
      status: "operational",
      congestion: 52,
      waiting: 4,
      description: "Operating as the principal 'Gateway of Eastern India,' Haldia heavily processes shipments arriving from Indonesia, Southeast Asia, and Australia. Docks tailored for coal, chemicals, and heavy industrial machinery."
    }
  ]
};

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
  initAuth();
  initModelHistory();
  initMaritimeAnimation();
  initEventListeners();
  renderApp();
});

// -------------------------------------------------------------
// 1. AUTHENTICATION & LOGIN POPUP LOGIC
// -------------------------------------------------------------

function initAuth() {
  const saved = localStorage.getItem("freightiq_user");
  if (saved) {
    try {
      state.user = JSON.parse(saved);
    } catch (e) {
      state.user = null;
    }
  }
  updateAuthUI();
}

function isLoggedIn() {
  return state.user !== null;
}

function updateAuthUI() {
  const authNav = document.getElementById("authNavSection");
  const loginOverlay = document.getElementById("loginLockOverlay");
  const searchInputs = document.querySelectorAll(".auth-guarded-input");

  if (isLoggedIn()) {
    if (authNav) {
      authNav.innerHTML = `
        <div class="flex items-center gap-3">
          <div class="text-right hidden sm:block">
            <div class="text-xs font-semibold text-slate-800">${state.user.name}</div>
            <div class="text-[10px] text-blue-600 font-medium">${state.user.company}</div>
          </div>
          <div class="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-xs border border-blue-300">
            ${state.user.name ? state.user.name.charAt(0) : "U"}
          </div>
          <button id="logoutBtn" class="text-xs text-slate-500 hover:text-red-600 font-medium px-2 py-1 rounded transition-colors flex items-center gap-1">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>
            Logout
          </button>
        </div>
      `;
      document.getElementById("logoutBtn")?.addEventListener("click", handleLogout);
    }
    if (loginOverlay) loginOverlay.classList.add("hidden");
    searchInputs.forEach((el) => {
      el.removeAttribute("disabled");
      el.classList.remove("cursor-pointer", "bg-slate-50");
    });
  } else {
    if (authNav) {
      authNav.innerHTML = `
        <button id="navLoginBtn" class="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-colors shadow-sm flex items-center gap-1.5 font-outfit">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"/></svg>
          Login
        </button>
      `;
      document.getElementById("navLoginBtn")?.addEventListener("click", openLoginModal);
    }
    if (loginOverlay) loginOverlay.classList.remove("hidden");
    searchInputs.forEach((el) => {
      el.setAttribute("disabled", "true");
      el.classList.add("cursor-pointer");
    });
  }
}

function openLoginModal() {
  const modal = document.getElementById("loginModal");
  if (modal) {
    // Requirements: inputs should be completely empty when first opened!
    const emailInput = document.getElementById("loginEmailInput");
    const pwdInput = document.getElementById("loginEmailPwd");
    const phoneInput = document.getElementById("loginPhoneInput");
    const otpInput = document.getElementById("loginPhoneOtp");
    const errEl = document.getElementById("loginErrorMsg");

    if (emailInput) emailInput.value = "";
    if (pwdInput) pwdInput.value = "";
    if (phoneInput) phoneInput.value = "";
    if (otpInput) otpInput.value = "";
    if (errEl) errEl.classList.add("hidden");

    modal.classList.remove("hidden");
    modal.classList.add("flex");
  }
}

function closeLoginModal() {
  const modal = document.getElementById("loginModal");
  if (modal) {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  }
  const errEl = document.getElementById("loginErrorMsg");
  if (errEl) errEl.classList.add("hidden");
}

function handleLogout() {
  localStorage.removeItem("freightiq_user");
  state.user = null;
  state.hasCalculatedPrice = false;
  updateAuthUI();
  showToast("Logged out successfully");
  renderApp();
}

// -------------------------------------------------------------
// 2. VALIDATION & LOGIN FORM SUBMISSION
// -------------------------------------------------------------

function setupAuthForms() {
  const tabEmail = document.getElementById("tabLoginEmail");
  const tabPhone = document.getElementById("tabLoginPhone");
  const formEmail = document.getElementById("formEmailSection");
  const formPhone = document.getElementById("formPhoneSection");

  tabEmail?.addEventListener("click", () => {
    tabEmail.classList.add("border-blue-600", "text-blue-600");
    tabEmail.classList.remove("border-transparent", "text-slate-500");
    tabPhone.classList.remove("border-blue-600", "text-blue-600");
    tabPhone.classList.add("border-transparent", "text-slate-500");
    formEmail.classList.remove("hidden");
    formPhone.classList.add("hidden");
  });

  tabPhone?.addEventListener("click", () => {
    tabPhone.classList.add("border-blue-600", "text-blue-600");
    tabPhone.classList.remove("border-transparent", "text-slate-500");
    tabEmail.classList.remove("border-blue-600", "text-blue-600");
    tabEmail.classList.add("border-transparent", "text-slate-500");
    formPhone.classList.remove("hidden");
    formEmail.classList.add("hidden");
  });

  // Demo Login Button
  document.getElementById("demoLoginBtn")?.addEventListener("click", () => {
    performLogin({
      id: "usr_sail_demo",
      name: "Capt. Rajesh Sharma",
      email: "r.sharma@sail.gov.in",
      phone: "+91 98401 23456",
      company: "Steel Authority of India Limited (SAIL)",
      role: "Chief Shipping & Logistics Officer"
    });
  });

  // Email form submit
  document.getElementById("submitEmailLogin")?.addEventListener("click", (e) => {
    e.preventDefault();
    const emailInput = document.getElementById("loginEmailInput")?.value.trim();
    const pwdInput = document.getElementById("loginEmailPwd")?.value;

    const emailRegex = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
    if (!emailInput || !emailRegex.test(emailInput)) {
      showLoginError("Please enter a valid corporate email address (e.g. name@sail.gov.in)");
      return;
    }
    if (!pwdInput || pwdInput.length < 4) {
      showLoginError("Password must be at least 4 characters.");
      return;
    }

    const cleanEmail = emailInput.toLowerCase();
    const namePart = cleanEmail.split("@")[0].replace(/[._]/g, " ");
    const formattedName = namePart.charAt(0).toUpperCase() + namePart.slice(1);

    performLogin({
      id: "usr_" + Date.now(),
      name: formattedName + " (Chartering)",
      email: cleanEmail,
      phone: "+91 98112 34567",
      company: "SAIL Logistics Division",
      role: "Logistics Manager"
    });
  });

  // Phone form submit
  document.getElementById("submitPhoneLogin")?.addEventListener("click", (e) => {
    e.preventDefault();
    const phoneInput = document.getElementById("loginPhoneInput")?.value.trim();
    const otpInput = document.getElementById("loginPhoneOtp")?.value.trim();

    const digitsOnly = phoneInput.replace(/\D/g, "");
    if (digitsOnly.length < 10) {
      showLoginError("Please enter a valid 10-digit mobile number.");
      return;
    }
    if (!otpInput || otpInput.length < 4) {
      showLoginError("Please enter the verification OTP.");
      return;
    }

    performLogin({
      id: "usr_" + Date.now(),
      name: "Chartering Specialist",
      email: "logistics." + digitsOnly.slice(-4) + "@sail.in",
      phone: "+91 " + digitsOnly.slice(-10),
      company: "Steel Authority of India Limited",
      role: "Chartering Specialist"
    });
  });
}

function showLoginError(msg) {
  const errEl = document.getElementById("loginErrorMsg");
  if (errEl) {
    errEl.textContent = msg;
    errEl.classList.remove("hidden");
  }
}

function performLogin(userData) {
  state.user = userData;
  localStorage.setItem("freightiq_user", JSON.stringify(userData));
  updateAuthUI();
  closeLoginModal();
  showToast(`Welcome, ${userData.name}!`);
  renderApp();
}

// -------------------------------------------------------------
// 3. MARITIME HERO SHIP ANIMATION
// -------------------------------------------------------------

function initMaritimeAnimation() {
  const canvas = document.getElementById("maritimeCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  function resize() {
    if (!canvas.parentElement) return;
    width = canvas.width = canvas.parentElement.clientWidth;
    height = canvas.height = canvas.parentElement.clientHeight;
  }

  let width = (canvas.width = canvas.parentElement.clientWidth || 1200);
  let height = (canvas.height = canvas.parentElement.clientHeight || 480);

  window.addEventListener("resize", resize);

  let step = 0;
  let shipX = -180;
  const shipSpeed = 0.95;

  // Floating wake bubble pool for realistic foaming displacement
  const wakeBubbles = Array.from({ length: 25 }, () => ({
    offsetX: -(Math.random() * 140 + 10),
    offsetY: (Math.random() - 0.5) * 22,
    radius: Math.random() * 3.5 + 1.5,
    alpha: Math.random() * 0.7 + 0.3
  }));

  function drawShip(x, y, scale = 1.18) {
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(scale, scale);

    // Subtle realistic pitching tilt as the vessel rides the swell
    const pitch = Math.sin(step * 1.6) * 0.032;
    ctx.rotate(pitch);

    // --- 1. Glowing Twin Wake Trails (Trailing Stern) ---
    const wakeGrad = ctx.createLinearGradient(0, 0, -220, 0);
    wakeGrad.addColorStop(0, "rgba(255, 255, 255, 0.92)");
    wakeGrad.addColorStop(0.2, "rgba(56, 189, 248, 0.75)");
    wakeGrad.addColorStop(0.6, "rgba(20, 184, 166, 0.4)");
    wakeGrad.addColorStop(1, "rgba(14, 165, 233, 0)");

    // Upper wake trail
    ctx.beginPath();
    ctx.moveTo(0, -6);
    ctx.quadraticCurveTo(-80, -18, -220, -32);
    ctx.lineWidth = 4.5;
    ctx.strokeStyle = wakeGrad;
    ctx.stroke();

    // Lower wake trail
    ctx.beginPath();
    ctx.moveTo(0, 4);
    ctx.quadraticCurveTo(-80, 14, -220, 24);
    ctx.lineWidth = 4.5;
    ctx.strokeStyle = wakeGrad;
    ctx.stroke();

    // Foaming turbulent water area between wakes
    ctx.fillStyle = "rgba(224, 242, 254, 0.3)";
    ctx.beginPath();
    ctx.moveTo(0, -5);
    ctx.lineTo(-140, -20);
    ctx.lineTo(-140, 16);
    ctx.closePath();
    ctx.fill();

    // Foaming bubbles trailing behind
    wakeBubbles.forEach((b) => {
      ctx.fillStyle = `rgba(255, 255, 255, ${b.alpha * 0.75})`;
      ctx.beginPath();
      ctx.arc(b.offsetX - (step * 8 % 40), b.offsetY, b.radius, 0, Math.PI * 2);
      ctx.fill();
    });

    // --- 2. Vessel Hull (Navy Slate with Depth & Waterline) ---
    ctx.shadowColor = "rgba(0, 0, 0, 0.6)";
    ctx.shadowBlur = 12;
    ctx.shadowOffsetY = 6;

    // Main Steel Hull
    ctx.fillStyle = "#0c1e36";
    ctx.beginPath();
    ctx.moveTo(0, 2);
    ctx.lineTo(105, 2);
    ctx.lineTo(124, -18);
    ctx.lineTo(24, -18);
    ctx.lineTo(3, -5);
    ctx.closePath();
    ctx.fill();
    ctx.shadowColor = "transparent";

    // Bright Safety Red Keel Line (Highly Visible!)
    ctx.fillStyle = "#ef4444";
    ctx.fillRect(4, -1, 102, 3.5);

    // Clean White Hull Accent Stripe
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(12, -7, 98, 1.8);

    // --- 3. Vibrant Cargo Container Stacks ---
    const containerColors = [
      ["#0284c7", "#38bdf8"], // Maritime Cyan
      ["#e11d48", "#f43f5e"], // Crimson Red
      ["#059669", "#10b981"], // Emerald Green
      ["#d97706", "#f59e0b"], // Vibrant Amber
      ["#2563eb", "#60a5fa"]  // Deep Royal Blue
    ];

    for (let i = 0; i < 4; i++) {
      const c = containerColors[i % containerColors.length];
      // Lower Container Box
      ctx.fillStyle = c[0];
      ctx.fillRect(28 + i * 15, -27, 13, 9);
      ctx.strokeStyle = "rgba(0, 0, 0, 0.35)";
      ctx.lineWidth = 1;
      ctx.strokeRect(28 + i * 15, -27, 13, 9);

      // Upper Container Box
      ctx.fillStyle = c[1];
      ctx.fillRect(30 + i * 15, -36, 11, 9);
      ctx.strokeRect(30 + i * 15, -36, 11, 9);
    }

    // --- 4. Superstructure Bridge (White with Illuminated Windows) ---
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(92, -45, 22, 27);
    ctx.fillStyle = "#e2e8f0";
    ctx.fillRect(90, -20, 26, 4);

    // Illuminated Navigation Windows (Glowing Cyan)
    ctx.fillStyle = "#38bdf8";
    ctx.shadowColor = "#0ea5e9";
    ctx.shadowBlur = 8;
    ctx.fillRect(95, -41, 17, 6);
    ctx.shadowColor = "transparent";

    // --- 5. Radar Mast & Rotating Antenna ---
    ctx.strokeStyle = "#cbd5e1";
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.moveTo(103, -45);
    ctx.lineTo(103, -58);
    ctx.stroke();

    // Rotating Radar Scanner
    const radarSpan = Math.cos(step * 4) * 8;
    ctx.lineWidth = 2.8;
    ctx.strokeStyle = "#ffffff";
    ctx.beginPath();
    ctx.moveTo(103 - radarSpan, -56);
    ctx.lineTo(103 + radarSpan, -56);
    ctx.stroke();

    // --- 6. Blinking Navigation Beacon Lights ---
    // Mast Top Amber/Red Light
    const mastPulse = (Math.sin(step * 6) + 1) / 2;
    ctx.fillStyle = `rgba(239, 68, 68, ${0.4 + mastPulse * 0.6})`;
    ctx.shadowColor = "#ef4444";
    ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.arc(103, -59, 3, 0, Math.PI * 2);
    ctx.fill();

    // Bow Starboard Green Navigation Light
    const bowPulse = (Math.sin(step * 5 + 1) + 1) / 2;
    ctx.fillStyle = `rgba(16, 185, 129, ${0.5 + bowPulse * 0.5})`;
    ctx.shadowColor = "#10b981";
    ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.arc(124, -18, 3, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowColor = "transparent";

    // --- 7. Dynamic Bow Cutting Spray ---
    ctx.strokeStyle = "rgba(255, 255, 255, 0.95)";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(124, -16);
    ctx.quadraticCurveTo(136, -11, 150, -6 + Math.sin(step * 3) * 3);
    ctx.stroke();

    ctx.restore();
  }

  function animate() {
    ctx.clearRect(0, 0, width, height);
    step += 0.024;

    // Water level positioned across the middle of the banner
    const waterY = Math.min(height * 0.46, height - 150);

    // Ocean Wave Layer 1 (Deep Maritime Flow)
    ctx.fillStyle = "rgba(14, 165, 233, 0.22)";
    ctx.beginPath();
    ctx.moveTo(0, height);
    for (let x = 0; x <= width; x += 12) {
      const y = waterY - 10 + Math.sin(x * 0.007 + step * 0.9) * 11;
      ctx.lineTo(x, y);
    }
    ctx.lineTo(width, height);
    ctx.closePath();
    ctx.fill();

    // Ocean Wave Layer 2 (Luminous Turquoise Swell)
    ctx.fillStyle = "rgba(20, 184, 166, 0.26)";
    ctx.beginPath();
    ctx.moveTo(0, height);
    for (let x = 0; x <= width; x += 10) {
      const y = waterY + Math.sin(x * 0.011 - step * 1.3) * 13;
      ctx.lineTo(x, y);
    }
    ctx.lineTo(width, height);
    ctx.closePath();
    ctx.fill();

    // Ship Sailing Motion Across Banner
    shipX += shipSpeed;
    if (shipX > width + 240) shipX = -200;
    const currentShipWaveY = waterY + Math.sin(shipX * 0.011 - step * 1.3) * 13;
    drawShip(shipX, currentShipWaveY, 1.18);

    // Ocean Wave Layer 3 (Foreground Wave with Foam Highlights)
    ctx.fillStyle = "rgba(6, 182, 212, 0.18)";
    ctx.beginPath();
    ctx.moveTo(0, height);
    for (let x = 0; x <= width; x += 10) {
      const y = waterY + 16 + Math.sin(x * 0.014 + step * 1.6) * 9;
      ctx.lineTo(x, y);
    }
    ctx.lineTo(width, height);
    ctx.closePath();
    ctx.fill();

    // Glowing Foam Crest Line on Water
    ctx.strokeStyle = "rgba(255, 255, 255, 0.45)";
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    for (let x = 0; x <= width; x += 15) {
      const y = waterY + 16 + Math.sin(x * 0.014 + step * 1.6) * 9;
      if (x === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    requestAnimationFrame(animate);
  }

  animate();
}

// -------------------------------------------------------------
// 4. EVENT LISTENERS & CHIP SELECTORS
// -------------------------------------------------------------

function initEventListeners() {
  setupAuthForms();

  // Modal close buttons
  document.getElementById("closeLoginModal")?.addEventListener("click", closeLoginModal);
  document.getElementById("loginModal")?.addEventListener("click", (e) => {
    if (e.target.id === "loginModal") closeLoginModal();
  });

  // Top-left sidebar drawer toggle
  const sidebarToggle = document.getElementById("sidebarToggleBtn");
  const sidebarDrawer = document.getElementById("sidebarDrawer");
  const closeSidebar = document.getElementById("closeSidebarBtn");
  const sidebarBackdrop = document.getElementById("sidebarBackdrop");

  sidebarToggle?.addEventListener("click", () => {
    sidebarDrawer?.classList.remove("closed");
    sidebarDrawer?.classList.add("open");
    sidebarBackdrop?.classList.remove("hidden");
  });

  const closeSidebarFunc = () => {
    sidebarDrawer?.classList.add("closed");
    sidebarDrawer?.classList.remove("open");
    sidebarBackdrop?.classList.add("hidden");
  };

  closeSidebar?.addEventListener("click", closeSidebarFunc);
  sidebarBackdrop?.addEventListener("click", closeSidebarFunc);

  // Sidebar Menu Navigation Items
  document.querySelectorAll(".sidebar-nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tab;
      if (target) {
        state.activeTab = target;
        closeSidebarFunc();
        renderApp();
      }
    });
  });

  // Search Guard: If not logged in, clicking *anywhere* triggers login
  const guardedZone = document.getElementById("authGuardedZone");
  guardedZone?.addEventListener("click", (e) => {
    if (!isLoggedIn()) {
      e.preventDefault();
      e.stopPropagation();
      openLoginModal();
    }
  });

  // Chips selection (Only Supramax, Panamax, Capesize, Handysize)
  document.querySelectorAll(".chip-btn").forEach((chip) => {
    chip.addEventListener("click", () => {
      if (!isLoggedIn()) {
        openLoginModal();
        return;
      }
      document.querySelectorAll(".chip-btn").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      const vtype = chip.dataset.vessel;
      if (vtype) {
        state.query.vesselType = vtype;
        const vesselSel = document.getElementById("vesselTypeSelect");
        if (vesselSel) vesselSel.value = vtype;
        handleFormChange();
      }
    });
  });

  // Form input change handlers
  document.getElementById("originSelect")?.addEventListener("change", handleFormChange);
  document.getElementById("destSelect")?.addEventListener("change", handleFormChange);
  document.getElementById("vesselTypeSelect")?.addEventListener("change", (e) => {
    const vtype = e.target.value;
    state.query.vesselType = vtype;
    document.querySelectorAll(".chip-btn").forEach((c) => {
      if (c.dataset.vessel === vtype) c.classList.add("active");
      else c.classList.remove("active");
    });
    handleFormChange();
  });

  // Check Infrastructure Constraints Button (Directs to Infrastructure Constraints comparison screen)
  document.getElementById("checkPriceBtn")?.addEventListener("click", (e) => {
    e.preventDefault();
    if (!isLoggedIn()) {
      openLoginModal();
      return;
    }
    state.hasCalculatedPrice = true;
    handleFormChange();
    state.activeTab = "infra-constraints";
    renderApp();
    window.scrollTo({ top: 0, behavior: "smooth" });
    recordModelHistoryEntry({
      action: "Infrastructure Constraints Analysis",
      category: "infrastructure",
      notes: `Compared LOA & Draft constraints for corridor: ${state.query.origin} \u2192 ${state.query.destination}.`
    });
    showToast("Navigating to Infrastructure Constraints & Port Capabilities Analysis.");
  });

  // Feedback Submission
  document.getElementById("submitFeedbackBtn")?.addEventListener("click", () => {
    const feedbackVal = document.getElementById("feedbackInput")?.value;
    if (feedbackVal) {
      showToast("Thank you! Your fixture rate observation has been submitted to the model.");
      document.getElementById("feedbackInput").value = "";
    }
  });
}

let formChangeTimeout = null;
function handleFormChange() {
  const originVal = document.getElementById("originSelect")?.value || "Indian East Coast Ports, India";
  const destVal = document.getElementById("destSelect")?.value || "Australia \u2014 Newcastle - Kooragang";
  const vesselVal = document.getElementById("vesselTypeSelect")?.value || state.query.vesselType || "Supramax";

  state.query.origin = originVal;
  state.query.destination = destVal;
  state.query.vesselType = vesselVal;

  // Update dynamic hero bold route label
  const dynamicOrigin = document.getElementById("heroOriginLabel");
  const dynamicDest = document.getElementById("heroDestLabel");
  if (dynamicOrigin) dynamicOrigin.textContent = originVal;
  if (dynamicDest) dynamicDest.textContent = destVal;

  if (state.hasCalculatedPrice) {
    recalculateAndRender();
    clearTimeout(formChangeTimeout);
    formChangeTimeout = setTimeout(() => {
      recordModelHistoryEntry({
        action: "Route Query Update",
        category: "valuation",
        notes: `Updated corridor query: ${originVal} \u2192 ${destVal} (${vesselVal}).`
      });
    }, 600);
  }
}

function recalculateAndRender() {
  renderResultsSection();
  if (state.activeTab === "infra-constraints") renderInfraConstraintsView();
  if (state.activeTab === "dual-forecast") renderDualForecastView();
  if (state.activeTab === "recommendations") renderRecommendationsView();
  if (state.activeTab === "idle-analysis") renderIdleAnalysisView();
  if (state.activeTab === "port-map") renderPortMapView();
  if (state.activeTab === "model-analysis") renderModelAnalysisView();
}

// -------------------------------------------------------------
// 5. APPLICATION VIEW RENDERING
// -------------------------------------------------------------

function renderApp() {
  document.querySelectorAll(".sidebar-nav-item").forEach((el) => {
    if (el.dataset.tab === state.activeTab) {
      el.classList.add("bg-blue-50", "text-blue-700", "font-semibold");
      el.classList.remove("text-slate-600");
    } else {
      el.classList.remove("bg-blue-50", "text-blue-700", "font-semibold");
      el.classList.add("text-slate-600");
    }
  });

  const heroSection = document.getElementById("heroSection");
  const searchBarSection = document.getElementById("searchBarSection");
  const resultsSection = document.getElementById("resultsDashboardSection");
  const dynamicViewContainer = document.getElementById("dynamicViewContainer");

  if (state.activeTab === "dashboard") {
    heroSection?.classList.remove("hidden");
    searchBarSection?.classList.remove("hidden");
    dynamicViewContainer?.classList.add("hidden");

    // "Without entering the details of which port and stuff to enter do not show the details of forecasting below etc."
    if (state.hasCalculatedPrice) {
      resultsSection?.classList.remove("hidden");
      renderResultsSection();
    } else {
      resultsSection?.classList.add("hidden");
    }
  } else {
    heroSection?.classList.add("hidden");
    searchBarSection?.classList.add("hidden");
    resultsSection?.classList.add("hidden");
    dynamicViewContainer?.classList.remove("hidden");

    if (state.activeTab === "infra-constraints") renderInfraConstraintsView();
    else if (state.activeTab === "dual-forecast") renderDualForecastView();
    else if (state.activeTab === "recommendations") renderRecommendationsView();
    else if (state.activeTab === "idle-analysis") renderIdleAnalysisView();
    else if (state.activeTab === "port-map") renderPortMapView();
    else if (state.activeTab === "model-analysis") renderModelAnalysisView();
  }
}

// -------------------------------------------------------------
// 6. DASHBOARD RESULTS RENDERING (FACTUAL BULK MARITIME PRICING)
// -------------------------------------------------------------

function getCalculatedMetrics() {
  const origin = state.query.origin;
  const dest = state.query.destination;
  const vessel = state.query.vesselType;

  // Realistic bulk freight rates ($/Ton) based on nautical distance & class
  let baseRate = 18.40;
  let typicalMin = 16.80;
  let typicalMax = 21.20;
  let distanceNm = 4250;
  let cargoDwt = 55000;

  if (vessel === "Capesize") {
    baseRate = 14.80;
    typicalMin = 13.20;
    typicalMax = 17.50;
    cargoDwt = 160000;
  } else if (vessel === "Panamax") {
    baseRate = 16.50;
    typicalMin = 15.00;
    typicalMax = 19.20;
    cargoDwt = 75000;
  } else if (vessel === "Handysize") {
    baseRate = 21.40;
    typicalMin = 19.50;
    typicalMax = 24.80;
    cargoDwt = 35000;
  }

  // Exact Route Adjustments matching user-specified terminals & countries
  const corridor = `${origin} ${dest}`;
  if (corridor.includes("Australia") || corridor.includes("Newcastle") || corridor.includes("Hay Point") || corridor.includes("Dalrymple") || corridor.includes("Abbot Point")) {
    distanceNm = 4850;
    baseRate = 18.40;
    typicalMin = 16.80;
    typicalMax = 21.20;
  } else if (corridor.includes("United States") || corridor.includes("Norfolk") || corridor.includes("Newport News") || corridor.includes("Baltimore")) {
    distanceNm = 11800;
    baseRate += 16.5;
    typicalMin += 14.5;
    typicalMax += 19.5;
  } else if (corridor.includes("Mozambique") || corridor.includes("Beira")) {
    distanceNm = 4150;
    baseRate += 1.2;
    typicalMin += 0.8;
    typicalMax += 1.8;
  } else if (corridor.includes("Russia") || corridor.includes("Nakhodka") || corridor.includes("Vostochny")) {
    distanceNm = 5400;
    baseRate += 5.2;
    typicalMin += 4.5;
    typicalMax += 6.5;
  } else if (corridor.includes("Indonesia") || corridor.includes("Taboneo") || corridor.includes("Banjarmasin")) {
    distanceNm = 2150;
    baseRate = Math.max(9.5, baseRate - 5.5);
    typicalMin = baseRate - 1.5;
    typicalMax = baseRate + 2.5;
  } else if (["Paradip", "Vizag", "Haldia", "Dhamra", "Gangavaram", "Gopalpur", "Sagar-Sandheads"].some((p) => corridor.includes(p))) {
    // Domestic Coastal route
    distanceNm = 450;
    baseRate = 8.20;
    typicalMin = 7.10;
    typicalMax = 9.80;
  }

  const expectedPriceStr = `$${baseRate.toFixed(2)}`;
  const typicalRangeStr = `$${typicalMin.toFixed(2)} \u2013 $${typicalMax.toFixed(2)} per ton`;
  const totalVoyageCost = Math.round(baseRate * cargoDwt);
  const totalVoyageCostStr = `Estimated Voyage Fixture: ~$${totalVoyageCost.toLocaleString()} per vessel (${cargoDwt.toLocaleString()} MT ${vessel})`;

  return {
    baseRate,
    typicalMin,
    typicalMax,
    cargoDwt,
    totalVoyageCost,
    expectedPriceStr,
    unit: "per ton",
    typicalRangeStr,
    totalVoyageCostStr,
    lastWeekDiff: "+$0.50",
    lastMonthDiff: "-$1.20",
    distanceNm
  };
}

function renderResultsSection() {
  const m = getCalculatedMetrics();

  // Summary Route Bar
  const summaryLane = document.getElementById("summaryLaneText");
  if (summaryLane) {
    summaryLane.innerHTML = `
      <span class="font-bold text-slate-900">${state.query.origin}</span>
      <span class="text-slate-400 mx-2">\u2192</span>
      <span class="font-bold text-slate-900">${state.query.destination}</span>
      <span class="text-slate-300 mx-2.5">|</span>
      <span class="text-blue-700 font-semibold">${state.query.vesselType} Bulk Carrier</span>
      <span class="text-slate-300 mx-2.5">|</span>
      <span class="text-slate-500 font-medium">${m.distanceNm.toLocaleString()} Nautical Miles</span>
    `;
  }

  // Pricing Card
  const priceVal = document.getElementById("cardExpectedPrice");
  const unitVal = document.getElementById("cardPriceUnit");
  const rangeVal = document.getElementById("cardTypicalRange");
  const voyageVal = document.getElementById("cardVoyageTotal");
  const weekDiff = document.getElementById("trendWeekDiff");
  const monthDiff = document.getElementById("trendMonthDiff");

  if (priceVal) priceVal.textContent = m.expectedPriceStr;
  if (unitVal) unitVal.textContent = m.unit;
  if (rangeVal) rangeVal.textContent = `Typical range: ${m.typicalRangeStr}`;
  if (voyageVal) voyageVal.textContent = m.totalVoyageCostStr;
  if (weekDiff) weekDiff.innerHTML = `<span class="text-red-500 font-semibold">\u2191 ${m.lastWeekDiff}</span>`;
  if (monthDiff) monthDiff.innerHTML = `<span class="text-emerald-600 font-semibold">\u2193 ${m.lastMonthDiff}</span>`;

  drawMarketTrendsChart();
}

function drawMarketTrendsChart() {
  const canvas = document.getElementById("marketTrendsCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  // High DPI (Retina) Canvas Rendering for Razor-Sharp Clarity
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const w = rect.width || canvas.parentElement?.clientWidth || 550;
  const h = 250;

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = `${w}px`;
  canvas.style.height = `${h}px`;

  ctx.resetTransform?.();
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);

  const padding = { top: 38, right: 35, bottom: 42, left: 62 };
  const graphW = w - padding.left - padding.right;
  const graphH = h - padding.top - padding.bottom;

  const labels = ["Sep 1", "Sep 7", "Sep 14", "Sep 21", "Sep 28", "Oct 5 (Today)", "Oct 12", "Oct 19", "Oct 26", "Nov 2", "Nov 9", "Nov 16"];
  const histPoints = [17.4, 17.8, 18.2, 17.9, 18.1, 18.4];
  const futurePoints = [18.4, 18.9, 19.5, 20.1, 20.8, 21.4];
  const lowerBounds = [18.4, 17.9, 18.2, 18.5, 18.9, 19.2];
  const upperBounds = [18.4, 19.8, 20.9, 22.1, 23.4, 24.5];

  const minY = 14;
  const maxY = 26;

  function toX(index) {
    return padding.left + (index / (labels.length - 1)) * graphW;
  }
  function toY(val) {
    return padding.top + graphH - ((val - minY) / (maxY - minY)) * graphH;
  }

  // Background Grid & Axis Lines
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(padding.left, padding.top, graphW, graphH);

  // Y-Axis Unit Header
  ctx.fillStyle = "#334155";
  ctx.font = "bold 11px Inter, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText("Rate ($ / Ton USD)", padding.left - 48, padding.top - 18);

  // Horizontal Grid Lines & Numbers
  for (let val = minY; val <= maxY; val += 2) {
    const y = toY(val);
    ctx.strokeStyle = val === 18 ? "#cbd5e1" : "#f1f5f9";
    ctx.lineWidth = val === 18 ? 1.5 : 1;
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(padding.left + graphW, y);
    ctx.stroke();

    ctx.fillStyle = "#64748b";
    ctx.font = "bold 10px 'JetBrains Mono', monospace";
    ctx.textAlign = "right";
    ctx.fillText(`$${val.toFixed(2)}`, padding.left - 8, y + 3.5);
  }

  // Vertical Month Divider Lines
  [0, 4, 8, 11].forEach((idx) => {
    const x = toX(idx);
    ctx.strokeStyle = "#e2e8f0";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, padding.top);
    ctx.lineTo(x, padding.top + graphH);
    ctx.stroke();
  });

  // Asymmetric Regret Risk Shaded Band
  const regretGrad = ctx.createLinearGradient(0, toY(25), 0, toY(17));
  regretGrad.addColorStop(0, "rgba(239, 68, 68, 0.22)");
  regretGrad.addColorStop(0.5, "rgba(239, 68, 68, 0.10)");
  regretGrad.addColorStop(1, "rgba(239, 68, 68, 0.02)");

  ctx.fillStyle = regretGrad;
  ctx.beginPath();
  ctx.moveTo(toX(5), toY(upperBounds[0]));
  for (let i = 0; i < upperBounds.length; i++) ctx.lineTo(toX(5 + i), toY(upperBounds[i]));
  for (let i = lowerBounds.length - 1; i >= 0; i--) ctx.lineTo(toX(5 + i), toY(lowerBounds[i]));
  ctx.closePath();
  ctx.fill();

  // Outer dashed boundary lines for regret band
  ctx.strokeStyle = "rgba(239, 68, 68, 0.55)";
  ctx.lineWidth = 1.4;
  ctx.setLineDash([3, 3]);
  ctx.beginPath();
  for (let i = 0; i < upperBounds.length; i++) {
    if (i === 0) ctx.moveTo(toX(5 + i), toY(upperBounds[i]));
    else ctx.lineTo(toX(5 + i), toY(upperBounds[i]));
  }
  ctx.stroke();
  ctx.beginPath();
  for (let i = 0; i < lowerBounds.length; i++) {
    if (i === 0) ctx.moveTo(toX(5 + i), toY(lowerBounds[i]));
    else ctx.lineTo(toX(5 + i), toY(lowerBounds[i]));
  }
  ctx.stroke();
  ctx.setLineDash([]);

  // Historical Fixtures Trend Line
  ctx.strokeStyle = "#2563eb";
  ctx.lineWidth = 3;
  ctx.beginPath();
  for (let i = 0; i < histPoints.length; i++) {
    const x = toX(i);
    const y = toY(histPoints[i]);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // Historical Data Dots
  for (let i = 0; i < histPoints.length; i++) {
    const x = toX(i);
    const y = toY(histPoints[i]);
    ctx.fillStyle = "#ffffff";
    ctx.strokeStyle = "#2563eb";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }

  // Forward Forecast Trend Line
  ctx.strokeStyle = "#e11d48";
  ctx.lineWidth = 3;
  ctx.setLineDash([6, 4]);
  ctx.beginPath();
  for (let i = 0; i < futurePoints.length; i++) {
    const x = toX(5 + i);
    const y = toY(futurePoints[i]);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.setLineDash([]);

  // Forecast Data Dots
  for (let i = 1; i < futurePoints.length; i++) {
    const x = toX(5 + i);
    const y = toY(futurePoints[i]);
    ctx.fillStyle = "#ffffff";
    ctx.strokeStyle = "#e11d48";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }

  // "Today" Demarcation Marker & Badge
  const todayX = toX(5);
  ctx.strokeStyle = "#059669";
  ctx.lineWidth = 2;
  ctx.setLineDash([3, 3]);
  ctx.beginPath();
  ctx.moveTo(todayX, padding.top);
  ctx.lineTo(todayX, padding.top + graphH);
  ctx.stroke();
  ctx.setLineDash([]);

  // Today Badge Pill
  ctx.fillStyle = "#059669";
  ctx.beginPath();
  ctx.roundRect(todayX - 28, padding.top - 18, 56, 17, 4);
  ctx.fill();
  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 9px Inter, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("\u25cf TODAY", todayX, padding.top - 6);

  // Callout Pill on Today ($18.40)
  const todayY = toY(histPoints[5]);
  ctx.fillStyle = "#0f172a";
  ctx.beginPath();
  ctx.roundRect(todayX - 25, todayY - 26, 50, 18, 5);
  ctx.fill();
  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 10px 'JetBrains Mono', monospace";
  ctx.textAlign = "center";
  ctx.fillText("$18.40", todayX, todayY - 14);

  // Callout Pill on Forecast End ($21.40)
  const endX = toX(11);
  const endY = toY(futurePoints[5]);
  ctx.fillStyle = "#e11d48";
  ctx.beginPath();
  ctx.roundRect(endX - 44, endY - 24, 48, 18, 5);
  ctx.fill();
  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 10px 'JetBrains Mono', monospace";
  ctx.textAlign = "center";
  ctx.fillText("$21.40", endX - 20, endY - 12);

  // Callout Pill on Upper Regret Bound ($24.50)
  const upperY = toY(upperBounds[5]);
  ctx.fillStyle = "#991b1b";
  ctx.beginPath();
  ctx.roundRect(endX - 44, upperY - 12, 48, 18, 5);
  ctx.fill();
  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 10px 'JetBrains Mono', monospace";
  ctx.textAlign = "center";
  ctx.fillText("$24.50", endX - 20, upperY);

  // X-Axis Date Labels
  ctx.fillStyle = "#64748b";
  ctx.font = "bold 10px Inter, sans-serif";
  ctx.textAlign = "center";
  for (let i = 0; i < labels.length; i++) {
    if (i % 2 === 0 || i === 5 || i === 11) {
      const isToday = i === 5;
      ctx.fillStyle = isToday ? "#059669" : "#64748b";
      ctx.fillText(labels[i].replace(" (Today)", ""), toX(i), padding.top + graphH + 18);
    }
  }

  // Interactive Top Legend
  const legX = padding.left + graphW - 270;
  const legY = padding.top - 18;

  ctx.fillStyle = "#2563eb";
  ctx.fillRect(legX, legY, 12, 6);
  ctx.fillStyle = "#334155";
  ctx.font = "10px Inter, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText("Historical", legX + 16, legY + 6);

  ctx.strokeStyle = "#e11d48";
  ctx.lineWidth = 2;
  ctx.setLineDash([3, 2]);
  ctx.beginPath();
  ctx.moveTo(legX + 75, legY + 3);
  ctx.lineTo(legX + 90, legY + 3);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = "#334155";
  ctx.fillText("AI Forecast", legX + 94, legY + 6);

  ctx.fillStyle = "rgba(239, 68, 68, 0.3)";
  ctx.fillRect(legX + 160, legY, 12, 6);
  ctx.fillStyle = "#334155";
  ctx.fillText("95% Regret Bound", legX + 176, legY + 6);
}

// -------------------------------------------------------------
// 7. SIDEBAR TAB 1: CONGESTION & HISTORICAL FORECASTING
// -------------------------------------------------------------

// -------------------------------------------------------------
// 7. SIDEBAR TAB 1: CONGESTION & HISTORICAL FORECASTING
// -------------------------------------------------------------

// The corridor dropdown drives the chart and the two model cards. Changing it does
// not re-render the whole view: the chart is redrawn in place from the new response.
window.selectForecastCorridor = function(corridorKey) {
  if (window.FreightIQApi && window.FreightIQApi.selectCorridor) {
    window.FreightIQApi.selectCorridor(corridorKey);
  }
};

function renderDualForecastView() {
  const container = document.getElementById("dynamicViewContainer");
  if (!container) return;

  const m = getCalculatedMetrics();

  container.innerHTML = `
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      <div class="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <span class="text-xs font-semibold text-blue-700 uppercase tracking-wider bg-blue-50 px-2.5 py-1 rounded-md border border-blue-200">
            Corridor Telemetry &amp; Model Forecast
          </span>
          <h2 class="text-2xl font-bold text-slate-900 mt-2 font-outfit">
            Observed Freight Rates with Model Forecast
          </h2>
          <p class="text-xs text-slate-500 mt-1">
            Each point is a recorded weekly rate. The forecast is the deployed model's
            14-day projection with its conformal interval, alongside Model 1's current
            line-up snapshot for the discharge port.
          </p>
        </div>
        <button onclick="state.activeTab='dashboard'; renderApp();" class="text-xs bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium px-3.5 py-2 rounded-lg transition-colors shadow-sm flex items-center gap-1.5 self-start md:self-auto">
          \u2190 Back to Route Query
        </button>
      </div>

      <!-- CORRIDOR SELECTOR BAR -->
      <div class="card-elevation p-4 bg-white rounded-2xl border border-slate-200 mb-6 shadow-xs">
        <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <p class="text-xs text-slate-500">
              The chart below is drawn from the model's own weekly observations and its
              forecast interval. Corridors listed here are the only ones with recorded rates.
            </p>
          </div>
          <select id="forecastCorridorSelect" onchange="window.selectForecastCorridor(this.value)"
            class="bg-slate-50 border border-slate-300 text-slate-900 text-xs font-bold rounded-xl p-2.5 focus:ring-2 focus:ring-blue-500 focus:bg-white cursor-pointer transition-colors shadow-2xs">
            <option value="">Loading corridors&hellip;</option>
          </select>
        </div>
        <p id="forecastCorridorNote" class="text-[11px] text-slate-500 mt-2 leading-relaxed">&nbsp;</p>
      </div>

      <!-- Model output cards, filled from /api/corridor-series -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <div class="card-elevation p-4 border-l-4 border-sky-600">
          <div class="text-xs text-slate-500 font-medium">Discharge Port &mdash; Model 1 snapshot</div>
          <div id="kpiCongestionValue" class="text-2xl font-bold text-slate-900 mt-1 font-outfit">
            <span class="text-slate-400 text-base">Loading&hellip;</span>
          </div>
          <div id="kpiCongestionNote" class="text-xs font-semibold mt-1 text-slate-500">
            &nbsp;
          </div>
        </div>

        <div class="card-elevation p-4 border-l-4 border-indigo-600">
          <div class="text-xs text-slate-500 font-medium">Model 2 &mdash; rate forecast</div>
          <div id="kpiRateValue" class="text-2xl font-bold text-slate-900 mt-1 font-outfit">
            <span class="text-slate-400 text-base">Loading&hellip;</span>
          </div>
          <div id="kpiRateNote" class="text-xs font-semibold mt-1 text-slate-500">
            &nbsp;
          </div>
        </div>
      </div>

      <!-- MAIN CHART & BACKTEST PANEL -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div class="lg:col-span-2 card-elevation p-6 bg-white rounded-2xl border border-slate-200">
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 pb-3 border-b border-slate-100">
            <div>
              <h3 class="font-bold text-slate-900 font-outfit text-base" id="chartTitle">
                Observed Rate History and Model Forecast
              </h3>
              <p class="text-xs text-slate-500" id="chartSubtitle">
                Weekly observed rates with the model's forecast and its 80% interval.
              </p>
            </div>
            <span class="text-[11px] font-bold text-slate-600 bg-slate-100 px-2.5 py-1 rounded-full shrink-0">
              GET /api/corridor-series
            </span>
          </div>
          <div class="relative w-full h-[300px]">
            <canvas id="dualForecastCanvas" class="w-full h-full"></canvas>
          </div>
          <p id="chartFootnote" class="text-[11px] text-slate-500 mt-3 leading-relaxed">&nbsp;</p>
        </div>

        <div class="card-elevation p-6 bg-white rounded-2xl border border-slate-200 flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <h3 class="font-bold text-slate-900 font-outfit text-base">Model Evaluation</h3>
              <span id="telemetryBadge" class="bg-slate-100 text-slate-500 text-[10px] font-bold px-2 py-0.5 rounded uppercase">Loading</span>
            </div>
            <p class="text-xs text-slate-500 mb-4">
              Served live from <span class="font-mono text-[11px]">GET /api/model-report</span>.
              Every figure below is produced by the walk-forward validation, not hard-coded.
            </p>
            <div id="telemetryBody" class="space-y-3 text-xs">
              <div class="text-slate-400 py-2">Contacting the model API&hellip;</div>
            </div>
          </div>

          <div class="mt-6 pt-3 border-t border-slate-100 bg-slate-50 p-3 rounded-xl border border-slate-200/80">
            <div class="text-[11px] font-bold text-slate-700 mb-1">What this chart does not show</div>
            <div class="text-[11px] text-slate-600 leading-relaxed">
              No congestion trend is drawn. Model 1 reads a single line-up snapshot per
              port and the dataset holds no congestion history, so any congestion curve
              here would be invented. The current snapshot is reported in the card
              above instead.
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  setTimeout(drawDualForecastCanvas, 50);
  // Populate the live Model Evaluation panel once this view is in the DOM.
  setTimeout(function () {
    if (window.FreightIQApi && window.FreightIQApi.renderTelemetry) {
      window.FreightIQApi.renderTelemetry();
    }
  }, 60);
  // Draw the chart from the model, not from a curve written into this file.
  if (window.FreightIQApi && window.FreightIQApi.renderCorridorChart) {
    window.FreightIQApi.renderCorridorChart();
  }
}

// The chart itself lives in api-status.js, because it is drawn from
// GET /api/corridor-series rather than from data held in this file.
//
// What used to be here drew a 302-line synthetic chart: a hard-coded base rate of
// $18.40, a four-point "history" spaced evenly around it, a five-point "forecast"
// produced by the formula baseRate + (congestion - 45) * 0.22, "regret bounds"
// computed as point +/- 0.6 with an arbitrary per-step widening, and an eight-point
// congestion trajectory derived by multiplying the port's score by hand-picked
// factors (0.52, 0.70, 0.85, ...). None of it came from a model.
//
// The replacement plots three real things and nothing else:
//   - the weekly rates the corridor actually recorded, unmodified
//   - the deployed model's 14-day point forecast
//   - that forecast's conformal interval
// There is no congestion line, because Model 1 reads a single line-up snapshot per
// port and the dataset holds no congestion history to plot.
function drawDualForecastCanvas() {
  if (window.FreightIQApi && window.FreightIQApi.drawSeriesChart) {
    window.FreightIQApi.drawSeriesChart();
  }
}

// -------------------------------------------------------------
// 8. SIDEBAR TAB 2: UNIFIED RECOMMENDATION SYSTEM
// -------------------------------------------------------------

function renderRecommendationsView() {
  const container = document.getElementById("dynamicViewContainer");
  if (!container) return;

  const m = getCalculatedMetrics();

  container.innerHTML = `
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      <div class="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <span class="text-xs font-semibold text-emerald-700 uppercase tracking-wider bg-emerald-50 px-2.5 py-1 rounded-md border border-emerald-200">
            Actionable Intelligence Engine
          </span>
          <h2 class="text-2xl font-bold text-slate-900 mt-2 font-outfit">
            Unified Recommendation System
          </h2>
        </div>
        <button onclick="state.activeTab='dashboard'; renderApp();" class="text-xs bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium px-3.5 py-2 rounded-lg transition-colors shadow-sm flex items-center gap-1.5">
          \u2190 Back to Route Query
        </button>
      </div>

      <!-- ONE BEST CHOICE UNIFIED RECOMMENDATION CARD -->
      <div class="card-elevation p-6 sm:p-7 bg-white border-t-4 border-emerald-600 rounded-2xl mb-8 shadow-md">
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-100">
          <div>
            <div class="flex items-center gap-2 mb-1">
              <span class="text-[11px] font-extrabold uppercase tracking-wider text-emerald-800 bg-emerald-100/80 px-2.5 py-0.5 rounded-full border border-emerald-300">
                Single Synthesized Recommendation \u00b7 Optimal Choice
              </span>
              <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
            </div>
            <h3 id="recoHeadline" class="text-xl sm:text-2xl font-extrabold text-slate-900 font-outfit mt-1">
              Connecting to the recommendation engine&hellip;
            </h3>
            <p id="recoNarrative" class="text-[12px] sm:text-xs text-slate-600 mt-1.5 leading-relaxed max-w-2xl">
              &nbsp;
            </p>
            <p class="text-xs text-slate-500 mt-1">
              Your route query: <strong class="text-slate-800">${state.query.origin}</strong> \u2192 <strong class="text-slate-800">${state.query.destination}</strong> (${m.distanceNm.toLocaleString()} NM)
            </p>

            <!--
              The panels below are driven by the trained models, which can only price
              corridors that have observed weekly rate history. That set does not match
              the port lists in the route form above, so the corridor under evaluation is
              chosen here, from the real corridor list, rather than silently mapped.
            -->
            <div id="modelCorridorPicker" class="mt-3">
              <select id="modelCorridorSelect"
                class="text-xs font-semibold text-slate-800 bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 max-w-full">
                <option value="">Loading corridor list&hellip;</option>
              </select>
              <p id="modelCorridorNote" class="text-[10px] text-slate-500 mt-1.5 leading-relaxed">
                &nbsp;
              </p>
            </div>
          </div>
          <!-- Space for Live Weather API Integration -->
          <div id="weatherApiSpace" class="p-3.5 bg-sky-50/70 border border-sky-200 rounded-xl shrink-0 min-w-[280px] md:max-w-sm">
            <div class="flex items-center justify-between pb-1.5 border-b border-sky-200/60 mb-2">
              <div class="flex items-center gap-1.5 text-xs font-bold text-sky-900">
                <svg class="w-4 h-4 text-sky-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 00-9.78 2.096A4.001 4.001 0 003 15z"/></svg>
                <span>Weather API Integration</span>
              </div>
              <span id="weatherLiveBadge" class="text-[10px] font-semibold text-sky-700 bg-sky-100 px-2 py-0.5 rounded-full border border-sky-200 flex items-center gap-1">
                <span class="w-1.5 h-1.5 rounded-full bg-slate-400"></span> Offline
              </span>
            </div>
            <div id="recoWeather" class="text-[11px] text-slate-600 space-y-1">
              <div class="text-slate-400">No observation yet.</div>
            </div>
          </div>
        </div>

        <!-- 3-Pillar Synthesized Rationale Grid (Simplified Language & Image 2 Rationales Removed) -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 pt-5">
          
          <!-- Column 1: Optimal Market Entry (Congestion Score & Freight Rate) -->
          <div class="bg-slate-50 p-4 sm:p-5 rounded-xl border border-slate-200/80 flex flex-col justify-between">
            <div>
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs font-bold uppercase tracking-wider text-blue-700">1. Optimal Market Entry</span>
                <span id="marketEntryBadge" class="text-[11px] font-bold bg-blue-100 text-blue-800 px-2 py-0.5 rounded">Connecting&hellip;</span>
              </div>
              <p id="marketEntryWhy" class="text-xs text-slate-700 leading-relaxed">&nbsp;</p>
              <div id="marketEntryRows" class="mt-3 text-xs space-y-2 text-slate-600">
                <div class="text-slate-400">Waiting for model output&hellip;</div>
              </div>
            </div>
          </div>

          <!-- Column 2: Vessel Optimizer (Physical Constraints of Ports) -->
          <div class="bg-slate-50 p-4 sm:p-5 rounded-xl border border-slate-200/80 flex flex-col justify-between">
            <div>
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs font-bold uppercase tracking-wider text-emerald-700">2. Vessel Optimizer</span>
                <span id="vesselBadge" class="text-[11px] font-bold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded">Connecting&hellip;</span>
              </div>
              <p id="vesselWhy" class="text-xs text-slate-700 leading-relaxed">&nbsp;</p>
              <div id="vesselRows" class="mt-3 text-xs space-y-2 text-slate-600">
                <div class="text-slate-400">Waiting for model output&hellip;</div>
              </div>
            </div>
          </div>

          <!-- Column 3: Risk Monitor (Berth Availability, Demand Volume & Weather API) -->
          <div class="bg-slate-50 p-4 sm:p-5 rounded-xl border border-slate-200/80 flex flex-col justify-between">
            <div>
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs font-bold uppercase tracking-wider text-amber-800">3. Risk Monitor</span>
                <span id="riskBadge" class="text-[11px] font-bold bg-amber-100 text-amber-800 px-2 py-0.5 rounded">Connecting&hellip;</span>
              </div>
              <p id="riskWhy" class="text-xs text-slate-700 leading-relaxed">&nbsp;</p>
              <div id="riskRows" class="mt-3 text-xs space-y-2 text-slate-600">
                <div class="text-slate-400">Waiting for model output&hellip;</div>
              </div>
            </div>
          </div>

        </div>
      </div>

      <!-- EXPLAINABILITY AI & THEORETICAL REASONING -->
      <div class="card-elevation p-6 sm:p-8 bg-white border border-slate-200 rounded-2xl">
        <div class="mb-5">
          <div class="flex items-center gap-2">
            <span class="text-[11px] font-extrabold uppercase tracking-wider text-purple-700 bg-purple-50 px-2.5 py-0.5 rounded-full border border-purple-200">
              Explainability AI
            </span>
          </div>
        </div>

        <!-- LIVE narrative, written only from model output -->
        <div id="explainLive" class="mb-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div class="text-xs text-slate-400">Composing the rationale&hellip;</div>
        </div>

        <!-- Subheadings with Points in Simpler Language -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
          
          <!-- Subheading 1: Port Congestion & Waiting Queues -->
          <div class="p-5 bg-white rounded-xl border border-slate-200 hover:border-slate-300 transition-colors shadow-2xs">
            <div class="flex items-center gap-2 mb-2">
              <span class="w-6 h-6 rounded-lg bg-rose-100 text-rose-700 flex items-center justify-center font-bold text-xs shrink-0">1</span>
              <h4 class="text-sm font-bold text-slate-900 font-outfit">Port Congestion & Waiting Line Dynamics</h4>
            </div>
            <p class="text-xs text-slate-600 leading-relaxed mb-3">
              When multiple bulk carriers arrive simultaneously, berth capacity gets bottlenecked. While waiting at anchor, a ship still incurs continuous daily operating expenses:
            </p>
            <ul class="text-xs text-slate-600 space-y-2 list-disc list-inside leading-relaxed">
              <li><strong>Demurrage Penalties:</strong> Delays at berths incur contract penalties, causing shipowners to raise their forward spot price quotes to cover lost time.</li>
              <li><strong>Turnaround Cascades:</strong> Heavy congestion today compounds into next week's schedule, directly increasing rate premiums on upcoming fixtures.</li>
            </ul>
          </div>

          <!-- Subheading 2: Vessel Compatibility & Physical Constraints -->
          <div class="p-5 bg-white rounded-xl border border-slate-200 hover:border-slate-300 transition-colors shadow-2xs">
            <div class="flex items-center gap-2 mb-2">
              <span class="w-6 h-6 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-xs shrink-0">2</span>
              <h4 class="text-sm font-bold text-slate-900 font-outfit">Vessel Compatibility & Physical Constraints</h4>
            </div>
            <p class="text-xs text-slate-600 leading-relaxed mb-3">
              Ports have strict structural boundaries that dictate which ships can enter safely without risking grounding or damage:
            </p>
            <ul class="text-xs text-slate-600 space-y-2 list-disc list-inside leading-relaxed">
              <li><strong>Draft & Length Limits:</strong> Oversized vessels cannot dock at shallower East Coast berths and must transfer cargo offshore, adding heavy lightering costs.</li>
              <li><strong>Gear Compatibility:</strong> Supramax vessels with onboard grab cranes can unload cargo independently without waiting for specialized shore-side equipment.</li>
            </ul>
          </div>

          <!-- Subheading 3: Currency & Fuel Dynamics -->
          <div class="p-5 bg-white rounded-xl border border-slate-200 hover:border-slate-300 transition-colors shadow-2xs">
            <div class="flex items-center gap-2 mb-2">
              <span class="w-6 h-6 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-xs shrink-0">3</span>
              <h4 class="text-sm font-bold text-slate-900 font-outfit">Currency Movements & Fuel Cost Realities</h4>
            </div>
            <p class="text-xs text-slate-600 leading-relaxed mb-3">
              International shipping trades across borders, creating constant interactions between foreign currencies and local logistics costs:
            </p>
            <ul class="text-xs text-slate-600 space-y-2 list-disc list-inside leading-relaxed">
              <li><strong>USD / INR Interaction:</strong> Ocean vessel charters and marine fuel (bunker oil) are billed globally in US Dollars, while port fees and inland trucking are paid in Indian Rupees.</li>
              <li><strong>Fuel Price Exposure:</strong> Changes in bunker fuel prices directly influence overall voyage expenditure, requiring dynamic hedging.</li>
            </ul>
          </div>

          <!-- Subheading 4: Weather & Safe Navigation Window -->
          <div class="p-5 bg-white rounded-xl border border-slate-200 hover:border-slate-300 transition-colors shadow-2xs">
            <div class="flex items-center gap-2 mb-2">
              <span class="w-6 h-6 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center font-bold text-xs shrink-0">4</span>
              <h4 class="text-sm font-bold text-slate-900 font-outfit">Weather Conditions & Navigation Safety</h4>
            </div>
            <p class="text-xs text-slate-600 leading-relaxed mb-3">
              Sea conditions directly affect voyage speed and whether port pilots can safely guide ships into dock:
            </p>
            <ul class="text-xs text-slate-600 space-y-2 list-disc list-inside leading-relaxed">
              <li><strong>Monsoon & Swell Impacts:</strong> High waves and gusty winds suspend pilot boarding and slow conveyor transfer speeds.</li>
              <li><strong>Arrival Buffers:</strong> Factoring weather forecasts allows charterers to agree on flexible 2\u20133 day arrival windows (laycans) to prevent costly dispute claims.</li>
            </ul>
          </div>

        </div>
      </div>

    </div>
  `;

  // The three pillars above used to contain numbers typed straight into this file
  // ("+8.4%", "~$2.80 saved per ton", "~4 Days in queue", "12.5m <= 14.5m"). They are
  // now placeholders. Ask the backend what the models actually say and fill them in.
  // If the backend is down the placeholders keep their "unavailable" wording - we
  // never fall back to a plausible-looking number.
  if (window.FreightIQApi && window.FreightIQApi.renderRecommendation) {
    window.FreightIQApi.renderRecommendation();
  }
}

// -------------------------------------------------------------
// 9. SIDEBAR TAB 3: IDLE SCENARIO ANALYSIS (INDIAN EAST COAST PORTS CONGESTION-BASED ALLOTMENT)
// -------------------------------------------------------------
// -------------------------------------------------------------

window.selectIdlePort = function(portId) {
  state.idleSelectedPort = portId;
  renderIdleAnalysisView();
};

window.allotTrucksToPort = function(portName, truckCount) {
  showToast(`Success! ${truckCount} empty trucks allotted to ${portName}. Dispatch orders and digital route guidance issued to drivers.`);
  recordModelHistoryEntry({
    action: "Truck Dispatch Allotment",
    category: "port",
    destination: portName,
    notes: `Allotted ${truckCount} empty trucks to ${portName} to mitigate forecasted cargo drop and prevent deadheading.`
  });
};

function renderIdleAnalysisView() {
  const container = document.getElementById("dynamicViewContainer");
  if (!container) return;

  // Selected East Coast Port (default to Vizag)
  const selectedPortId = state.idleSelectedPort || "vizag";
  const currentPort = state.portsIndia.find(p => p.id === selectedPortId) || state.portsIndia[0];

  // Specific neighboring allotments tailored to selected East Coast port
  let allotmentOptions = [];
  if (currentPort.id === "vizag") {
    allotmentOptions = [
      {
        name: "Gangavaram Port",
        state: "Andhra Pradesh",
        congestion: 44,
        distance: "25 km",
        traffic: "Low Congestion \u00b7 Fast Clearance",
        cargo: "Coke & Steel Plant Billets",
        slots: 25,
        pay: "\u20b92,800 \u2013 \u20b93,400 / day",
        color: "emerald"
      },
      {
        name: "Gopalpur Port",
        state: "Odisha",
        congestion: 30,
        distance: "210 km",
        traffic: "Lowest East Coast Congestion \u00b7 High Demand",
        cargo: "Imported Coal & Mineral Rakes",
        slots: 20,
        pay: "\u20b94,500 \u2013 \u20b95,400 / trip",
        color: "blue"
      },
      {
        name: "Dhamra Port",
        state: "Odisha",
        congestion: 38,
        distance: "480 km",
        traffic: "Rapid Rail-to-Conveyor Turnaround",
        cargo: "Thermal Coal & Pellets",
        slots: 20,
        pay: "\u20b95,800 \u2013 \u20b96,500 / trip",
        color: "indigo"
      }
    ];
  } else if (currentPort.id === "paradip") {
    allotmentOptions = [
      {
        name: "Dhamra Port",
        state: "Odisha",
        congestion: 38,
        distance: "98 km",
        traffic: "Low Congestion \u00b7 Rapid Mechanized Loading",
        cargo: "Iron Ore Pellets & Bulk Coal",
        slots: 40,
        pay: "\u20b93,800 \u2013 \u20b94,600 / trip",
        color: "emerald"
      },
      {
        name: "Gopalpur Port",
        state: "Odisha",
        congestion: 30,
        distance: "175 km",
        traffic: "Lowest Congestion \u00b7 Fast Berthing",
        cargo: "Heavy Industrial Minerals",
        slots: 35,
        pay: "\u20b94,200 \u2013 \u20b95,000 / trip",
        color: "blue"
      },
      {
        name: "Gangavaram Port",
        state: "Andhra Pradesh",
        congestion: 44,
        distance: "360 km",
        traffic: "Deepwater Capesize Dispatch",
        cargo: "Finished Steel & Coking Coal",
        slots: 30,
        pay: "\u20b95,200 \u2013 \u20b96,000 / trip",
        color: "indigo"
      }
    ];
  } else if (currentPort.id === "haldia") {
    allotmentOptions = [
      {
        name: "Dhamra Port",
        state: "Odisha",
        congestion: 38,
        distance: "195 km",
        traffic: "Deep Draft \u00b7 High Conveyor Loading",
        cargo: "Imported Thermal Coal",
        slots: 45,
        pay: "\u20b94,600 \u2013 \u20b95,500 / trip",
        color: "emerald"
      },
      {
        name: "Sagar-Sandheads",
        state: "West Bengal",
        congestion: 42,
        distance: "75 km",
        traffic: "Active Maritime Staging Gate",
        cargo: "Lighterage Cargo & Bagged Feedstock",
        slots: 30,
        pay: "\u20b93,200 \u2013 \u20b94,000 / trip",
        color: "blue"
      },
      {
        name: "Paradip Port",
        state: "Odisha",
        congestion: 68,
        distance: "320 km",
        traffic: "Bulk Coal Rakes Dispatch",
        cargo: "Mechanized Pellets",
        slots: 25,
        pay: "\u20b94,800 \u2013 \u20b95,800 / trip",
        color: "amber"
      }
    ];
  } else {
    // For other ports, recommend lowest congestion ports on East Coast
    const candidates = state.portsIndia
      .filter(p => p.id !== currentPort.id)
      .sort((a, b) => a.congestion - b.congestion)
      .slice(0, 3);
    
    allotmentOptions = candidates.map(p => ({
      name: p.name,
      state: p.state,
      congestion: p.congestion,
      distance: "120 \u2013 350 km",
      traffic: p.congestion < 50 ? "Low Congestion \u00b7 High Truck Need" : "Moderate Demand",
      cargo: "Bulk Minerals & Steel Coils",
      slots: 25,
      pay: "\u20b93,500 \u2013 \u20b94,800 / trip",
      color: "emerald"
    }));
  }

  const isCongested = currentPort.congestion >= 60;
  const totalIdleRisk = isCongested ? 105 : 20;

  container.innerHTML = `
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      
      <!-- Top Title & Navigation -->
      <div class="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div class="flex items-center gap-2">
            <span class="text-xs font-bold uppercase tracking-wider text-amber-700 bg-amber-50 px-2.5 py-0.5 rounded-full border border-amber-200">
              Indian Ports Operational Welfare
            </span>
          </div>
          <h2 class="text-2xl font-bold text-slate-900 font-outfit mt-1">
            Idle Scenario Analysis
          </h2>
        </div>
        <button onclick="state.activeTab='dashboard'; renderApp();" class="text-xs bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium px-3.5 py-2 rounded-lg transition-colors shadow-sm flex items-center gap-1.5 self-start md:self-auto">
          \u2190 Back to Route Query
        </button>
      </div>

      <!-- Plain Language Explanation Banner -->
      <div class="card-elevation p-5 bg-gradient-to-r from-amber-50 via-white to-sky-50 rounded-2xl border border-amber-200/80 mb-6">
        <div class="flex flex-col md:flex-row items-start md:items-center gap-4">
          <div class="w-12 h-12 rounded-xl bg-amber-500 text-white flex items-center justify-center font-bold text-2xl shrink-0 shadow-sm">
            \u1f69b
          </div>
          <div class="flex-1">
            <h3 class="text-base font-bold text-slate-900 font-outfit">
              Preventing Worker Losses & Empty Truck Deadheading at East Coast Ports
            </h3>
            <p class="text-xs text-slate-600 mt-1 leading-relaxed">
              When an Indian East Coast port has a <strong>high congestion score</strong>, ships face long berthing queues and cargo cannot be unloaded. 
              Local dock truck drivers arrive at the gates only to find loading halted. 
              <strong>Deadheading</strong> occurs when a driver has to drive back empty\u2014losing fuel and earning zero daily income. 
              By continuously evaluating each East Coast port's congestion score, FreightIQ detects loading drops days in advance and 
              <strong>allots empty trucks to neighboring low-congestion ports</strong> that have ready cargo and an acute truck shortage.
            </p>
          </div>
        </div>
      </div>

      <!-- Interactive East Coast Port Congestion Matrix (Selector) -->
      <div class="card-elevation p-5 bg-white rounded-2xl border border-slate-200 mb-8">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 pb-3 border-b border-slate-100">
          <div>
            <h3 class="text-sm font-bold text-slate-900 font-outfit">
              Indian East Coast Ports Congestion Scoreboard
            </h3>
            <p class="text-xs text-slate-500">
              Click any port to analyze its congestion score, idle driver risk, and optimal re-allotment routes
            </p>
          </div>
          <span class="text-[11px] font-semibold text-slate-500 bg-slate-100 px-2.5 py-1 rounded-full">
              7 East Coast Gateways Monitored
          </span>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
          ${state.portsIndia.map(p => {
            const isSelected = p.id === currentPort.id;
            let scoreBg = "bg-emerald-50 text-emerald-700 border-emerald-200";
            let dotColor = "bg-emerald-500";
            let statusLabel = "Fast Flow";
            if (p.congestion >= 65) {
              scoreBg = "bg-rose-50 text-rose-700 border-rose-200";
              dotColor = "bg-rose-500";
              statusLabel = "Congested";
            } else if (p.congestion >= 50) {
              scoreBg = "bg-amber-50 text-amber-700 border-amber-200";
              dotColor = "bg-amber-500";
              statusLabel = "Moderate";
            }

            return `
              <button onclick="selectIdlePort('${p.id}')" class="p-3 rounded-xl border text-left transition-all relative ${
                isSelected 
                  ? 'border-blue-600 ring-2 ring-blue-500/20 bg-blue-50/40 shadow-xs' 
                  : 'border-slate-200 bg-slate-50 hover:bg-white hover:border-slate-300'
              }">
                <div class="flex items-center justify-between mb-1.5">
                  <span class="text-[11px] font-bold text-slate-800 truncate">${p.name.split(' ')[0]}</span>
                  <span class="w-2 h-2 rounded-full ${dotColor}"></span>
                </div>
                <div class="text-lg font-bold font-mono ${p.congestion >= 65 ? 'text-rose-600' : p.congestion >= 50 ? 'text-amber-600' : 'text-emerald-600'}">
                  ${p.congestion}<span class="text-[10px] text-slate-400 font-sans font-normal">/100</span>
                </div>
                <div class="text-[10px] text-slate-500 mt-0.5 truncate">${p.state}</div>
                <div class="mt-2 text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border inline-block ${scoreBg}">
                  ${statusLabel}
                </div>
                ${isSelected ? '<div class="absolute -top-1.5 -right-1.5 bg-blue-600 text-white rounded-full w-4 h-4 flex items-center justify-center text-[9px] font-bold">\u2713</div>' : ''}
              </button>
            `;
          }).join('')}
        </div>
      </div>

      <!-- Selected Port Congestion & Idle Risk Diagnostic -->
      <div class="card-elevation p-6 bg-white rounded-2xl border border-slate-200 mb-8">
        <div class="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 pb-4 border-b border-slate-100">
          <div>
            <div class="flex items-center gap-2 mb-1">
              <span class="text-xs font-bold uppercase tracking-wider ${isCongested ? 'text-rose-700 bg-rose-50 border-rose-200' : 'text-emerald-700 bg-emerald-50 border-emerald-200'} px-2.5 py-0.5 rounded-full border">
                ${isCongested ? 'High Berth Congestion Detected' : 'Fluid Port Operations'}
              </span>
              <span class="text-xs text-slate-500">${currentPort.state}, India</span>
            </div>
            <h3 class="text-xl font-bold text-slate-900 font-outfit">
              ${currentPort.name} \u2014 Congestion Diagnostic & Idle Risk
            </h3>
            <p class="text-xs text-slate-500 mt-0.5">
              ${currentPort.description}
            </p>
          </div>
          <div class="flex items-center gap-3 shrink-0">
            <div class="text-center p-3 rounded-xl bg-slate-50 border border-slate-200 min-w-[100px]">
              <div class="text-[10px] uppercase font-bold text-slate-400">Congestion Score</div>
              <div class="text-2xl font-bold font-mono ${isCongested ? 'text-rose-600' : 'text-emerald-600'}">
                ${currentPort.congestion}<span class="text-xs font-normal text-slate-400">/100</span>
              </div>
            </div>
            <div class="text-center p-3 rounded-xl bg-slate-50 border border-slate-200 min-w-[100px]">
              <div class="text-[10px] uppercase font-bold text-slate-400">Anchorage Queue</div>
              <div class="text-2xl font-bold font-mono text-slate-800">
                ${currentPort.waiting} <span class="text-xs font-normal text-slate-500">ships</span>
              </div>
            </div>
            <div class="text-center p-3 rounded-xl ${isCongested ? 'bg-rose-50 border-rose-200 text-rose-800' : 'bg-emerald-50 border-emerald-200 text-emerald-800'} border min-w-[110px]">
              <div class="text-[10px] uppercase font-bold">Idle Truck Risk</div>
              <div class="text-2xl font-bold font-mono">
                ${isCongested ? '65 Trucks' : '0 (Low)'}
              </div>
            </div>
          </div>
        </div>

        <!-- 7-Day Forward Loading Outlook for Selected Port -->
        <div class="mt-6">
          <div class="flex items-center justify-between mb-3">
            <h4 class="text-xs font-bold uppercase tracking-wider text-slate-600 font-outfit">
              7-Day Cargo Discharge & Worker Employability Forecast
            </h4>
            <span class="text-xs text-slate-400">Next 7 Days Projected Trajectory</span>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-3">
            
            <!-- Day 1 -->
            <div class="p-3 bg-slate-50 rounded-xl border border-emerald-200 border-t-4 border-t-emerald-500 flex flex-col justify-between">
              <div>
                <div class="flex items-center justify-between text-xs mb-1">
                  <span class="font-bold text-slate-800">Day 1 (Today)</span>
                  <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
                </div>
                <div class="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded inline-block mb-1.5">
                  \u1f7e2 Normal Loading
                </div>
                <div class="text-[11px] text-slate-600 space-y-0.5">
                  <div>Cargo: <strong>12,400 MT</strong></div>
                  <div>Trucks: <strong>180 Active</strong></div>
                </div>
              </div>
              <div class="mt-2.5 pt-1.5 border-t border-slate-200 text-[10px] text-emerald-700 font-medium">
                \u2713 Full employment
              </div>
            </div>

            <!-- Day 2 -->
            <div class="p-3 bg-slate-50 rounded-xl border border-emerald-200 border-t-4 border-t-emerald-500 flex flex-col justify-between">
              <div>
                <div class="flex items-center justify-between text-xs mb-1">
                  <span class="font-bold text-slate-800">Day 2</span>
                  <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
                </div>
                <div class="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded inline-block mb-1.5">
                  \u1f7e2 Normal Loading
                </div>
                <div class="text-[11px] text-slate-600 space-y-0.5">
                  <div>Cargo: <strong>11,800 MT</strong></div>
                  <div>Trucks: <strong>170 Active</strong></div>
                </div>
              </div>
              <div class="mt-2.5 pt-1.5 border-t border-slate-200 text-[10px] text-emerald-700 font-medium">
                \u2713 Full employment
              </div>
            </div>

            <!-- Day 3: Disruption or Continuation -->
            ${isCongested ? `
              <div class="p-3 bg-rose-50/70 rounded-xl border border-rose-300 border-t-4 border-t-rose-500 flex flex-col justify-between shadow-xs">
                <div>
                  <div class="flex items-center justify-between text-xs mb-1">
                    <span class="font-bold text-rose-900">Day 3 (Drop Alert)</span>
                    <span class="w-2 h-2 rounded-full bg-rose-500 animate-ping"></span>
                  </div>
                  <div class="text-[10px] font-extrabold text-rose-800 bg-rose-100 px-1.5 py-0.5 rounded inline-block mb-1.5">
                    \u26a0\ufe0f -52% Cargo Drop
                  </div>
                  <div class="text-[11px] text-slate-700 space-y-0.5">
                    <div>Cargo: <strong class="text-rose-600">5,800 MT only</strong></div>
                    <div>Berth queue backlog</div>
                    <div class="text-rose-700 font-bold">65 Trucks Idle Risk</div>
                  </div>
                </div>
                <div class="mt-2.5 pt-1.5 border-t border-rose-200 text-[10px] text-rose-800 font-bold">
                  \u1f6a8 Re-allotment needed
                </div>
              </div>
            ` : `
              <div class="p-3 bg-slate-50 rounded-xl border border-emerald-200 border-t-4 border-t-emerald-500 flex flex-col justify-between">
                <div>
                  <div class="flex items-center justify-between text-xs mb-1">
                    <span class="font-bold text-slate-800">Day 3</span>
                    <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
                  </div>
                  <div class="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded inline-block mb-1.5">
                    \u1f7e2 Normal Flow
                  </div>
                  <div class="text-[11px] text-slate-600 space-y-0.5">
                    <div>Cargo: <strong>14,100 MT</strong></div>
                    <div>Trucks: <strong>185 Active</strong></div>
                  </div>
                </div>
                <div class="mt-2.5 pt-1.5 border-t border-slate-200 text-[10px] text-emerald-700 font-medium">
                  \u2713 High Demand
                </div>
              </div>
            `}

            <!-- Day 4 -->
            ${isCongested ? `
              <div class="p-3 bg-amber-50/70 rounded-xl border border-amber-300 border-t-4 border-t-amber-500 flex flex-col justify-between">
                <div>
                  <div class="flex items-center justify-between text-xs mb-1">
                    <span class="font-bold text-amber-900">Day 4 (Low Volume)</span>
                    <span class="w-2 h-2 rounded-full bg-amber-500"></span>
                  </div>
                  <div class="text-[10px] font-extrabold text-amber-800 bg-amber-100 px-1.5 py-0.5 rounded inline-block mb-1.5">
                    \u26a0\ufe0f -35% Loading
                  </div>
                  <div class="text-[11px] text-slate-700 space-y-0.5">
                    <div>Cargo: <strong class="text-amber-700">7,900 MT</strong></div>
                    <div>Delayed discharge</div>
                    <div class="text-amber-800 font-bold">40 Trucks Idle Risk</div>
                  </div>
                </div>
                <div class="mt-2.5 pt-1.5 border-t border-amber-200 text-[10px] text-amber-800 font-bold">
                  \u26a0\ufe0f Re-allotment needed
                </div>
              </div>
            ` : `
              <div class="p-3 bg-slate-50 rounded-xl border border-emerald-200 border-t-4 border-t-emerald-500 flex flex-col justify-between">
                <div>
                  <div class="flex items-center justify-between text-xs mb-1">
                    <span class="font-bold text-slate-800">Day 4</span>
                    <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
                  </div>
                  <div class="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded inline-block mb-1.5">
                    \u1f7e2 Normal Flow
                  </div>
                  <div class="text-[11px] text-slate-600 space-y-0.5">
                    <div>Cargo: <strong>13,500 MT</strong></div>
                    <div>Trucks: <strong>180 Active</strong></div>
                  </div>
                </div>
                <div class="mt-2.5 pt-1.5 border-t border-slate-200 text-[10px] text-emerald-700 font-medium">
                  \u2713 High Demand
                </div>
              </div>
            `}

            <!-- Day 5 -->
            <div class="p-3 bg-slate-50 rounded-xl border border-emerald-200 border-t-4 border-t-emerald-500 flex flex-col justify-between">
              <div>
                <div class="flex items-center justify-between text-xs mb-1">
                  <span class="font-bold text-slate-800">Day 5</span>
                  <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
                </div>
                <div class="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded inline-block mb-1.5">
                  \u1f7e2 Volume Normalized
                </div>
                <div class="text-[11px] text-slate-600 space-y-0.5">
                  <div>Cargo: <strong>13,200 MT</strong></div>
                  <div>Trucks: <strong>190 Active</strong></div>
                </div>
              </div>
              <div class="mt-2.5 pt-1.5 border-t border-slate-200 text-[10px] text-emerald-700 font-medium">
                \u2713 Full employment
              </div>
            </div>

            <!-- Day 6 -->
            <div class="p-3 bg-slate-50 rounded-xl border border-emerald-200 border-t-4 border-t-emerald-500 flex flex-col justify-between">
              <div>
                <div class="flex items-center justify-between text-xs mb-1">
                  <span class="font-bold text-slate-800">Day 6</span>
                  <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
                </div>
                <div class="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded inline-block mb-1.5">
                  \u1f7e2 Normal Loading
                </div>
                <div class="text-[11px] text-slate-600 space-y-0.5">
                  <div>Cargo: <strong>12,000 MT</strong></div>
                  <div>Trucks: <strong>175 Active</strong></div>
                </div>
              </div>
              <div class="mt-2.5 pt-1.5 border-t border-slate-200 text-[10px] text-emerald-700 font-medium">
                \u2713 Full employment
              </div>
            </div>

            <!-- Day 7 -->
            <div class="p-3 bg-slate-50 rounded-xl border border-emerald-200 border-t-4 border-t-emerald-500 flex flex-col justify-between">
              <div>
                <div class="flex items-center justify-between text-xs mb-1">
                  <span class="font-bold text-slate-800">Day 7</span>
                  <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
                </div>
                <div class="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded inline-block mb-1.5">
                  \u1f7e2 Normal Loading
                </div>
                <div class="text-[11px] text-slate-600 space-y-0.5">
                  <div>Cargo: <strong>12,600 MT</strong></div>
                  <div>Trucks: <strong>180 Active</strong></div>
                </div>
              </div>
              <div class="mt-2.5 pt-1.5 border-t border-slate-200 text-[10px] text-emerald-700 font-medium">
                \u2713 Full employment
              </div>
            </div>

          </div>
        </div>
      </div>

      <!-- Actionable Employability: Congestion Score-Based Alternative Port Allotment -->
      <div class="card-elevation p-6 sm:p-7 bg-white rounded-2xl mb-8 border border-slate-200">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-100 mb-6">
          <div>
            <div class="flex items-center gap-2 mb-1">
              <span class="text-xs font-bold uppercase tracking-wider text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded-full border border-blue-200">
                Actionable Employability Re-Allotment
              </span>
              <span class="text-xs text-slate-500">Targeting Lower Congestion Ports on East Coast</span>
            </div>
            <h3 class="text-xl font-bold text-slate-900 font-outfit">
              Allot Busy / Low-Congestion Traffic Ports for Empty Trucks & Drivers
            </h3>
            <p class="text-xs text-slate-500 mt-0.5">
              Based on East Coast congestion scores, these nearby ports have active berths, low waiting queues, and ready cargo waiting to be moved. Reroute empty trucks here to eliminate deadheading.
            </p>
          </div>
          <div class="flex items-center gap-2 text-xs font-semibold text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-xl border border-emerald-200 shrink-0">
            <span>\u2713 ${totalIdleRisk} Empty Trucks Can Be Reassigned Today</span>
          </div>
        </div>

        <!-- Port Allotment Cards Grid -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
          ${allotmentOptions.map((opt, idx) => `
            <div class="p-5 rounded-xl bg-slate-50 border border-slate-200 hover:border-blue-400 transition-all flex flex-col justify-between shadow-xs hover:shadow-md">
              <div>
                <div class="flex items-center justify-between mb-3">
                  <span class="text-xs font-extrabold uppercase text-blue-700 bg-blue-100 px-2 py-0.5 rounded">Allotment Route ${idx + 1}</span>
                  <span class="text-xs font-bold text-emerald-700 font-mono">${opt.distance} away</span>
                </div>
                <h4 class="text-lg font-bold text-slate-900 font-outfit">${opt.name}</h4>
                <p class="text-xs text-slate-500 mt-0.5">${opt.state}, India</p>
                
                <div class="mt-4 p-3 bg-white rounded-lg border border-slate-200 text-xs space-y-2">
                  <div class="flex justify-between items-center">
                    <span class="text-slate-500">Congestion Score:</span>
                    <span class="font-mono font-bold ${opt.congestion < 50 ? 'text-emerald-700' : 'text-amber-700'} bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
                      ${opt.congestion}/100 (${opt.congestion < 50 ? 'Low Queue' : 'Moderate'})
                    </span>
                  </div>
                  <div class="flex justify-between items-start">
                    <span class="text-slate-500">Port Traffic:</span>
                    <strong class="text-slate-800 text-right">${opt.traffic}</strong>
                  </div>
                  <div class="flex justify-between items-start">
                    <span class="text-slate-500">Cargo Ready to Haul:</span>
                    <strong class="text-slate-900 text-right">${opt.cargo}</strong>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="text-slate-500">Available Truck Slots:</span>
                    <strong class="text-blue-700 font-bold">${opt.slots} Empty Trucks Needed</strong>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="text-slate-500">Estimated Worker Pay:</span>
                    <strong class="text-emerald-700 font-bold">${opt.pay}</strong>
                  </div>
                </div>
              </div>

              <div class="mt-5 pt-3 border-t border-slate-200">
                <button onclick="allotTrucksToPort('${opt.name}', ${opt.slots})" class="w-full bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold py-2.5 rounded-xl transition-colors shadow-xs flex items-center justify-center gap-1.5 cursor-pointer">
                  <span>Allot ${opt.slots} Trucks to ${opt.name.split(' ')[0]} \u2192</span>
                </button>
              </div>
            </div>
          `).join('')}
        </div>
      </div>

      <!-- Simple Outcomes & Welfare Summary -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div class="card-elevation p-5 bg-white rounded-xl border-l-4 border-emerald-500">
          <div class="text-xs text-slate-500 font-medium">Workers Protected From Idling</div>
          <div class="text-2xl font-bold text-slate-900 font-outfit mt-1">${totalIdleRisk} Drivers & Helpers</div>
          <div class="text-xs text-emerald-700 mt-1 font-semibold">100% matched to low-congestion port rakes</div>
        </div>

        <div class="card-elevation p-5 bg-white rounded-xl border-l-4 border-blue-500">
          <div class="text-xs text-slate-500 font-medium">Empty Miles Avoided (Zero Deadheading)</div>
          <div class="text-2xl font-bold text-slate-900 font-outfit mt-1">14,200 km</div>
          <div class="text-xs text-blue-700 mt-1 font-semibold">Wasted diesel converted into paid freight revenue</div>
        </div>

        <div class="card-elevation p-5 bg-white rounded-xl border-l-4 border-amber-500">
          <div class="text-xs text-slate-500 font-medium">Average Daily Income Secured</div>
          <div class="text-2xl font-bold text-slate-900 font-outfit mt-1">\u20b94,250 <span class="text-xs font-normal text-slate-500">/ driver</span></div>
          <div class="text-xs text-amber-700 mt-1 font-semibold">Guaranteed minimum daily livelihood protection</div>
        </div>
      </div>

    </div>
  `;
}

// -------------------------------------------------------------
// 10. SIDEBAR TAB 4: ACCURATE EAST COAST PORT MAP (WITH SAGAR-SANDHEADS, GANGAVARAM, GOPALPUR)
// -------------------------------------------------------------

function renderPortMapView() {
  const container = document.getElementById("dynamicViewContainer");
  if (!container) return;

  container.innerHTML = `
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      <div class="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <span class="text-xs font-semibold text-blue-700 uppercase tracking-wider bg-blue-50 px-2.5 py-1 rounded-md border border-blue-200">
            Geographic Maritime Telemetry
          </span>
          <h2 class="text-2xl font-bold text-slate-900 mt-2 font-outfit">
            India East Coast Port Intelligence Map
          </h2>
          <p class="text-sm text-slate-500 mt-1">
            Geographically accurate coastal corridor featuring West Bengal, Odisha, and Andhra Pradesh gateways.
          </p>
        </div>
        <button onclick="state.activeTab='dashboard'; renderApp();" class="text-xs bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium px-3 py-2 rounded-lg transition-colors shadow-sm">
          \u2190 Back to Route Query
        </button>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <!-- SVG Map Container (8 cols) -->
        <div class="lg:col-span-7 card-elevation p-6 relative overflow-hidden bg-gradient-to-b from-sky-50 to-blue-50/40">
          <div class="flex items-center justify-between mb-4">
            <h3 class="font-bold text-slate-800 font-outfit text-sm">East Coast Gateways & Sandheads Anchorage</h3>
            <div class="flex items-center gap-3 text-xs">
              <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span> Normal (< 50)</span>
              <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-full bg-amber-500"></span> Congested (\u2265 65)</span>
            </div>
          </div>

          <div class="relative w-full h-[520px] flex items-center justify-center">
            <!-- Geographically Accurate SVG Map of East Coast India (West Bengal, Odisha, Andhra Pradesh) -->
            <svg viewBox="0 0 560 720" class="w-full h-full max-h-[540px] select-none rounded-xl" style="background: radial-gradient(circle at 65% 50%, #0d233a 0%, #061526 100%);">
              <defs>
                <pattern id="marineGrid" width="30" height="30" patternUnits="userSpaceOnUse">
                  <path d="M 0 15 Q 7.5 7.5 15 15 T 30 15" fill="none" stroke="rgba(56, 189, 248, 0.05)" stroke-width="1"/>
                </pattern>
                <!-- Land Gradient with Realistic Coastal Terrain Feel -->
                <linearGradient id="coastalLand" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#f8fafc" />
                  <stop offset="60%" stop-color="#f1f5f9" />
                  <stop offset="100%" stop-color="#e2e8f0" />
                </linearGradient>
                <!-- Bathymetry Shading Gradient -->
                <linearGradient id="shelfDrop" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="rgba(14, 165, 233, 0.12)" />
                  <stop offset="100%" stop-color="rgba(2, 132, 199, 0.02)" />
                </linearGradient>
              </defs>

              <!-- Ocean Grid Background -->
              <rect width="560" height="720" fill="url(#marineGrid)" />

              <!-- Geographic Coordinate Grid (Parallels & Meridians) -->
              <!-- Latitude Parallels -->
              <g stroke="rgba(255,255,255,0.07)" stroke-width="0.8" stroke-dasharray="2,3">
                <line x1="0" y1="80" x2="560" y2="80" />
                <line x1="0" y1="180" x2="560" y2="180" />
                <line x1="0" y1="290" x2="560" y2="290" />
                <line x1="0" y1="410" x2="560" y2="410" />
                <line x1="0" y1="530" x2="560" y2="530" />
                <line x1="0" y1="650" x2="560" y2="650" />
              </g>
              <text x="548" y="84" font-size="8" fill="rgba(148,163,184,0.6)" text-anchor="end" font-family="'JetBrains Mono', monospace">22\u00b0N</text>
              <text x="548" y="184" font-size="8" fill="rgba(148,163,184,0.6)" text-anchor="end" font-family="'JetBrains Mono', monospace">21\u00b0N</text>
              <text x="548" y="294" font-size="8" fill="rgba(148,163,184,0.6)" text-anchor="end" font-family="'JetBrains Mono', monospace">20\u00b0N</text>
              <text x="548" y="414" font-size="8" fill="rgba(148,163,184,0.6)" text-anchor="end" font-family="'JetBrains Mono', monospace">19\u00b0N</text>
              <text x="548" y="534" font-size="8" fill="rgba(148,163,184,0.6)" text-anchor="end" font-family="'JetBrains Mono', monospace">18\u00b0N</text>
              <text x="548" y="654" font-size="8" fill="rgba(148,163,184,0.6)" text-anchor="end" font-family="'JetBrains Mono', monospace">17\u00b0N</text>

              <!-- Longitude Meridians -->
              <g stroke="rgba(255,255,255,0.07)" stroke-width="0.8" stroke-dasharray="2,3">
                <line x1="160" y1="0" x2="160" y2="720" />
                <line x1="300" y1="0" x2="300" y2="720" />
                <line x1="440" y1="0" x2="440" y2="720" />
              </g>
              <text x="160" y="712" font-size="8" fill="rgba(148,163,184,0.6)" text-anchor="middle" font-family="'JetBrains Mono', monospace">84\u00b0E</text>
              <text x="300" y="712" font-size="8" fill="rgba(148,163,184,0.6)" text-anchor="middle" font-family="'JetBrains Mono', monospace">86\u00b0E</text>
              <text x="440" y="712" font-size="8" fill="rgba(148,163,184,0.6)" text-anchor="middle" font-family="'JetBrains Mono', monospace">88\u00b0E</text>

              <!-- Bathymetric Shelf Depth Contours (10m, 20m, 50m, 100m) -->
              <!-- 20m Depth Contour -->
              <path d="M 460 30 C 445 70 415 130 405 180 C 375 220 360 250 345 285 C 335 320 315 350 280 395 C 255 430 225 470 190 520 C 160 570 145 620 120 720" fill="none" stroke="rgba(56, 189, 248, 0.15)" stroke-width="1.2" stroke-dasharray="4,4"/>
              <text x="358" y="275" font-size="7" fill="rgba(56, 189, 248, 0.45)" font-family="'JetBrains Mono', monospace">20m isobath</text>

              <!-- 50m Continental Shelf Edge -->
              <path d="M 490 60 C 470 120 445 190 425 250 C 390 300 370 340 340 390 C 300 450 260 510 220 580 C 190 635 170 670 150 720" fill="none" stroke="rgba(14, 165, 233, 0.2)" stroke-width="1.4"/>
              <text x="415" y="280" font-size="7" fill="rgba(14, 165, 233, 0.5)" font-family="'JetBrains Mono', monospace">50m shelf break</text>

              <!-- Accurate Landmass Shape of East Coast India (West Bengal -> Odisha -> Andhra Pradesh) -->
              <path d="M 0 0 
                       L 440 0 
                       C 432 25 415 45 400 62 
                       C 388 72 380 75 372 78
                       C 368 85 365 98 375 115 
                       C 385 130 392 142 386 150 
                       C 375 160 360 170 345 185 
                       C 335 198 338 215 330 230 
                       C 324 242 320 255 315 270 
                       C 310 285 318 298 322 308 
                       C 325 315 320 322 308 330 
                       C 295 340 280 355 268 370 
                       C 255 385 240 405 228 420 
                       C 218 432 210 442 202 455 
                       C 192 470 182 485 172 505 
                       C 160 528 148 550 138 562 
                       C 142 570 144 576 138 580 
                       C 130 585 125 595 120 610 
                       C 112 630 102 655 92 680 
                       C 84 700 78 715 72 720 
                       L 0 720 Z" 
                    fill="url(#coastalLand)" stroke="#475569" stroke-width="1.8" />

              <!-- Chilika Lake Lagoon (Authentic Coastal Feature between Puri & Gopalpur) -->
              <path d="M 235 378 
                       C 248 375 262 382 268 395 
                       C 272 405 265 415 252 418 
                       C 238 420 228 410 224 400 
                       C 220 390 226 380 235 378 Z" 
                    fill="#38bdf8" fill-opacity="0.35" stroke="#0284c7" stroke-width="1.2"/>
              <!-- Outer Sand Spit Barrier of Chilika -->
              <path d="M 268 372 C 275 390 262 415 250 426" fill="none" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="3,2"/>
              <text x="248" y="402" font-size="8.5" fill="#0369a1" font-weight="700" text-anchor="middle">Chilika Lagoon</text>

              <!-- Major River Inlets & Estuaries -->
              <!-- 1. Hooghly River Estuary (Leading to Kolkata & Haldia) -->
              <path d="M 378 0 C 375 35 370 65 372 78 C 374 88 382 110 388 138" fill="none" stroke="#38bdf8" stroke-width="4.5" stroke-linecap="round"/>
              <text x="345" y="55" font-size="8" fill="#0284c7" font-weight="bold">Hooghly River</text>

              <!-- 2. Subarnarekha River Delta (Border Area) -->
              <path d="M 345 185 C 330 178 300 170 280 168" fill="none" stroke="#60a5fa" stroke-width="2.2" opacity="0.6"/>

              <!-- 3. Dhamra River & Wheeler (Kalam) Island -->
              <path d="M 330 230 C 310 228 290 225 270 222" fill="none" stroke="#60a5fa" stroke-width="2.5" opacity="0.6"/>
              <ellipse cx="348" cy="235" rx="5" ry="3" fill="#cbd5e1" stroke="#64748b" stroke-width="1"/>
              <text x="356" y="238" font-size="7" fill="#475569" font-style="italic">Kalam Is.</text>

              <!-- 4. Mahanadi Delta Bulge (Paradip Promontory & False Point) -->
              <path d="M 322 308 C 295 300 270 295 240 290" fill="none" stroke="#60a5fa" stroke-width="3" opacity="0.6"/>
              <path d="M 308 330 C 285 320 260 310 240 290" fill="none" stroke="#60a5fa" stroke-width="2" opacity="0.5"/>

              <!-- 5. Dolphin's Nose Rocky Headland (Protecting Vizag) -->
              <path d="M 134 565 C 145 568 148 578 138 584" fill="#94a3b8" stroke="#334155" stroke-width="1.8"/>
              <text x="150" y="578" font-size="7.5" fill="#334155" font-weight="bold">Dolphin's Nose</text>

              <!-- State Border Demarcation Lines (Accurate Geographical Boundaries) -->
              <!-- West Bengal / Odisha Boundary -->
              <g>
                <path d="M 345 185 L 210 170" stroke="#64748b" stroke-dasharray="5,4" stroke-width="1.4"/>
                <rect x="235" y="152" width="76" height="14" rx="3" fill="#ffffff" fill-opacity="0.9" stroke="#cbd5e1" stroke-width="0.8"/>
                <text x="273" y="163" font-size="8" fill="#1e293b" font-weight="800" text-anchor="middle">WEST BENGAL</text>
                <rect x="235" y="172" width="76" height="14" rx="3" fill="#ffffff" fill-opacity="0.9" stroke="#cbd5e1" stroke-width="0.8"/>
                <text x="273" y="183" font-size="8" fill="#1e293b" font-weight="800" text-anchor="middle">ODISHA</text>
              </g>

              <!-- Odisha / Andhra Pradesh Boundary (South of Gopalpur / Berhampur) -->
              <g>
                <path d="M 172 505 L 45 490" stroke="#64748b" stroke-dasharray="5,4" stroke-width="1.4"/>
                <rect x="80" y="472" width="60" height="14" rx="3" fill="#ffffff" fill-opacity="0.9" stroke="#cbd5e1" stroke-width="0.8"/>
                <text x="110" y="483" font-size="8" fill="#1e293b" font-weight="800" text-anchor="middle">ODISHA</text>
                <rect x="65" y="493" width="90" height="14" rx="3" fill="#ffffff" fill-opacity="0.9" stroke="#cbd5e1" stroke-width="0.8"/>
                <text x="110" y="504" font-size="8" fill="#1e293b" font-weight="800" text-anchor="middle">ANDHRA PRADESH</text>
              </g>

              <!-- Maritime Shipping Channels & Fairways -->
              <!-- Sandheads to Sagar Deepwater Fairway -->
              <line x1="425" y1="215" x2="388" y2="138" stroke="#38bdf8" stroke-width="2.2" stroke-dasharray="4,3"/>
              <!-- Sagar to Haldia Estuary Fairway -->
              <line x1="388" y1="138" x2="372" y2="78" stroke="#38bdf8" stroke-width="2" stroke-dasharray="3,3"/>

              <!-- Ocean Basin Label -->
              <text x="430" y="490" font-size="16" fill="rgba(255,255,255,0.14)" font-weight="900" font-family="'Outfit', sans-serif" letter-spacing="4">BAY OF BENGAL</text>
              <text x="430" y="508" font-size="9" fill="rgba(14,165,233,0.4)" font-weight="bold" font-family="'JetBrains Mono', monospace">EAST COAST CORRIDOR</text>

              <!-- ============================================== -->
              <!-- THE 7 INDIAN EAST COAST PORTS (ACCURATE SPATIAL POSITIONS) -->
              <!-- ============================================== -->

              <!-- 1. HALDIA DOCK COMPLEX (West Bengal - Inland Riverine Port) -->
              <g class="cursor-pointer group" onclick="selectPortFromMap('haldia')">
                <circle cx="372" cy="78" r="7" fill="#2563eb" stroke="#ffffff" stroke-width="2"/>
                <rect x="250" y="68" width="112" height="20" rx="4" fill="#0f172a" fill-opacity="0.9" stroke="#3b82f6" stroke-width="1"/>
                <text x="306" y="82" font-size="9.5" font-weight="bold" fill="#ffffff" text-anchor="middle">Haldia Dock (8.5m)</text>
              </g>

              <!-- 2. SAGAR ISLAND & SANDHEADS ANCHORAGE (West Bengal Deepwater Gateway) -->
              <g class="cursor-pointer group" onclick="selectPortFromMap('sagar-sandheads')">
                <!-- Sagar Island Staging Post -->
                <circle cx="388" cy="138" r="6" fill="#0ea5e9" stroke="#ffffff" stroke-width="2"/>
                <rect x="398" y="128" width="128" height="18" rx="4" fill="#0f172a" fill-opacity="0.85" stroke="#0ea5e9" stroke-width="1"/>
                <text x="462" y="141" font-size="9" font-weight="bold" fill="#7dd3fc" text-anchor="middle">Sagar Island Staging Gate</text>

                <!-- Sandheads Deep Ocean Anchorage (Crucial 16m Pilotage Station) -->
                <circle cx="425" cy="215" r="9" fill="#f59e0b" stroke="#ffffff" stroke-width="2"/>
                <circle cx="425" cy="215" r="16" fill="none" stroke="#f59e0b" stroke-width="1.8" stroke-dasharray="3,3" class="animate-spin"/>
                <rect x="365" y="235" width="150" height="22" rx="5" fill="#0f172a" stroke="#f59e0b" stroke-width="1.2"/>
                <text x="440" y="250" font-size="10" font-weight="extrabold" fill="#fbbf24" text-anchor="middle">Sandheads Anchorage \u2693 (16m)</text>
              </g>

              <!-- 3. DHAMRA PORT (Odisha - Capesize Deepwater Gateway) -->
              <g class="cursor-pointer group" onclick="selectPortFromMap('dhamra')">
                <circle cx="330" cy="230" r="7.5" fill="#10b981" stroke="#ffffff" stroke-width="2"/>
                <rect x="215" y="220" width="105" height="20" rx="4" fill="#0f172a" fill-opacity="0.9" stroke="#10b981" stroke-width="1"/>
                <text x="267" y="234" font-size="9.5" font-weight="bold" fill="#ffffff" text-anchor="middle">Dhamra Port (17.0m)</text>
              </g>

              <!-- 4. PARADIP PORT (Odisha - Major Bulk Iron Ore & Coal Terminal) -->
              <g class="cursor-pointer group" onclick="selectPortFromMap('paradip')">
                <circle cx="322" cy="308" r="9" fill="#f59e0b" stroke="#ffffff" stroke-width="2"/>
                <circle cx="322" cy="308" r="17" fill="none" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="2,2"/>
                <rect x="338" y="298" width="128" height="22" rx="5" fill="#0f172a" stroke="#f59e0b" stroke-width="1.2"/>
                <text x="402" y="313" font-size="10" font-weight="extrabold" fill="#fbbf24" text-anchor="middle">Paradip Port (14.5m) \u26a0\ufe0f</text>
              </g>

              <!-- 5. GOPALPUR PORT (Odisha - Deepwater Mineral Gateway) -->
              <g class="cursor-pointer group" onclick="selectPortFromMap('gopalpur')">
                <circle cx="202" cy="455" r="7.5" fill="#10b981" stroke="#ffffff" stroke-width="2"/>
                <rect x="95" y="445" width="98" height="20" rx="4" fill="#0f172a" fill-opacity="0.9" stroke="#10b981" stroke-width="1"/>
                <text x="144" y="459" font-size="9.5" font-weight="bold" fill="#ffffff" text-anchor="middle">Gopalpur (12.5m)</text>
              </g>

              <!-- 6. VISAKHAPATNAM (VIZAG) PORT (Andhra Pradesh - Primary Coking Coal Terminal) -->
              <g class="cursor-pointer group" onclick="selectPortFromMap('vizag')">
                <circle cx="138" cy="565" r="9.5" fill="#ef4444" stroke="#ffffff" stroke-width="2.5"/>
                <circle cx="138" cy="565" r="18" fill="none" stroke="#ef4444" stroke-width="1.8" stroke-dasharray="3,2"/>
                <rect x="155" y="554" width="135" height="22" rx="5" fill="#0f172a" stroke="#ef4444" stroke-width="1.4"/>
                <text x="222" y="569" font-size="10" font-weight="extrabold" fill="#fca5a5" text-anchor="middle">Vizag Port (18.0m) \u1f534</text>
              </g>

              <!-- 7. GANGAVARAM PORT (Andhra Pradesh - India's Deepest Port 21m) -->
              <g class="cursor-pointer group" onclick="selectPortFromMap('gangavaram')">
                <circle cx="120" cy="610" r="8.5" fill="#10b981" stroke="#ffffff" stroke-width="2"/>
                <rect x="136" y="600" width="130" height="20" rx="4" fill="#0f172a" fill-opacity="0.9" stroke="#10b981" stroke-width="1.2"/>
                <text x="201" y="614" font-size="9.5" font-weight="bold" fill="#34d399" text-anchor="middle">Gangavaram Port (21.0m)</text>
              </g>

              <!-- Nautical Compass Rose -->
              <g transform="translate(65, 75)">
                <circle cx="0" cy="0" r="24" fill="rgba(15,23,42,0.8)" stroke="#38bdf8" stroke-width="1.2"/>
                <!-- Star points -->
                <polygon points="0,-20 4,-5 19,0 4,4 0,19 -4,4 -19,0 -4,-5" fill="#38bdf8"/>
                <polygon points="0,-20 0,0 19,0" fill="#ffffff" fill-opacity="0.6"/>
                <polygon points="0,19 0,0 -19,0" fill="#ffffff" fill-opacity="0.6"/>
                <text x="0" y="-23" font-size="9" font-weight="900" fill="#38bdf8" text-anchor="middle">N</text>
              </g>

              <!-- Nautical Scale Bar -->
              <g transform="translate(30, 685)">
                <rect x="0" y="0" width="100" height="4" fill="#ffffff" stroke="#0f172a" stroke-width="1"/>
                <rect x="0" y="0" width="50" height="4" fill="#0f172a"/>
                <text x="0" y="14" font-size="8" fill="#cbd5e1" font-family="'JetBrains Mono', monospace">0</text>
                <text x="50" y="14" font-size="8" fill="#cbd5e1" font-family="'JetBrains Mono', monospace">25</text>
                <text x="100" y="14" font-size="8" fill="#cbd5e1" font-family="'JetBrains Mono', monospace">50 NM</text>
              </g>
            </svg>
          </div>
        </div>

        <!-- Port Operational Dossier Card (5 cols) -->
        <div class="lg:col-span-5 card-elevation p-6 flex flex-col justify-between" id="portDetailSidebar">
          <div>
            <div class="pb-3 border-b border-slate-100 mb-4">
              <span class="text-[10px] font-bold uppercase tracking-wider text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded-full border border-blue-200">
                Port Operational Dossier
              </span>
              <h3 class="font-bold text-slate-900 font-outfit text-xl mt-2" id="mapPortName">Visakhapatnam (Vizag)</h3>
              <p class="text-xs text-slate-500" id="mapPortState">Andhra Pradesh \u00b7 Natural Deepwater Harbour</p>
            </div>

            <!-- Detailed Operational Description Provided by User -->
            <div class="p-3.5 bg-blue-50/60 rounded-xl border border-blue-100 mb-4">
              <div class="text-[11px] font-bold uppercase text-blue-900 mb-1">Strategic Significance:</div>
              <p class="text-xs text-slate-700 leading-relaxed" id="mapPortDesc">
                Vital gateway for metallurgical and coking coal. Acts as a primary entry point for Mozambican coking coal (destined for Indian steel giants like SAIL) as well as Australian coking coal.
              </p>
            </div>

            <div class="space-y-3 text-xs">
              <div class="flex items-center justify-between py-1.5 border-b border-slate-50">
                <span class="text-slate-500">Max Permissible Draft</span>
                <span class="font-bold text-slate-800" id="mapPortDraft">18.0 Metres</span>
              </div>
              <div class="flex items-center justify-between py-1.5 border-b border-slate-50">
                <span class="text-slate-500">Max Vessel LOA</span>
                <span class="font-bold text-slate-800" id="mapPortLoa">320.0 Metres</span>
              </div>
              <div class="flex items-center justify-between py-1.5 border-b border-slate-50">
                <span class="text-slate-500">Total Operational Berths</span>
                <span class="font-bold text-slate-800" id="mapPortBerths">26 Berths</span>
              </div>
              <div class="flex items-center justify-between py-1.5 border-b border-slate-50">
                <span class="text-slate-500">Congestion Score</span>
                <span class="font-bold text-rose-600" id="mapPortScore">72 / 100</span>
              </div>
            </div>

            <!-- Dynamic Congestion Suggestion Box -->
            <div id="portCongestionSuggestionBox" class="mt-4 p-3 rounded-xl border border-rose-200 bg-rose-50/70 text-xs text-rose-900 flex items-start gap-2.5">
              <svg class="w-4 h-4 text-rose-600 mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
              <div>
                <strong class="font-bold block mb-0.5">Elevated Congestion Risk (72/100):</strong>
                <span>High queue concentration. Elevated risk of berthing delays and demurrage penalties. Recommend coordinating laycan buffers, pre-notifying terminal dispatch, or exploring lighterage operations.</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}

let activeSelectedPortId = "vizag";
window.selectPortFromMap = function (portId) {
  activeSelectedPortId = portId;
  const p = state.portsIndia.find((x) => x.id === portId);
  if (!p) return;

  const nameEl = document.getElementById("mapPortName");
  const stateEl = document.getElementById("mapPortState");
  const descEl = document.getElementById("mapPortDesc");
  const draftEl = document.getElementById("mapPortDraft");
  const loaEl = document.getElementById("mapPortLoa");
  const berthsEl = document.getElementById("mapPortBerths");
  const scoreEl = document.getElementById("mapPortScore");
  const suggestionBox = document.getElementById("portCongestionSuggestionBox");

  if (nameEl) nameEl.textContent = p.name;
  if (stateEl) stateEl.textContent = `${p.state} \u00b7 East Coast Maritime Hub`;
  if (descEl) descEl.textContent = p.description;
  if (draftEl) draftEl.textContent = `${p.maxDraft} Metres`;
  if (loaEl) loaEl.textContent = `${p.maxLoa} Metres`;
  if (berthsEl) berthsEl.textContent = `${p.berths} Berths`;
  if (scoreEl) {
    scoreEl.textContent = `${p.congestion} / 100`;
    scoreEl.className = `font-bold ${p.congestion >= 60 ? 'text-rose-600' : p.congestion >= 40 ? 'text-amber-600' : 'text-emerald-600'}`;
  }

  if (suggestionBox) {
    if (p.congestion >= 60) {
      suggestionBox.className = "mt-4 p-3 rounded-xl border border-rose-200 bg-rose-50/70 text-xs text-rose-900 flex items-start gap-2.5";
      suggestionBox.innerHTML = `
        <svg class="w-4 h-4 text-rose-600 mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
        <div>
          <strong class="font-bold block mb-0.5">Elevated Congestion Risk (${p.congestion}/100):</strong>
          <span>High queue concentration. Elevated risk of berthing delays and demurrage penalties. Recommend coordinating laycan buffers, pre-notifying terminal dispatch, or exploring lighterage operations.</span>
        </div>
      `;
    } else if (p.congestion >= 40) {
      suggestionBox.className = "mt-4 p-3 rounded-xl border border-amber-200 bg-amber-50/70 text-xs text-amber-900 flex items-start gap-2.5";
      suggestionBox.innerHTML = `
        <svg class="w-4 h-4 text-amber-600 mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
        <div>
          <strong class="font-bold block mb-0.5">Moderate Port Congestion (${p.congestion}/100):</strong>
          <span>Manageable vessel traffic with normal turnarounds. Berthing line queues are stable; maintain standard arrival ETA scheduling.</span>
        </div>
      `;
    } else {
      suggestionBox.className = "mt-4 p-3 rounded-xl border border-emerald-200 bg-emerald-50/70 text-xs text-emerald-900 flex items-start gap-2.5";
      suggestionBox.innerHTML = `
        <svg class="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
        <div>
          <strong class="font-bold block mb-0.5">Optimal Traffic Flow (${p.congestion}/100):</strong>
          <span>Low congestion score. Fast turnaround, immediate or minimal berth queuing, and negligible demurrage exposure. Optimal gateway conditions.</span>
        </div>
      `;
    }
  }
};

window.applyPortToRoute = function () {
  const p = state.portsIndia.find((x) => x.id === activeSelectedPortId);
  if (p) {
    state.query.destination = p.name.includes("Vizag") ? "Vizag" : p.name;
    const destSel = document.getElementById("destSelect");
    if (destSel) destSel.value = state.query.destination;
    state.activeTab = "dashboard";
    renderApp();
    recordModelHistoryEntry({
      action: "Port Gateway Selection",
      category: "port",
      destination: state.query.destination,
      notes: `Applied port gateway ${p.name} (${p.state}) from Port Intelligence Map.`
    });
    showToast(`Destination set to ${p.name} and logged to history.`);
  }
};

// -------------------------------------------------------------
// 11. TOAST NOTIFICATIONS
// -------------------------------------------------------------

function showToast(message) {
  let toast = document.getElementById("fiqToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "fiqToast";
    toast.className = "fixed bottom-5 right-5 z-50 bg-slate-900 text-white text-xs font-medium px-4 py-2.5 rounded-xl shadow-lg transition-all duration-300 opacity-0 pointer-events-none transform translate-y-2 flex items-center gap-2 border border-slate-700";
    document.body.appendChild(toast);
  }
  toast.innerHTML = `
    <svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
    <span>${message}</span>
  `;
  toast.classList.remove("opacity-0", "translate-y-2", "pointer-events-none");
  toast.classList.add("opacity-100", "translate-y-0");

  setTimeout(() => {
    toast.classList.remove("opacity-100", "translate-y-0");
    toast.classList.add("opacity-0", "translate-y-2", "pointer-events-none");
  }, 3200);
}

// -------------------------------------------------------------
// 12. MODEL ANALYSIS & USER ENTRY AUDIT HISTORY (CHROME-STYLE HISTORY)
// -------------------------------------------------------------

function getDefaultModelHistorySeed() {
  const now = Date.now();
  return [
    {
      id: "fiq_run_101",
      timestamp: new Date(now - 14 * 60 * 1000).toISOString(),
      displayDate: "25 Sep 2026",
      displayTime: "12:48 PM",
      timeAgo: "14 mins ago",
      dateGroup: "Today",
      user: "SAIL Procurement Desk (Officer ID: 7041)",
      role: "Senior Charterer / Dry Bulk Desk",
      action: "Freight Rate Valuation",
      category: "valuation",
      origin: "Australia \u2014 Newcastle - Kooragang",
      originCountry: "Australia",
      destination: "Vizag",
      destinationState: "Andhra Pradesh",
      vesselType: "Supramax",
      cargoDwt: 55000,
      cargoCommodity: "Premium Hard Coking Coal",
      distanceNm: 4850,
      speedKnots: 12.5,
      voyageDays: 16.2,
      baseRate: 21.40,
      currency: "USD",
      unit: "$/Ton",
      totalExpenditure: 1177000,
      regretMin: 19.80,
      regretMax: 22.60,
      regretLossBenefit: "58.9%",
      congestionScore: 0.48,
      portQueueDays: 1.4,
      queueWaitHours: 33.6,
      waitingVessels: 8,
      confidenceScore: "94.8%",
      verdict: "LOCK IN SPOT FIXTURE",
      verdictBadge: "Spot Lock-in",
      bunkerConsumptionMT: 372,
      bunkerPriceUSD: 615,
      fuelCostShare: "41.5%",
      portTariffShare: "18.2%",
      tceDailyRate: 14250,
      scenarioWeights: { weather: 1.0, congestion: 1.0, fuel: 1.0, fx: 1.0 },
      notes: "Regular quarterly coking coal parcel for Visakhapatnam Steel Plant (RINL/SAIL). Upward rate momentum observed."
    },
    {
      id: "fiq_run_102",
      timestamp: new Date(now - 58 * 60 * 1000).toISOString(),
      displayDate: "25 Sep 2026",
      displayTime: "12:04 PM",
      timeAgo: "58 mins ago",
      dateGroup: "Today",
      user: "Chartering Desk (Capt. A. Sen)",
      role: "Marine Logistics Officer",
      action: "Scenario Stress Test",
      category: "scenario",
      origin: "United States \u2014 Norfolk - Lamberts Point Pier 6",
      originCountry: "United States",
      destination: "Paradip",
      destinationState: "Odisha",
      vesselType: "Capesize",
      cargoDwt: 160000,
      cargoCommodity: "Metallurgical High-Vol Coal",
      distanceNm: 11800,
      speedKnots: 12.5,
      voyageDays: 39.3,
      baseRate: 31.30,
      currency: "USD",
      unit: "$/Ton",
      totalExpenditure: 5008000,
      regretMin: 29.40,
      regretMax: 34.10,
      regretLossBenefit: "63.2%",
      congestionScore: 0.72,
      portQueueDays: 2.8,
      queueWaitHours: 67.2,
      waitingVessels: 14,
      confidenceScore: "91.2%",
      verdict: "CONSIDER 3-MONTH COA SPLIT",
      verdictBadge: "COA Recommended",
      bunkerConsumptionMT: 1415,
      bunkerPriceUSD: 615,
      fuelCostShare: "46.8%",
      portTariffShare: "14.1%",
      tceDailyRate: 22800,
      scenarioWeights: { weather: 1.3, congestion: 1.1, fuel: 1.2, fx: 1.0 },
      notes: "Cape routing sensitivity stress test evaluated under weather 1.3x and bunker surge 1.2x multipliers."
    },
    {
      id: "fiq_run_103",
      timestamp: new Date(now - 148 * 60 * 1000).toISOString(),
      displayDate: "25 Sep 2026",
      displayTime: "10:34 AM",
      timeAgo: "2 hours ago",
      dateGroup: "Today",
      user: "SAIL Procurement Desk (Officer ID: 7041)",
      role: "Senior Charterer / Dry Bulk Desk",
      action: "Vessel Optimization",
      category: "vessel",
      origin: "Indonesia \u2014 Taboneo (Banjarmasin anchorage)",
      originCountry: "Indonesia",
      destination: "Haldia",
      destinationState: "West Bengal",
      vesselType: "Panamax",
      cargoDwt: 75000,
      cargoCommodity: "Thermal Coal (Indonesian Mid-CV)",
      distanceNm: 2150,
      speedKnots: 12.5,
      voyageDays: 7.2,
      baseRate: 12.90,
      currency: "USD",
      unit: "$/Ton",
      totalExpenditure: 967500,
      regretMin: 11.80,
      regretMax: 14.20,
      regretLossBenefit: "54.1%",
      congestionScore: 0.64,
      portQueueDays: 2.1,
      queueWaitHours: 50.4,
      waitingVessels: 11,
      confidenceScore: "96.1%",
      verdict: "LIGHTEN PARCEL OR TRANSSHIP AT SAGAR",
      verdictBadge: "Lightening Required",
      bunkerConsumptionMT: 172,
      bunkerPriceUSD: 615,
      fuelCostShare: "38.2%",
      portTariffShare: "22.5%",
      tceDailyRate: 11900,
      scenarioWeights: { weather: 1.0, congestion: 1.0, fuel: 1.0, fx: 1.0 },
      notes: "River draft limitation at Haldia (8.2m tide-dependent). Recommended transshipment or Sagar Sandheads lightering."
    },
    {
      id: "fiq_run_104",
      timestamp: new Date(now - 26 * 3600 * 1000).toISOString(),
      displayDate: "24 Sep 2026",
      displayTime: "03:15 PM",
      timeAgo: "Yesterday",
      dateGroup: "Yesterday",
      user: "SAIL Logistics Cell (Kolkata HQ)",
      role: "Central Raw Material Desk",
      action: "Freight Rate Valuation",
      category: "valuation",
      origin: "Russia \u2014 Vostochny",
      originCountry: "Russia",
      destination: "Dhamra",
      destinationState: "Odisha",
      vesselType: "Supramax",
      cargoDwt: 55000,
      cargoCommodity: "PCI Coal (Pulverized Coal Injection)",
      distanceNm: 5400,
      speedKnots: 12.5,
      voyageDays: 18.0,
      baseRate: 23.60,
      currency: "USD",
      unit: "$/Ton",
      totalExpenditure: 1298000,
      regretMin: 22.10,
      regretMax: 25.20,
      regretLossBenefit: "61.0%",
      congestionScore: 0.32,
      portQueueDays: 0.8,
      queueWaitHours: 19.2,
      waitingVessels: 4,
      confidenceScore: "93.4%",
      verdict: "SPOT FIXTURE APPROVED",
      verdictBadge: "Approved",
      bunkerConsumptionMT: 410,
      bunkerPriceUSD: 615,
      fuelCostShare: "43.1%",
      portTariffShare: "16.8%",
      tceDailyRate: 14800,
      scenarioWeights: { weather: 1.0, congestion: 1.0, fuel: 1.0, fx: 1.0 },
      notes: "Far East Russian export terminal loading for Bokaro Steel Plant feeding via Dhamra deep-water cape berth."
    },
    {
      id: "fiq_run_105",
      timestamp: new Date(now - 31 * 3600 * 1000).toISOString(),
      displayDate: "24 Sep 2026",
      displayTime: "11:22 AM",
      timeAgo: "Yesterday",
      dateGroup: "Yesterday",
      user: "Port Operations Cell",
      role: "Discharge Port Coordinator",
      action: "Port Gateway Selection",
      category: "port",
      origin: "Australia \u2014 Hay Point Coal Terminal",
      originCountry: "Australia",
      destination: "Gangavaram",
      destinationState: "Andhra Pradesh",
      vesselType: "Capesize",
      cargoDwt: 160000,
      cargoCommodity: "Hard Coking Coal",
      distanceNm: 4850,
      speedKnots: 12.5,
      voyageDays: 16.2,
      baseRate: 14.80,
      currency: "USD",
      unit: "$/Ton",
      totalExpenditure: 2368000,
      regretMin: 13.50,
      regretMax: 16.20,
      regretLossBenefit: "65.4%",
      congestionScore: 0.38,
      portQueueDays: 1.1,
      queueWaitHours: 26.4,
      waitingVessels: 5,
      confidenceScore: "95.5%",
      verdict: "LOW DEMURRAGE RISK \u2014 PROCEED",
      verdictBadge: "Low Demurrage",
      bunkerConsumptionMT: 585,
      bunkerPriceUSD: 615,
      fuelCostShare: "40.2%",
      portTariffShare: "17.4%",
      tceDailyRate: 19500,
      scenarioWeights: { weather: 1.0, congestion: 1.0, fuel: 1.0, fx: 1.0 },
      notes: "Deep water harbor evaluation with direct automated conveyor discharge to stockyards."
    },
    {
      id: "fiq_run_106",
      timestamp: new Date(now - 52 * 3600 * 1000).toISOString(),
      displayDate: "23 Sep 2026",
      displayTime: "02:40 PM",
      timeAgo: "2 days ago",
      dateGroup: "Earlier this week",
      user: "Chartering Desk (Capt. A. Sen)",
      role: "Marine Logistics Officer",
      action: "Fleet Repositioning Simulation",
      category: "scenario",
      origin: "Mozambique \u2014 Beira",
      originCountry: "Mozambique",
      destination: "Gopalpur",
      destinationState: "Odisha",
      vesselType: "Supramax",
      cargoDwt: 55000,
      cargoCommodity: "Coking Coal (Moatize Basin)",
      distanceNm: 4150,
      speedKnots: 12.5,
      voyageDays: 13.8,
      baseRate: 19.60,
      currency: "USD",
      unit: "$/Ton",
      totalExpenditure: 1078000,
      regretMin: 18.40,
      regretMax: 21.00,
      regretLossBenefit: "56.8%",
      congestionScore: 0.28,
      portQueueDays: 0.7,
      queueWaitHours: 16.8,
      waitingVessels: 3,
      confidenceScore: "92.7%",
      verdict: "OPTIMAL ANTI-DEADHEADING BALLAST ROUTE",
      verdictBadge: "Anti-Deadheading Fit",
      bunkerConsumptionMT: 318,
      bunkerPriceUSD: 615,
      fuelCostShare: "39.6%",
      portTariffShare: "19.0%",
      tceDailyRate: 13600,
      scenarioWeights: { weather: 1.0, congestion: 1.0, fuel: 1.0, fx: 1.0 },
      notes: "Ballast repositioning leg evaluated for Supramax vessel completing discharge on East African coast."
    }
  ];
}

function initModelHistory() {
  try {
    const raw = localStorage.getItem("freightiq_model_history");
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) {
        state.modelHistory = parsed;
      } else {
        state.modelHistory = getDefaultModelHistorySeed();
        saveModelHistory(state.modelHistory);
      }
    } else {
      state.modelHistory = getDefaultModelHistorySeed();
      saveModelHistory(state.modelHistory);
    }
  } catch (e) {
    console.error("Error loading model history:", e);
    state.modelHistory = getDefaultModelHistorySeed();
  }
  updateHistoryBadge();
}

function updateHistoryBadge() {
  const badge = document.getElementById("historyBadgeCount");
  if (badge) {
    const count = state.modelHistory ? state.modelHistory.length : 0;
    badge.textContent = `${count} logs`;
  }
}

function saveModelHistory(list) {
  state.modelHistory = list;
  try {
    localStorage.setItem("freightiq_model_history", JSON.stringify(list));
  } catch (e) {
    console.error("Could not write to localStorage:", e);
  }
  updateHistoryBadge();
}

function recordModelHistoryEntry(data = {}) {
  const origin = data.origin || state.query.origin;
  const destination = data.destination || state.query.destination;
  const vesselType = data.vesselType || state.query.vesselType;
  const m = getCalculatedMetrics();

  const now = new Date();
  const hours = now.getHours();
  const minutes = now.getMinutes();
  const ampm = hours >= 12 ? 'PM' : 'AM';
  const formattedHours = hours % 12 ? hours % 12 : 12;
  const formattedMinutes = minutes < 10 ? '0' + minutes : minutes;
  const timeStr = `${formattedHours}:${formattedMinutes} ${ampm}`;

  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const dateStr = `${now.getDate()} ${months[now.getMonth()]} ${now.getFullYear()}`;

  const action = data.action || "Freight Rate Valuation";
  const category = data.category || (action.includes("Scenario") ? "scenario" : action.includes("Vessel") ? "vessel" : action.includes("Port") ? "port" : "valuation");

  let cargoDwt = 55000;
  if (vesselType === "Capesize") cargoDwt = 160000;
  else if (vesselType === "Panamax") cargoDwt = 75000;
  else if (vesselType === "Handysize") cargoDwt = 35000;

  const baseRate = m.baseRate || 21.40;
  const totalExpenditure = Math.round(baseRate * cargoDwt);
  const voyageDays = (m.distanceNm / (12.5 * 24)).toFixed(1);

  const entry = {
    id: "fiq_run_" + Date.now() + "_" + Math.random().toString(36).substring(2, 6),
    timestamp: now.toISOString(),
    displayDate: dateStr,
    displayTime: timeStr,
    timeAgo: "Just now",
    dateGroup: "Today",
    user: state.user ? (state.user.name || state.user.email) : "SAIL Procurement Desk (Officer ID: 7041)",
    role: state.user ? (state.user.role || "Procurement Officer") : "Senior Charterer / Dry Bulk Desk",
    action: action,
    category: category,
    origin: origin,
    originCountry: origin.split("\u2014")[0]?.trim() || "International",
    destination: destination,
    destinationState: destination.includes("Vizag") || destination.includes("Gangavaram") ? "Andhra Pradesh" : destination.includes("Haldia") || destination.includes("Sagar") ? "West Bengal" : "Odisha",
    vesselType: vesselType,
    cargoDwt: cargoDwt,
    cargoCommodity: data.cargoCommodity || (origin.includes("Coal") || origin.includes("Australia") || origin.includes("Indonesia") ? "Coking Coal" : "Metallurgical Coal"),
    distanceNm: m.distanceNm || 4850,
    speedKnots: 12.5,
    voyageDays: parseFloat(voyageDays),
    baseRate: parseFloat(baseRate.toFixed(2)),
    currency: "USD",
    unit: "$/Ton",
    totalExpenditure: totalExpenditure,
    regretMin: parseFloat((m.typicalMin || (baseRate * 0.92)).toFixed(2)),
    regretMax: parseFloat((m.typicalMax || (baseRate * 1.08)).toFixed(2)),
    regretLossBenefit: "59.2%",
    congestionScore: destination.includes("Haldia") ? 0.64 : destination.includes("Paradip") ? 0.58 : 0.44,
    portQueueDays: destination.includes("Haldia") ? 2.1 : destination.includes("Paradip") ? 1.8 : 1.2,
    queueWaitHours: destination.includes("Haldia") ? 50.4 : destination.includes("Paradip") ? 43.2 : 28.8,
    waitingVessels: destination.includes("Haldia") ? 11 : destination.includes("Paradip") ? 9 : 6,
    confidenceScore: "95.1%",
    verdict: data.verdict || "LOCK IN SPOT FIXTURE",
    verdictBadge: data.verdictBadge || "Spot Lock-in",
    bunkerConsumptionMT: Math.round(parseFloat(voyageDays) * 23),
    bunkerPriceUSD: 615,
    fuelCostShare: "42.0%",
    portTariffShare: "18.0%",
    tceDailyRate: Math.round((totalExpenditure * 0.52) / Math.max(1, parseFloat(voyageDays))),
    scenarioWeights: { ...state.scenarioWeights },
    notes: data.notes || `Live inquiry evaluated for ${vesselType} bulk shipment on corridor ${origin} to ${destination}.`
  };

  state.modelHistory.unshift(entry);
  if (state.modelHistory.length > 80) state.modelHistory.pop();
  saveModelHistory(state.modelHistory);

  if (state.activeTab === "model-analysis") {
    renderModelAnalysisView();
  }
}

window.clearModelHistory = function () {
  if (confirm("Are you sure you want to clear all model entry history records?")) {
    state.modelHistory = [];
    saveModelHistory(state.modelHistory);
    renderModelAnalysisView();
    showToast("Model analysis history cleared.");
  }
};

window.resetModelHistorySeed = function () {
  state.modelHistory = getDefaultModelHistorySeed();
  saveModelHistory(state.modelHistory);
  renderModelAnalysisView();
  showToast("Demonstration audit trail restored.");
};

window.deleteModelHistoryEntry = function (id) {
  state.modelHistory = state.modelHistory.filter(x => x.id !== id);
  saveModelHistory(state.modelHistory);
  renderModelAnalysisView();
  showToast("Entry removed from history.");
};

window.reRunModelHistoryEntry = function (id) {
  const entry = state.modelHistory.find(x => x.id === id);
  if (!entry) return;

  state.query.origin = entry.origin;
  state.query.destination = entry.destination;
  state.query.vesselType = entry.vesselType;

  const originSel = document.getElementById("originSelect");
  const destSel = document.getElementById("destSelect");
  const vesselSel = document.getElementById("vesselTypeSelect");

  if (originSel) originSel.value = entry.origin;
  if (destSel) destSel.value = entry.destination;
  if (vesselSel) vesselSel.value = entry.vesselType;

  const dynamicOrigin = document.getElementById("heroOriginLabel");
  const dynamicDest = document.getElementById("heroDestLabel");
  if (dynamicOrigin) dynamicOrigin.textContent = entry.origin;
  if (dynamicDest) dynamicDest.textContent = entry.destination;

  document.querySelectorAll(".chip-btn").forEach((c) => {
    if (c.dataset.vessel === entry.vesselType) c.classList.add("active");
    else c.classList.remove("active");
  });

  state.hasCalculatedPrice = true;
  state.activeTab = "dashboard";
  closeModelDetailModal();
  renderApp();

  const resultsEl = document.getElementById("resultsDashboardSection");
  if (resultsEl) {
    resultsEl.classList.remove("hidden");
    resultsEl.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  showToast(`Restored query: ${entry.origin} \u2192 ${entry.destination}`);
};

window.exportModelHistoryCSV = function () {
  if (!state.modelHistory || state.modelHistory.length === 0) {
    showToast("No history entries to export.");
    return;
  }

  const headers = [
    "Run ID",
    "Timestamp",
    "Date",
    "Time",
    "Operator",
    "Action Type",
    "Origin Port",
    "Destination Port",
    "Vessel Class",
    "Cargo DWT",
    "Distance (NM)",
    "Voyage Days",
    "Modeled Rate ($/Ton)",
    "Total Voyage Cost ($)",
    "Regret Bound Min",
    "Regret Bound Max",
    "Berth Congestion Score",
    "Queue Delay Hours",
    "Confidence",
    "Decision Verdict",
    "Notes"
  ];

  const rows = state.modelHistory.map(e => [
    `"${e.id}"`,
    `"${e.timestamp}"`,
    `"${e.displayDate}"`,
    `"${e.displayTime}"`,
    `"${(e.user || '').replace(/"/g, '""')}"`,
    `"${(e.action || '').replace(/"/g, '""')}"`,
    `"${(e.origin || '').replace(/"/g, '""')}"`,
    `"${(e.destination || '').replace(/"/g, '""')}"`,
    `"${e.vesselType}"`,
    e.cargoDwt,
    e.distanceNm,
    e.voyageDays,
    e.baseRate,
    e.totalExpenditure,
    e.regretMin,
    e.regretMax,
    e.congestionScore,
    e.queueWaitHours,
    `"${e.confidenceScore}"`,
    `"${(e.verdict || '').replace(/"/g, '""')}"`,
    `"${(e.notes || '').replace(/"/g, '""')}"`
  ]);

  const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map(r => r.join(","))].join("\n");
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", `freightiq_model_audit_trail_${Date.now()}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  showToast("Audit trail CSV downloaded.");
};

window.exportModelHistoryJSON = function () {
  if (!state.modelHistory || state.modelHistory.length === 0) {
    showToast("No history entries to export.");
    return;
  }
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(state.modelHistory, null, 2));
  const link = document.createElement("a");
  link.setAttribute("href", dataStr);
  link.setAttribute("download", `freightiq_model_history_${Date.now()}.json`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  showToast("Model analysis JSON file downloaded.");
};

window.copyModelEntryJSON = function (id) {
  const entry = state.modelHistory.find(x => x.id === id);
  if (!entry) return;
  navigator.clipboard.writeText(JSON.stringify(entry, null, 2)).then(() => {
    showToast("Copied entry JSON to clipboard!");
  }).catch(() => {
    showToast("Failed to copy JSON to clipboard.");
  });
};

window.openModelDetailModal = function (id) {
  const entry = state.modelHistory.find(x => x.id === id);
  if (!entry) return;

  const modal = document.getElementById("modelAnalysisDetailModal");
  const body = document.getElementById("modelDetailModalBody");
  if (!modal || !body) return;

  const badgeColor = entry.category === "scenario" ? "bg-amber-100 text-amber-800 border-amber-300" :
                     entry.category === "vessel" ? "bg-emerald-100 text-emerald-800 border-emerald-300" :
                     entry.category === "port" ? "bg-teal-100 text-teal-800 border-teal-300" :
                     "bg-blue-100 text-blue-800 border-blue-300";

  body.innerHTML = `
    <div>
      <!-- Modal Header -->
      <div class="flex items-start justify-between pb-4 border-b border-slate-100 mb-6">
        <div>
          <div class="flex items-center gap-2 mb-1.5 flex-wrap">
            <span class="text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full border ${badgeColor}">
              ${entry.action}
            </span>
            <span class="text-xs font-mono text-slate-400 bg-slate-100 px-2 py-0.5 rounded">
              ${entry.id}
            </span>
            <span class="text-xs text-slate-500 font-medium">
              ${entry.displayDate} \u00b7 ${entry.displayTime}
            </span>
          </div>
          <h2 class="text-xl font-bold text-slate-900 font-outfit">
            ${entry.origin} <span class="text-blue-600">\u2192</span> ${entry.destination}
          </h2>
          <p class="text-xs text-slate-500 mt-0.5">
            Logged by <strong class="text-slate-700">${entry.user}</strong> (${entry.role || 'Chartering Cell'})
          </p>
        </div>
      </div>

      <!-- Key Economic Highlight Strip -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 bg-slate-50 rounded-xl border border-slate-200 mb-6">
        <div>
          <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Modeled Rate</div>
          <div class="text-xl font-bold text-slate-900 font-outfit mt-0.5">$${entry.baseRate.toFixed(2)} <span class="text-xs font-normal text-slate-500">/ Ton</span></div>
          <div class="text-[10px] text-slate-500 mt-0.5">Confidence: ${entry.confidenceScore}</div>
        </div>
        <div>
          <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Total Fixture Value</div>
          <div class="text-xl font-bold text-emerald-700 font-outfit mt-0.5">$${(entry.totalExpenditure / 1e6).toFixed(2)}M</div>
          <div class="text-[10px] text-slate-500 mt-0.5">For ${entry.cargoDwt.toLocaleString()} MT</div>
        </div>
        <div>
          <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Distance & Sea Transit</div>
          <div class="text-xl font-bold text-slate-900 font-outfit mt-0.5">${entry.distanceNm.toLocaleString()} <span class="text-xs font-normal text-slate-500">NM</span></div>
          <div class="text-[10px] text-slate-500 mt-0.5">~${entry.voyageDays} days @ 12.5 kts</div>
        </div>
        <div>
          <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Port Congestion Risk</div>
          <div class="text-xl font-bold text-amber-700 font-outfit mt-0.5">${Math.round(entry.congestionScore * 100)}%</div>
          <div class="text-[10px] text-slate-500 mt-0.5">~${entry.portQueueDays} days queue wait</div>
        </div>
      </div>

      <!-- 3-Column Detailed Analysis -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-5 mb-6 text-xs">
        
        <!-- Column 1: Route & Vessel Specifications -->
        <div class="bg-white p-4 rounded-xl border border-slate-200 space-y-2.5">
          <div class="font-bold text-slate-800 text-sm font-outfit border-b border-slate-100 pb-1.5 flex items-center gap-1.5">
            <svg class="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10a1 1 0 001 1h1m8-1a1 1 0 01-1 1H9m4-1V8a1 1 0 011-1h2.586a1 1 0 01.707.293l3.414 3.414a1 1 0 01.293.707V16a1 1 0 01-1 1h-1m-6-1a1 1 0 001 1h1M5 17a2 2 0 104 0m-4 0a2 2 0 114 0m6 0a2 2 0 104 0m-4 0a2 2 0 114 0"/></svg>
            Operational Parameters
          </div>
          <div class="flex justify-between py-1 border-b border-slate-100">
            <span class="text-slate-500">Origin Port:</span>
            <span class="font-semibold text-slate-800 text-right">${entry.origin}</span>
          </div>
          <div class="flex justify-between py-1 border-b border-slate-100">
            <span class="text-slate-500">Destination Port:</span>
            <span class="font-semibold text-slate-800 text-right">${entry.destination} (${entry.destinationState})</span>
          </div>
          <div class="flex justify-between py-1 border-b border-slate-100">
            <span class="text-slate-500">Vessel Class:</span>
            <span class="font-semibold text-slate-800">${entry.vesselType}</span>
          </div>
          <div class="flex justify-between py-1 border-b border-slate-100">
            <span class="text-slate-500">Cargo Deadweight:</span>
            <span class="font-semibold text-slate-800">${entry.cargoDwt.toLocaleString()} MT DWT</span>
          </div>
          <div class="flex justify-between py-1">
            <span class="text-slate-500">Commodity:</span>
            <span class="font-semibold text-slate-800">${entry.cargoCommodity || 'Coking Coal'}</span>
          </div>
        </div>

        <!-- Column 2: Financial & Rate Breakdown -->
        <div class="bg-white p-4 rounded-xl border border-slate-200 space-y-2.5">
          <div class="font-bold text-slate-800 text-sm font-outfit border-b border-slate-100 pb-1.5 flex items-center gap-1.5">
            <svg class="w-4 h-4 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            Valuation & Cost Shares
          </div>
          <div class="flex justify-between py-1 border-b border-slate-100">
            <span class="text-slate-500">Asymmetric Regret Range:</span>
            <span class="font-semibold text-slate-800">$${entry.regretMin.toFixed(2)} \u2013 $${entry.regretMax.toFixed(2)}</span>
          </div>
          <div class="flex justify-between py-1 border-b border-slate-100">
            <span class="text-slate-500">TCE Equivalent:</span>
            <span class="font-semibold text-slate-800">~$${entry.tceDailyRate.toLocaleString()} / day</span>
          </div>
          <div class="flex justify-between py-1 border-b border-slate-100">
            <span class="text-slate-500">Bunker Fuel Share:</span>
            <span class="font-semibold text-slate-800">${entry.fuelCostShare} (~${entry.bunkerConsumptionMT} MT)</span>
          </div>
          <div class="flex justify-between py-1 border-b border-slate-100">
            <span class="text-slate-500">Port Tariffs & Dues:</span>
            <span class="font-semibold text-slate-800">${entry.portTariffShare}</span>
          </div>
          <div class="flex justify-between py-1">
            <span class="text-slate-500">Regret Benefit vs OLS:</span>
            <span class="font-semibold text-teal-700">${entry.regretLossBenefit}</span>
          </div>
        </div>

        <!-- Column 3: Decision & Sensitivity Multipliers -->
        <div class="bg-white p-4 rounded-xl border border-slate-200 space-y-2.5">
          <div class="font-bold text-slate-800 text-sm font-outfit border-b border-slate-100 pb-1.5 flex items-center gap-1.5">
            <svg class="w-4 h-4 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            Model Verdict & Scenarios
          </div>
          <div class="p-2.5 bg-emerald-50 border border-emerald-200 rounded-lg">
            <div class="text-[10px] font-bold uppercase text-emerald-700">Recommendation Verdict</div>
            <div class="text-xs font-bold text-emerald-900 mt-0.5">${entry.verdict}</div>
          </div>
          <div class="text-[11px] text-slate-600 leading-snug">
            <strong>Notes:</strong> ${entry.notes}
          </div>
          <div class="pt-2 border-t border-slate-100">
            <div class="text-[10px] text-slate-400 uppercase font-semibold mb-1">Scenario Multipliers</div>
            <div class="grid grid-cols-2 gap-1 text-[11px] font-mono text-slate-600">
              <div>Weather: ${entry.scenarioWeights?.weather || 1.0}x</div>
              <div>Congestion: ${entry.scenarioWeights?.congestion || 1.0}x</div>
              <div>Bunker Fuel: ${entry.scenarioWeights?.fuel || 1.0}x</div>
              <div>Currency FX: ${entry.scenarioWeights?.fx || 1.0}x</div>
            </div>
          </div>
        </div>

      </div>

      <!-- Raw JSON Inspector Accordion -->
      <div class="border border-slate-200 rounded-xl overflow-hidden mb-6">
        <div class="p-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-xs font-bold text-slate-700 font-mono">Raw Machine-Readable Audit Payload</span>
            <span class="text-[10px] text-slate-400">(JSON Schema v2.4)</span>
          </div>
          <button onclick="copyModelEntryJSON('${entry.id}')" class="text-xs bg-white border border-slate-200 text-slate-700 hover:bg-slate-100 font-medium px-2.5 py-1 rounded-md transition-colors flex items-center gap-1 shadow-2xs">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"/></svg>
            Copy JSON
          </button>
        </div>
        <pre class="p-4 bg-slate-900 text-cyan-300 font-mono text-[11px] overflow-x-auto max-h-56 leading-relaxed select-all">${JSON.stringify(entry, null, 2)}</pre>
      </div>

      <!-- Modal Footer Action Buttons -->
      <div class="flex flex-col sm:flex-row items-center justify-between gap-3 pt-4 border-t border-slate-100">
        <div class="text-[11px] text-slate-400">
          Record ID: <span class="font-mono text-slate-600">${entry.id}</span> \u00b7 Stored locally
        </div>
        <div class="flex items-center gap-2 w-full sm:w-auto">
          <button onclick="closeModelDetailModal()" class="flex-1 sm:flex-none text-xs bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium px-4 py-2.5 rounded-xl transition-colors">
            Close
          </button>
          <button onclick="reRunModelHistoryEntry('${entry.id}')" class="flex-1 sm:flex-none text-xs bg-blue-600 hover:bg-blue-700 text-white font-bold px-5 py-2.5 rounded-xl shadow-md transition-colors flex items-center justify-center gap-1.5">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
            Re-run in Model Engine
          </button>
        </div>
      </div>
    </div>
  `;

  modal.classList.remove("hidden");
  modal.classList.add("flex");
};

window.closeModelDetailModal = function () {
  const modal = document.getElementById("modelAnalysisDetailModal");
  if (modal) {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  }
};

function renderModelAnalysisView() {
  const container = document.getElementById("dynamicViewContainer");
  if (!container) return;

  const totalRuns = state.modelHistory ? state.modelHistory.length : 0;
  let avgRate = 0;
  let totalDwt = 0;
  if (totalRuns > 0) {
    const sumRate = state.modelHistory.reduce((acc, x) => acc + (x.baseRate || 0), 0);
    avgRate = (sumRate / totalRuns).toFixed(2);
    totalDwt = state.modelHistory.reduce((acc, x) => acc + (x.cargoDwt || 0), 0);
  }

  container.innerHTML = `
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      
      <!-- Top Header Navigation & Title -->
      <div class="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 class="text-2xl font-bold text-slate-900 font-outfit">
            Analysis History
          </h2>
        </div>

        <!-- Action Header Buttons -->
        <div class="flex flex-wrap items-center gap-2">
          <button onclick="state.activeTab='dashboard'; renderApp();" class="text-xs bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium px-3 py-2 rounded-lg transition-colors shadow-2xs">
            \u2190 Back to Route Explorer
          </button>
          <button onclick="exportModelHistoryCSV()" class="text-xs bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-3 py-2 rounded-lg transition-colors shadow-xs flex items-center gap-1.5">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
            Export CSV
          </button>
          <button onclick="exportModelHistoryJSON()" class="text-xs bg-slate-800 hover:bg-slate-900 text-white font-bold px-3 py-2 rounded-lg transition-colors shadow-xs flex items-center gap-1.5">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
            Export JSON
          </button>
        </div>
      </div>

      <!-- Chrome History Filter & Search Toolbar -->
      <div class="card-elevation p-4 mb-6 bg-white">
        <div class="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
          
          <!-- Search Input (Chrome History Style) -->
          <div class="relative flex-1">
            <svg class="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
            <input 
              id="historySearchInput" 
              type="text" 
              placeholder="Search history by port, vessel class, date, operator, or notes..." 
              value="${state.modelHistoryFilter.search || ''}"
              class="w-full text-xs pl-10 pr-8 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-purple-500 focus:bg-white transition-colors"
            >
            ${state.modelHistoryFilter.search ? `
              <button onclick="clearHistorySearch()" class="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-1">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
              </button>
            ` : ''}
          </div>

          <!-- Vessel Filter Chips -->
          <div class="flex items-center gap-1.5 flex-wrap">
            <span class="text-[11px] font-bold text-slate-400 uppercase tracking-wider mr-1">Vessel:</span>
            ${['all', 'Capesize', 'Panamax', 'Supramax'].map(v => `
              <button 
                onclick="filterHistoryVessel('${v}')" 
                class="px-2.5 py-1 text-xs font-medium rounded-lg transition-colors ${state.modelHistoryFilter.vessel === v ? 'bg-purple-600 text-white font-bold shadow-2xs' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}"
              >
                ${v === 'all' ? 'All' : v}
              </button>
            `).join('')}
          </div>

          <!-- Category Filter Chips -->
          <div class="flex items-center gap-1.5 flex-wrap">
            <span class="text-[11px] font-bold text-slate-400 uppercase tracking-wider mr-1">Type:</span>
            ${[
              { key: 'all', label: 'All Actions' },
              { key: 'valuation', label: 'Valuations' },
              { key: 'scenario', label: 'Stress Tests' },
              { key: 'port', label: 'Port Gateway' }
            ].map(c => `
              <button 
                onclick="filterHistoryCategory('${c.key}')" 
                class="px-2.5 py-1 text-xs font-medium rounded-lg transition-colors ${state.modelHistoryFilter.category === c.key ? 'bg-slate-800 text-white font-bold shadow-2xs' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}"
              >
                ${c.label}
              </button>
            `).join('')}
          </div>

        </div>
      </div>

      <!-- History Entries Timeline Section -->
      <div id="historyEntriesTimelineContainer">
        ${renderModelHistoryTimelineList()}
      </div>

    </div>
  `;

  // Attach search listener
  const searchInput = document.getElementById("historySearchInput");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      state.modelHistoryFilter.search = e.target.value.toLowerCase().trim();
      updateModelHistoryTimelineDOM();
    });
  }
}

function updateModelHistoryTimelineDOM() {
  const container = document.getElementById("historyEntriesTimelineContainer");
  if (container) {
    container.innerHTML = renderModelHistoryTimelineList();
  }
}

window.clearHistorySearch = function () {
  state.modelHistoryFilter.search = "";
  const input = document.getElementById("historySearchInput");
  if (input) input.value = "";
  updateModelHistoryTimelineDOM();
};

window.filterHistoryVessel = function (vessel) {
  state.modelHistoryFilter.vessel = vessel;
  renderModelAnalysisView();
};

window.filterHistoryCategory = function (category) {
  state.modelHistoryFilter.category = category;
  renderModelAnalysisView();
};

function renderModelHistoryTimelineList() {
  if (!state.modelHistory || state.modelHistory.length === 0) {
    return `
      <div class="card-elevation p-12 text-center bg-white rounded-2xl">
        <div class="w-12 h-12 mx-auto mb-3 bg-purple-50 text-purple-600 rounded-full flex items-center justify-center">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
        </div>
        <h3 class="text-base font-bold text-slate-800 font-outfit">No History Records Found</h3>
        <p class="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
          Start exploring freight routes, running scenario sensitivity models, or restore demonstration audit logs below.
        </p>
        <button onclick="resetModelHistorySeed()" class="mt-4 text-xs bg-purple-600 hover:bg-purple-700 text-white font-bold px-4 py-2 rounded-xl transition-colors shadow-md">
          Restore Demonstration Records
        </button>
      </div>
    `;
  }

  // Filter entries
  const query = (state.modelHistoryFilter.search || "").toLowerCase();
  const vesselFilter = state.modelHistoryFilter.vessel;
  const categoryFilter = state.modelHistoryFilter.category;

  const filtered = state.modelHistory.filter(item => {
    if (vesselFilter !== "all" && item.vesselType !== vesselFilter) return false;
    if (categoryFilter !== "all" && item.category !== categoryFilter) return false;
    if (!query) return true;

    const searchable = `
      ${item.id} ${item.action} ${item.origin} ${item.destination} 
      ${item.vesselType} ${item.user} ${item.verdict} ${item.notes} ${item.displayDate}
    `.toLowerCase();
    return searchable.includes(query);
  });

  if (filtered.length === 0) {
    return `
      <div class="card-elevation p-10 text-center bg-white rounded-2xl">
        <svg class="w-10 h-10 mx-auto text-slate-300 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
        <h3 class="text-sm font-bold text-slate-700">No matching history entries</h3>
        <p class="text-xs text-slate-400 mt-1">Try changing your search terms or filters.</p>
        <button onclick="clearHistorySearch(); filterHistoryVessel('all'); filterHistoryCategory('all');" class="mt-3 text-xs text-blue-600 hover:underline font-semibold">
          Reset all filters
        </button>
      </div>
    `;
  }

  // Group by DateGroup or DisplayDate (Today, Yesterday, etc.)
  const groups = {};
  filtered.forEach(item => {
    const grp = item.dateGroup || item.displayDate || "Recent Logs";
    if (!groups[grp]) groups[grp] = [];
    groups[grp].push(item);
  });

  return Object.keys(groups).map(groupName => {
    const items = groups[groupName];
    return `
      <div class="mb-8">
        
        <!-- Chrome-Style Date Group Header -->
        <div class="flex items-center gap-2 mb-3">
          <div class="w-2.5 h-2.5 rounded-full bg-purple-500"></div>
          <h3 class="text-xs font-bold text-slate-700 uppercase tracking-wider font-outfit">
            ${groupName}
          </h3>
          <span class="text-[10px] text-slate-400 font-mono">(${items.length} records)</span>
          <div class="flex-1 border-t border-slate-200 ml-2"></div>
        </div>

        <!-- Timeline Entries -->
        <div class="space-y-3 relative pl-3 border-l-2 border-slate-200 ml-1">
          ${items.map(item => renderHistoryItemCard(item)).join('')}
        </div>

      </div>
    `;
  }).join('');
}

function renderHistoryItemCard(item) {
  const isScenario = item.category === "scenario";
  const isVessel = item.category === "vessel";
  const isPort = item.category === "port";

  const categoryBadgeClass = isScenario ? "bg-amber-100 text-amber-800 border-amber-200" :
                             isVessel ? "bg-emerald-100 text-emerald-800 border-emerald-200" :
                             isPort ? "bg-teal-100 text-teal-800 border-teal-200" :
                             "bg-blue-100 text-blue-800 border-blue-200";

  return `
    <div class="card-elevation card-elevation-hover p-4 sm:p-5 bg-white relative transition-all rounded-xl border border-slate-200 group">
      
      <!-- Top Row: Time, Category Pill, User, & Action Controls -->
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2.5 border-b border-slate-100 mb-3">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="text-xs font-mono font-bold text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
            ${item.displayTime}
          </span>
          <span class="text-[10px] text-slate-400">
            (${item.timeAgo || item.displayDate})
          </span>
          <span class="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${categoryBadgeClass}">
            ${item.action}
          </span>
          <span class="text-xs text-slate-500 hidden md:inline">
            \u00b7 <strong class="text-slate-700 font-medium">${item.user}</strong>
          </span>
        </div>

        <!-- Action Buttons (Inspect, Re-run, Delete) -->
        <div class="flex items-center gap-1.5 self-end sm:self-auto">
          <button 
            onclick="openModelDetailModal('${item.id}')" 
            title="Inspect full mathematical details and parameters"
            class="text-xs bg-slate-50 hover:bg-purple-50 text-slate-700 hover:text-purple-700 border border-slate-200 hover:border-purple-200 font-medium px-2.5 py-1.5 rounded-lg transition-colors flex items-center gap-1 shadow-2xs"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>
            <span>Inspect</span>
          </button>
          <button 
            onclick="reRunModelHistoryEntry('${item.id}')" 
            title="Load these parameters into Dashboard model engine"
            class="text-xs bg-blue-50 hover:bg-blue-600 text-blue-700 hover:text-white border border-blue-200 hover:border-blue-600 font-medium px-2.5 py-1.5 rounded-lg transition-colors flex items-center gap-1 shadow-2xs"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
            <span>Re-run</span>
          </button>
          <button 
            onclick="deleteModelHistoryEntry('${item.id}')" 
            title="Delete this history record"
            class="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
          </button>
        </div>
      </div>

      <!-- Middle: Route Arrow & Corridor -->
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-3">
        <div class="flex items-center gap-2 text-sm sm:text-base font-bold text-slate-900 font-outfit flex-wrap">
          <span class="text-blue-700">${item.origin}</span>
          <svg class="w-4 h-4 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
          <span class="text-emerald-700">${item.destination}</span>
          <span class="text-xs font-normal text-slate-400">(${item.destinationState})</span>
        </div>

        <!-- Right Side Highlight Pill: Rate & Total -->
        <div class="flex items-baseline gap-2 shrink-0">
          <div class="text-right">
            <span class="text-base sm:text-lg font-bold text-slate-900 font-outfit">$${item.baseRate.toFixed(2)}</span>
            <span class="text-xs text-slate-500 font-normal">/ Ton</span>
          </div>
          <span class="text-xs font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
            Total: $${(item.totalExpenditure / 1e6).toFixed(2)}M
          </span>
        </div>
      </div>

    </div>
  `;
}

// -------------------------------------------------------------
// 12. SIDEBAR TAB: INFRASTRUCTURE CONSTRAINTS & PORT CAPABILITIES
// -------------------------------------------------------------

const portConstraintsData = [
  { port_id: "visakhapatnam", port_name: "Visakhapatnam (Vizag)", state: "Andhra Pradesh", latitude: 17.686, longitude: 83.218, max_draft_m: 18.0, max_loa_m: 320.0, max_beam_m: 48.0, num_berths: 26, crane_handling_tph: 22000, tide_restriction: false, max_vessel_class: "Capesize", typical_throughput_mt: 72 },
  { port_id: "gangavaram", port_name: "Gangavaram Port", state: "Andhra Pradesh", latitude: 17.633, longitude: 83.221, max_draft_m: 21.0, max_loa_m: 350.0, max_beam_m: 52.0, num_berths: 10, crane_handling_tph: 26000, tide_restriction: false, max_vessel_class: "Capesize", typical_throughput_mt: 58 },
  { port_id: "paradip", port_name: "Paradip Port", state: "Odisha", latitude: 20.316, longitude: 86.611, max_draft_m: 14.5, max_loa_m: 295.0, max_beam_m: 45.0, num_berths: 18, crane_handling_tph: 25000, tide_restriction: false, max_vessel_class: "Capesize", typical_throughput_mt: 138 },
  { port_id: "dhamra", port_name: "Dhamra Port", state: "Odisha", latitude: 20.762, longitude: 86.903, max_draft_m: 17.0, max_loa_m: 300.0, max_beam_m: 46.0, num_berths: 8, crane_handling_tph: 24000, tide_restriction: false, max_vessel_class: "Capesize", typical_throughput_mt: 35 },
  { port_id: "gopalpur", port_name: "Gopalpur Port", state: "Odisha", latitude: 19.267, longitude: 84.900, max_draft_m: 9.0, max_loa_m: 185.0, max_beam_m: 28.0, num_berths: 4, crane_handling_tph: 8000, tide_restriction: false, max_vessel_class: "Handymax", typical_throughput_mt: 8 },
  { port_id: "haldia", port_name: "Haldia Dock Complex", state: "West Bengal", latitude: 22.028, longitude: 88.068, max_draft_m: 8.5, max_loa_m: 210.0, max_beam_m: 31.0, num_berths: 24, crane_handling_tph: 9000, tide_restriction: true, max_vessel_class: "Handysize", typical_throughput_mt: 42 },
  { port_id: "sagar", port_name: "Sagar & Sandheads", state: "West Bengal", latitude: 21.650, longitude: 88.100, max_draft_m: 9.5, max_loa_m: 230.0, max_beam_m: 32.0, num_berths: 6, crane_handling_tph: 10000, tide_restriction: true, max_vessel_class: "Panamax", typical_throughput_mt: 12 }
];

const internationalLoadingPortsData = [
  { country: "Australia", port_name: "Australia \u2014 Newcastle - Kooragang", terminal_operator: "Port Waratah Coal Services (PWCS)", max_loa_m: 300, max_beam_m: 50, max_draft_m: 15.2, handling_rate: "Up to 10,500 tph", handling_rate_num: 10500, max_vessel_class: "Capesize (up to 210,000 DWT)", loading_method: "Fixed berth", notes: "Sailing draft is tide/UKC dependent", source_url: "https://pwcs.com.au" },
  { country: "Australia", port_name: "Australia \u2014 Newcastle - Carrington", terminal_operator: "Port Waratah Coal Services (PWCS)", max_loa_m: 270, max_beam_m: 47, max_draft_m: 12.5, handling_rate: "Up to 2,500 tph per loader", handling_rate_num: 2500, max_vessel_class: "Panamax (up to 180,000 DWT)", loading_method: "Fixed berth", notes: "LOA extendable to 275m with approval", source_url: "https://pwcs.com.au" },
  { country: "Australia", port_name: "Australia \u2014 Newcastle - NCIG", terminal_operator: "Newcastle Coal Infrastructure Group (NCIG)", max_loa_m: 300, max_beam_m: 50, max_draft_m: 13.8, handling_rate: "Up to 10,500 tph", handling_rate_num: 10500, max_vessel_class: "Capesize (min 35,000 DWT)", loading_method: "Fixed berth", notes: "Draft after tide and 10% UKC allowance", source_url: "https://ncig.com.au" },
  { country: "Australia", port_name: "Australia \u2014 Hay Point Coal Terminal", terminal_operator: "North Queensland Bulk Ports (NQBP)", max_loa_m: 300, max_beam_m: 60.9, max_draft_m: 18.6, handling_rate: "4,500-8,400 tph by berth", handling_rate_num: 8400, max_vessel_class: "Capesize (up to 230,000 DWT)", loading_method: "Fixed berth (3 berths)", notes: "Berth pocket depth up to 18.6m", source_url: "https://nqbp.com.au" },
  { country: "Australia", port_name: "Australia \u2014 Dalrymple Bay Coal Terminal", terminal_operator: "DBCT Management", max_loa_m: 320, max_beam_m: 52, max_draft_m: 16.24, handling_rate: "7,200-8,650 tph per loader", handling_rate_num: 8650, max_vessel_class: "Capesize (40,000-220,000 DWT)", loading_method: "Fixed berth (4 berths)", notes: "3 shiploaders system", source_url: "https://dbct.com.au" },
  { country: "Australia", port_name: "Australia \u2014 Abbot Point Coal Terminal", terminal_operator: "North Queensland Bulk Ports (NQBP)", max_loa_m: 300, max_beam_m: 70, max_draft_m: 18.5, handling_rate: "6,000-7,200 tph", handling_rate_num: 7200, max_vessel_class: "Capesize", loading_method: "Fixed berth (2 berths)", notes: "Deepwater offshore berth", source_url: "https://nqbp.com.au" },
  { country: "Indonesia", port_name: "Indonesia \u2014 Taboneo (Banjarmasin anchorage)", terminal_operator: "Various barge operators", max_loa_m: 100, max_beam_m: 40, max_draft_m: 6.4, handling_rate: "600 tph conveyor / 15,000-40,000 t/day", handling_rate_num: 2500, max_vessel_class: "Bulkers via transshipment", loading_method: "Anchorage transshipment", notes: "Ocean vessels loaded via barge/floating crane transshipment", source_url: "https://gem.wiki" },
  { country: "Mozambique", port_name: "Mozambique \u2014 Beira", terminal_operator: "CFM / Cornelder de Mocambique", max_loa_m: 140, max_beam_m: 25, max_draft_m: 7.0, handling_rate: "~6.5 Mt/yr rail feed", handling_rate_num: 1500, max_vessel_class: "Handysize / Offshore transshipment", loading_method: "Fixed pier + offshore transshipment", notes: "Night-navigation limit 140m LOA; channel ~11m", source_url: "https://delagoasl.com" },
  { country: "United States", port_name: "United States \u2014 Norfolk - Lamberts Point Pier 6", terminal_operator: "Norfolk Southern", max_loa_m: 305, max_beam_m: 53, max_draft_m: 15.0, handling_rate: "16,000-20,000 tons/hr", handling_rate_num: 18000, max_vessel_class: "Capesize (>165,000 DWT)", loading_method: "Fixed berth", notes: "High-speed tandem rotary car dumpers", source_url: "https://vamaritime.com" },
  { country: "United States", port_name: "United States \u2014 Newport News - Kinder Morgan Pier IX", terminal_operator: "Kinder Morgan", max_loa_m: 305, max_beam_m: 47, max_draft_m: 15.2, handling_rate: "8,000 tons/hr design", handling_rate_num: 8000, max_vessel_class: "Capesize", loading_method: "Fixed berth", notes: "50ft MLW channel; air draft 19.8m", source_url: "https://vamaritime.com" },
  { country: "United States", port_name: "United States \u2014 Baltimore - CNX Marine Terminal (Curtis Bay)", terminal_operator: "CNX Resources", max_loa_m: 381, max_beam_m: 53, max_draft_m: 14.3, handling_rate: "7,000 short tons/hr", handling_rate_num: 7000, max_vessel_class: "Panamax/Capesize", loading_method: "Fixed berth", notes: "Air draft 16.8m (55ft)", source_url: "https://moranshipping.com" },
  { country: "Russia", port_name: "Russia \u2014 Nakhodka", terminal_operator: "Nakhodka Commercial Sea Port", max_loa_m: 199, max_beam_m: 30, max_draft_m: 11.0, handling_rate: "~12 Mtpa aggregate", handling_rate_num: 2000, max_vessel_class: "Handysize/Handymax (~35,000 DWT)", loading_method: "Fixed berth (multiple terminals)", notes: "Coal handling split across several smaller terminals", source_url: "https://gem.wiki" },
  { country: "Russia", port_name: "Russia \u2014 Vostochny", terminal_operator: "Vostochny Port (VPK)", max_loa_m: 300, max_beam_m: 48, max_draft_m: 16.5, handling_rate: "4 shiploaders x ~3,000 tph", handling_rate_num: 12000, max_vessel_class: "Capesize (~180,000 DWT)", loading_method: "Fixed berth", notes: "Planned increase to 18-19m; fairway depth up to 22m", source_url: "https://portnews.ru" }
];

let selectedInfraOrigin = "paradip";
let selectedInfraDest = "Australia \u2014 Newcastle - Kooragang";
let selectedInfraVessel = "Capesize";
let selectedInfraDatasetTab = "indian";
let infraSearchQuery = "";

function getIndianPortObj(query) {
  if (!query) return portConstraintsData[0];
  const q = query.toLowerCase();
  const found = portConstraintsData.find(p => 
    p.port_id.toLowerCase() === q ||
    p.port_name.toLowerCase().includes(q) ||
    q.includes(p.port_name.toLowerCase()) ||
    q.includes(p.port_id.toLowerCase())
  );
  return found || portConstraintsData[0];
}

function getIntlPortObj(query) {
  if (!query) return internationalLoadingPortsData[0];
  const q = query.toLowerCase();
  const found = internationalLoadingPortsData.find(p => 
    p.port_name.toLowerCase() === q ||
    p.port_name.toLowerCase().includes(q) ||
    q.includes(p.port_name.toLowerCase().replace("australia \u2014 ", "").replace("indonesia \u2014 ", "").replace("mozambique \u2014 ", "").replace("russia \u2014 ", "").replace("united states \u2014 ", ""))
  );
  return found || internationalLoadingPortsData[0];
}

function renderInfraConstraintsView() {
  const container = document.getElementById("dynamicViewContainer");
  if (!container) return;

  const p1 = getIndianPortObj(selectedInfraOrigin);
  const p2 = getIntlPortObj(selectedInfraDest);

  const filteredIndian = portConstraintsData.filter(p => 
    !infraSearchQuery || 
    p.port_name.toLowerCase().includes(infraSearchQuery.toLowerCase()) || 
    p.state.toLowerCase().includes(infraSearchQuery.toLowerCase()) ||
    p.max_vessel_class.toLowerCase().includes(infraSearchQuery.toLowerCase())
  );

  const filteredIntl = internationalLoadingPortsData.filter(p => 
    !infraSearchQuery || 
    p.port_name.toLowerCase().includes(infraSearchQuery.toLowerCase()) || 
    p.country.toLowerCase().includes(infraSearchQuery.toLowerCase()) ||
    p.terminal_operator.toLowerCase().includes(infraSearchQuery.toLowerCase())
  );

  container.innerHTML = `
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      
      <!-- Top Title & Navigation Bar -->
      <div class="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <span class="text-xs font-semibold text-cyan-700 uppercase tracking-wider bg-cyan-50 px-2.5 py-1 rounded-md border border-cyan-200">
            Port Infrastructure & Constraint Comparison
          </span>
          <h2 class="text-2xl font-bold text-slate-900 mt-2 font-outfit">
            Port Infrastructure Constraints Analysis
          </h2>
          <p class="text-sm text-slate-500 mt-1">
            Compare maximum LOA (Length Overall) and Draft limits between Indian East Coast ports and International loading terminals.
          </p>
        </div>
        <button onclick="state.activeTab='dashboard'; renderApp();" class="text-xs bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium px-3 py-2 rounded-lg transition-colors shadow-sm self-start md:self-auto">
          \u2190 Back to Route Query
        </button>
      </div>

      <!-- INTERACTIVE ROUTE & PORT SELECTION BAR -->
      <div class="card-elevation bg-white rounded-2xl p-5 mb-6 border border-slate-200 shadow-sm">
        <div class="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
          
          <!-- Select Indian Discharge Port (Port 1) -->
          <div class="md:col-span-5 bg-slate-50 p-3.5 rounded-xl border border-slate-200">
            <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">
              Indian Discharge Port (Port 1)
            </label>
            <select id="infraOriginSelect" onchange="selectedInfraOrigin=this.value; state.query.origin=this.options[this.selectedIndex].text; renderInfraConstraintsView();" class="bg-white text-sm font-bold text-slate-800 w-full p-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-cyan-500 cursor-pointer">
              ${portConstraintsData.map(p => `
                <option value="${p.port_id}" ${p.port_id === p1.port_id ? 'selected' : ''}>
                  ${p.port_name} (${p.state})
                </option>
              `).join('')}
            </select>
          </div>

          <!-- Corridor Arrow -->
          <div class="md:col-span-2 flex items-center justify-center text-slate-400 font-bold">
            <div class="flex items-center gap-2 bg-slate-100 px-3 py-1.5 rounded-full text-xs text-cyan-700 font-semibold border border-slate-200">
              <span>Compare Route</span>
              <svg class="w-4 h-4 text-cyan-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
            </div>
          </div>

          <!-- Select International Loading Port (Port 2) -->
          <div class="md:col-span-5 bg-slate-50 p-3.5 rounded-xl border border-slate-200">
            <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">
              International Loading Port (Port 2)
            </label>
            <select id="infraDestSelect" onchange="selectedInfraDest=this.value; state.query.destination=this.value; renderInfraConstraintsView();" class="bg-white text-sm font-bold text-slate-800 w-full p-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-cyan-500 cursor-pointer">
              ${internationalLoadingPortsData.map(p => `
                <option value="${p.port_name}" ${p.port_name === p2.port_name ? 'selected' : ''}>
                  ${p.port_name}
                </option>
              `).join('')}
            </select>
          </div>

        </div>
      </div>

      <!-- FULL DATASET MATRIX EXPLORER TABLE (port_constraints & international-loading-ports) -->
      <div class="card-elevation bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
        
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h3 class="font-bold text-slate-900 font-outfit text-lg">Full Port Infrastructure Dataset Explorer</h3>
            <p class="text-xs text-slate-500">Datasets: port_constraints.csv & international_loading_ports.csv</p>
          </div>

          <!-- Controls: Tab Switch + Search -->
          <div class="flex flex-wrap items-center gap-3">
            
            <!-- Dataset Tab Switcher -->
            <div class="flex p-1 bg-slate-100 rounded-xl border border-slate-200 text-xs">
              <button onclick="selectedInfraDatasetTab='indian'; renderInfraConstraintsView();" class="px-3 py-1.5 rounded-lg font-semibold transition-colors ${selectedInfraDatasetTab === 'indian' ? 'bg-white text-cyan-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'}">
                Indian East Coast Ports (${portConstraintsData.length})
              </button>
              <button onclick="selectedInfraDatasetTab='international'; renderInfraConstraintsView();" class="px-3 py-1.5 rounded-lg font-semibold transition-colors ${selectedInfraDatasetTab === 'international' ? 'bg-white text-emerald-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'}">
                International Loading Ports (${internationalLoadingPortsData.length})
              </button>
            </div>

            <!-- Search Filter Input -->
            <div class="relative">
              <input type="text" placeholder="Search port, state, or operator..." value="${infraSearchQuery}" oninput="infraSearchQuery=this.value; renderInfraConstraintsView();" class="text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 pl-8 text-slate-800 focus:outline-none focus:ring-2 focus:ring-cyan-500 w-48 sm:w-56" />
              <svg class="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
            </div>

          </div>
        </div>

        <!-- TABLE SECTION -->
        <div class="overflow-x-auto border border-slate-200 rounded-xl">
          ${selectedInfraDatasetTab === 'indian' ? `
            <!-- Indian Ports Table -->
            <table class="w-full text-left border-collapse text-xs">
              <thead class="bg-slate-50 border-b border-slate-200 text-[11px] text-slate-500 uppercase font-bold tracking-wider">
                <tr>
                  <th class="p-3">Port Name</th>
                  <th class="p-3">State</th>
                  <th class="p-3 text-right">Max Draft (m)</th>
                  <th class="p-3 text-right">Max LOA (m)</th>
                  <th class="p-3 text-right">Max Beam (m)</th>
                  <th class="p-3 text-center">Berths</th>
                  <th class="p-3 text-right">Crane Handling (TPH)</th>
                  <th class="p-3 text-center">Tide Restricted</th>
                  <th class="p-3">Max Vessel Class</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100 font-medium text-slate-700">
                ${filteredIndian.map(p => `
                  <tr class="hover:bg-cyan-50/40 transition-colors ${p.port_id === p1.port_id ? 'bg-cyan-50/80 font-bold text-cyan-900' : ''}">
                    <td class="p-3 flex items-center gap-2">
                      <span class="w-2 h-2 rounded-full ${p.port_id === p1.port_id ? 'bg-cyan-600' : 'bg-slate-300'}"></span>
                      <span>${p.port_name}</span>
                    </td>
                    <td class="p-3 text-slate-500">${p.state}</td>
                    <td class="p-3 text-right font-bold ${p.max_draft_m < 12 ? 'text-rose-600' : 'text-slate-900'}">${p.max_draft_m} m</td>
                    <td class="p-3 text-right font-bold text-slate-900">${p.max_loa_m} m</td>
                    <td class="p-3 text-right text-slate-600">${p.max_beam_m} m</td>
                    <td class="p-3 text-center text-slate-600">${p.num_berths}</td>
                    <td class="p-3 text-right font-bold text-slate-900">${p.crane_handling_tph.toLocaleString()}</td>
                    <td class="p-3 text-center">
                      <span class="px-2 py-0.5 rounded text-[10px] font-bold ${p.tide_restriction ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'}">
                        ${p.tide_restriction ? 'Yes' : 'No'}
                      </span>
                    </td>
                    <td class="p-3">
                      <span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-700">
                        ${p.max_vessel_class}
                      </span>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          ` : `
            <!-- International Ports Table -->
            <table class="w-full text-left border-collapse text-xs">
              <thead class="bg-slate-50 border-b border-slate-200 text-[11px] text-slate-500 uppercase font-bold tracking-wider">
                <tr>
                  <th class="p-3">Country & Port Name</th>
                  <th class="p-3">Terminal Operator</th>
                  <th class="p-3 text-right">Max Draft (m)</th>
                  <th class="p-3 text-right">Max LOA (m)</th>
                  <th class="p-3 text-right">Max Beam (m)</th>
                  <th class="p-3">Handling Rate</th>
                  <th class="p-3">Loading Method</th>
                  <th class="p-3">Max Vessel Class</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100 font-medium text-slate-700">
                ${filteredIntl.map(p => `
                  <tr class="hover:bg-emerald-50/40 transition-colors ${p.port_name === p2.port_name ? 'bg-emerald-50/80 font-bold text-emerald-900' : ''}">
                    <td class="p-3 flex items-center gap-2">
                      <span class="w-2 h-2 rounded-full ${p.port_name === p2.port_name ? 'bg-emerald-600' : 'bg-slate-300'}"></span>
                      <span>${p.port_name}</span>
                    </td>
                    <td class="p-3 text-slate-500">${p.terminal_operator}</td>
                    <td class="p-3 text-right font-bold ${p.max_draft_m < 12 ? 'text-rose-600' : 'text-slate-900'}">${p.max_draft_m} m</td>
                    <td class="p-3 text-right font-bold text-slate-900">${p.max_loa_m} m</td>
                    <td class="p-3 text-right text-slate-600">${p.max_beam_m} m</td>
                    <td class="p-3 font-semibold text-slate-800">${p.handling_rate}</td>
                    <td class="p-3 text-slate-600">${p.loading_method}</td>
                    <td class="p-3">
                      <span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                        ${p.max_vessel_class}
                      </span>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          `}
        </div>

      </div>

    </div>
  `;
}
