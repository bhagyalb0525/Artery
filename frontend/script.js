// ============================================================
// Artery — Digital Art Marketplace frontend logic
// Talks to the FastAPI backend over plain fetch() calls.
// ============================================================

// Change this to your deployed backend URL once you go live, e.g.
// const API_BASE = "https://your-app-name.onrender.com";
const API_BASE = "http://127.0.0.1:8080";

// ---------- State ----------
let token = localStorage.getItem("art_token") || null;
let userName = localStorage.getItem("art_user_name") || null;
let currentCategory = "all";
let currentSearch = "";
let authMode = "login"; // or "signup"
let activeArtwork = null; // currently open in detail modal

// ---------- DOM refs ----------
const $ = (id) => document.getElementById(id);

const els = {
  loginBtn: $("loginBtn"),
  signupBtn: $("signupBtn"),
  logoutBtn: $("logoutBtn"),
  uploadBtn: $("uploadBtn"),
  heroUploadBtn: $("heroUploadBtn"),
  userGreeting: $("userGreeting"),

  authModal: $("authModal"),
  authForm: $("authForm"),
  authTitle: $("authTitle"),
  authSubmitBtn: $("authSubmitBtn"),
  authSwitchText: $("authSwitchText"),
  authSwitchLink: $("authSwitchLink"),
  authError: $("authError"),
  nameGroup: $("nameGroup"),
  nameInput: $("nameInput"),
  emailInput: $("emailInput"),
  passwordInput: $("passwordInput"),

  uploadModal: $("uploadModal"),
  uploadForm: $("uploadForm"),
  uploadError: $("uploadError"),

  detailModal: $("detailModal"),
  detailImage: $("detailImage"),
  detailTitle: $("detailTitle"),
  detailArtist: $("detailArtist"),
  detailDescription: $("detailDescription"),
  detailPrice: $("detailPrice"),
  detailCategory: $("detailCategory"),
  detailBuyBtn: $("detailBuyBtn"),
  detailMsg: $("detailMsg"),

  artGrid: $("artGrid"),
  emptyState: $("emptyState"),
  searchInput: $("searchInput"),
  categoryFilters: $("categoryFilters"),

  galleryView: $("galleryView"),
  myArtView: $("myArtView"),
  myPurchasesView: $("myPurchasesView"),
  myArtGrid: $("myArtGrid"),
  myArtEmpty: $("myArtEmpty"),
  myPurchasesGrid: $("myPurchasesGrid"),
  myPurchasesEmpty: $("myPurchasesEmpty"),

  navLinks: document.querySelectorAll(".nav-links a"),
  hamburger: $("hamburger"),
  navLinksWrap: document.querySelector(".nav-links"),

  toast: $("toast"),
};

// ============================================================
// Helpers
// ============================================================

function showToast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.classList.toggle("error", isError);
  els.toast.classList.remove("hidden");
  requestAnimationFrame(() => els.toast.classList.add("show"));
  setTimeout(() => {
    els.toast.classList.remove("show");
    setTimeout(() => els.toast.classList.add("hidden"), 250);
  }, 2600);
}

function authHeaders() {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function formatPrice(price) {
  return `₹${Number(price).toLocaleString("en-IN")}`;
}

function updateAuthUI() {
  const loggedIn = Boolean(token);
  els.loginBtn.classList.toggle("hidden", loggedIn);
  els.signupBtn.classList.toggle("hidden", loggedIn);
  els.logoutBtn.classList.toggle("hidden", !loggedIn);
  els.uploadBtn.classList.toggle("hidden", !loggedIn);
  els.userGreeting.classList.toggle("hidden", !loggedIn);
  if (loggedIn) els.userGreeting.textContent = `Hi, ${userName}`;
}

function openModal(modal) {
  modal.classList.remove("hidden");
}

function closeModal(modal) {
  modal.classList.add("hidden");
}

function switchView(viewName) {
  els.galleryView.classList.toggle("hidden", viewName !== "gallery");
  els.myArtView.classList.toggle("hidden", viewName !== "my-art");
  els.myPurchasesView.classList.toggle("hidden", viewName !== "my-purchases");

  els.navLinks.forEach((link) => {
    link.classList.toggle("active", link.dataset.view === viewName);
  });

  if (viewName === "my-art") loadMyArtworks();
  if (viewName === "my-purchases") loadMyPurchases();
}

// ============================================================
// Gallery — browse artworks (public)
// ============================================================

async function loadGallery() {
  try {
    const params = new URLSearchParams();
    if (currentCategory !== "all") params.set("category", currentCategory);
    if (currentSearch) params.set("search", currentSearch);

    const res = await fetch(`${API_BASE}/artworks?${params.toString()}`);
    if (!res.ok) throw new Error("Failed to load gallery");
    const artworks = await res.json();
    renderArtGrid(artworks, els.artGrid, els.emptyState, false);
  } catch (err) {
    showToast("Could not load artworks. Is the backend running?", true);
    console.error(err);
  }
}

function renderArtGrid(artworks, gridEl, emptyEl, isOwner) {
  gridEl.innerHTML = "";
  emptyEl.classList.toggle("hidden", artworks.length > 0);

  artworks.forEach((art) => {
    const soldOut = art.stock <= 0;
    const card = document.createElement("div");
    card.className = `art-card${soldOut ? " sold-out" : ""}`;
    card.innerHTML = `
      <div class="thumb-wrap">
        <img src="${API_BASE}${art.image_path}" alt="${escapeHtml(art.title)}" loading="lazy" />
        ${soldOut ? `<div class="sold-badge">Sold Out</div>` : ""}
      </div>
      <div class="art-card-body">
        <h3 class="art-card-title">${escapeHtml(art.title)}</h3>
        <p class="art-card-artist">${art.artist_name ? "by " + escapeHtml(art.artist_name) : ""}</p>
        <div class="art-card-footer">
          <span class="art-card-price">${soldOut ? '<span style="color:var(--text-muted)">Sold Out</span>' : formatPrice(art.price)}</span>
          <span class="art-card-category">${escapeHtml(art.category)}</span>
        </div>
        ${art.stock > 1 ? `<p class="art-card-stock">${art.stock} left</p>` : ""}
        ${isOwner ? `<button class="art-card-delete" data-id="${art.id}">Delete</button>` : ""}
      </div>
    `;

    card.querySelector(".thumb-wrap").addEventListener("click", () => openDetail(art));
    card.querySelector(".art-card-title").addEventListener("click", () => openDetail(art));

    if (isOwner) {
      card.querySelector(".art-card-delete").addEventListener("click", async (e) => {
        e.stopPropagation();
        await deleteArtwork(art.id);
      });
    }

    gridEl.appendChild(card);
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

// ============================================================
// Artwork detail + buy
// ============================================================

function openDetail(art) {
  activeArtwork = art;
  const soldOut = art.stock <= 0;
  els.detailImage.src = `${API_BASE}${art.image_path}`;
  els.detailImage.alt = art.title;
  els.detailTitle.textContent = art.title;
  els.detailArtist.textContent = art.artist_name ? `by ${art.artist_name}` : "";
  els.detailDescription.textContent = art.description || "No description provided.";
  els.detailPrice.textContent = formatPrice(art.price);
  els.detailCategory.textContent = art.category;
  els.detailMsg.classList.add("hidden");

  // Stock indicator
  const existingStock = document.getElementById("detailStock");
  if (existingStock) existingStock.remove();
  if (art.stock > 0) {
    const stockEl = document.createElement("p");
    stockEl.id = "detailStock";
    stockEl.style.cssText = "font-size:0.82rem;color:var(--text-muted);margin:0.3rem 0 0;";
    stockEl.textContent = art.stock === 1 ? "Only 1 left" : `${art.stock} copies available`;
    els.detailArtist.after(stockEl);
  }

  // Disable buy button if sold out
  els.detailBuyBtn.disabled = soldOut;
  els.detailBuyBtn.textContent = soldOut ? "Sold Out" : "Buy now";
  els.detailBuyBtn.style.opacity = soldOut ? "0.5" : "1";

  openModal(els.detailModal);
}

els.detailBuyBtn.addEventListener("click", async () => {
  if (!activeArtwork) return;
  if (!token) {
    closeModal(els.detailModal);
    openAuth("login");
    showToast("Log in first to make a purchase.");
    return;
  }
  await startRazorpayCheckout(activeArtwork);
});

// ============================================================
// Razorpay checkout flow
//
// 1. Ask our backend to create a Razorpay order for this artwork.
// 2. Open Razorpay's hosted checkout popup with that order_id.
// 3. On success, Razorpay hands us a payment_id + signature.
// 4. Send those to our backend to verify — the backend re-checks the
//    signature itself using the secret key, so we never just trust
//    whatever the popup tells the browser.
// ============================================================

async function startRazorpayCheckout(artwork) {
  els.detailBuyBtn.disabled = true;
  els.detailBuyBtn.textContent = "Starting checkout…";

  try {
    // Step 1: create the order on our backend
    const checkoutRes = await fetch(`${API_BASE}/artworks/${artwork.id}/checkout`, {
      method: "POST",
      headers: authHeaders(),
    });
    const order = await checkoutRes.json();
    if (!checkoutRes.ok) throw new Error(order.detail || "Could not start checkout");

    // Step 2: open Razorpay's popup
    const options = {
      key: order.key_id,
      amount: order.amount,
      currency: order.currency,
      name: "Artery",
      description: order.artwork_title,
      order_id: order.order_id,
      prefill: {
        name: order.buyer_name,
        email: order.buyer_email,
      },
      theme: { color: "#e8753c" },
      handler: async function (response) {
        // Step 3 + 4: Razorpay calls this only after a successful payment.
        // `response` contains razorpay_payment_id, razorpay_order_id, razorpay_signature.
        await verifyPaymentOnServer(response, artwork);
      },
      modal: {
        ondismiss: function () {
          // User closed the popup without paying — just reset the button.
          els.detailBuyBtn.disabled = false;
          els.detailBuyBtn.textContent = "Buy now";
        },
      },
    };

    const rzp = new Razorpay(options);
    rzp.open();
  } catch (err) {
    els.detailMsg.classList.remove("hidden");
    els.detailMsg.style.color = "var(--error)";
    els.detailMsg.textContent = err.message;
  } finally {
    els.detailBuyBtn.disabled = false;
    els.detailBuyBtn.textContent = "Buy now";
  }
}

async function verifyPaymentOnServer(razorpayResponse, artwork) {
  try {
    const res = await fetch(`${API_BASE}/payments/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        razorpay_order_id: razorpayResponse.razorpay_order_id,
        razorpay_payment_id: razorpayResponse.razorpay_payment_id,
        razorpay_signature: razorpayResponse.razorpay_signature,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Payment verification failed");

    els.detailMsg.classList.remove("hidden");
    els.detailMsg.style.color = "var(--success)";
    els.detailMsg.textContent = `Payment successful! You now own "${artwork.title}".`;
    showToast("Payment successful!");
  } catch (err) {
    els.detailMsg.classList.remove("hidden");
    els.detailMsg.style.color = "var(--error)";
    els.detailMsg.textContent = err.message;
    showToast("Payment could not be verified.", true);
  }
}

// ============================================================
// Auth — signup / login / logout
// ============================================================

function openAuth(mode) {
  authMode = mode;
  els.authError.classList.add("hidden");
  els.authForm.reset();
  if (mode === "signup") {
    els.authTitle.textContent = "Create your account";
    els.nameGroup.classList.remove("hidden");
    els.authSubmitBtn.textContent = "Sign up";
    els.authSwitchText.textContent = "Already have an account?";
    els.authSwitchLink.textContent = "Log in";
  } else {
    els.authTitle.textContent = "Log in";
    els.nameGroup.classList.add("hidden");
    els.authSubmitBtn.textContent = "Log in";
    els.authSwitchText.textContent = "Don't have an account?";
    els.authSwitchLink.textContent = "Sign up";
  }
  openModal(els.authModal);
}

els.loginBtn.addEventListener("click", () => openAuth("login"));
els.signupBtn.addEventListener("click", () => openAuth("signup"));
els.heroUploadBtn.addEventListener("click", () => {
  if (token) openModal(els.uploadModal);
  else {
    openAuth("signup");
    showToast("Create an account to start selling your art.");
  }
});

els.authSwitchLink.addEventListener("click", (e) => {
  e.preventDefault();
  openAuth(authMode === "login" ? "signup" : "login");
});

els.authForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  els.authError.classList.add("hidden");

  const email = els.emailInput.value.trim();
  const password = els.passwordInput.value;
  const name = els.nameInput.value.trim();

  const endpoint = authMode === "signup" ? "/signup" : "/login";
  const payload = authMode === "signup" ? { name, email, password } : { email, password };

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Something went wrong");

    token = data.access_token;
    userName = data.name;
    localStorage.setItem("art_token", token);
    localStorage.setItem("art_user_name", userName);

    updateAuthUI();
    closeModal(els.authModal);
    showToast(authMode === "signup" ? `Welcome, ${userName}!` : `Welcome back, ${userName}!`);
  } catch (err) {
    els.authError.textContent = err.message;
    els.authError.classList.remove("hidden");
  }
});

els.logoutBtn.addEventListener("click", () => {
  token = null;
  userName = null;
  localStorage.removeItem("art_token");
  localStorage.removeItem("art_user_name");
  updateAuthUI();
  switchView("gallery");
  showToast("Logged out.");
});

// ============================================================
// Upload artwork
// ============================================================

els.uploadBtn.addEventListener("click", () => openModal(els.uploadModal));

els.uploadForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  els.uploadError.classList.add("hidden");

  const formData = new FormData();
  formData.append("title", $("artTitle").value.trim());
  formData.append("description", $("artDescription").value.trim());
  formData.append("price", $("artPrice").value);
  formData.append("category", $("artCategory").value);
  formData.append("stock", $("artStock").value || "1");
  formData.append("image", $("artImage").files[0]);

  try {
    const res = await fetch(`${API_BASE}/artworks`, {
      method: "POST",
      headers: authHeaders(), // do NOT set Content-Type — browser sets multipart boundary
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");

    closeModal(els.uploadModal);
    els.uploadForm.reset();
    showToast("Artwork published!");
    loadGallery();
  } catch (err) {
    els.uploadError.textContent = err.message;
    els.uploadError.classList.remove("hidden");
  }
});

async function deleteArtwork(id) {
  if (!confirm("Delete this artwork? This cannot be undone.")) return;
  try {
    const res = await fetch(`${API_BASE}/artworks/${id}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Delete failed");
    showToast("Artwork deleted.");
    loadMyArtworks();
  } catch (err) {
    showToast(err.message, true);
  }
}

// ============================================================
// My Art / My Purchases
// ============================================================

async function loadMyArtworks() {
  if (!token) return;
  try {
    const res = await fetch(`${API_BASE}/my-artworks`, { headers: authHeaders() });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to load");
    renderArtGrid(data, els.myArtGrid, els.myArtEmpty, true);
  } catch (err) {
    showToast(err.message, true);
  }
}

async function loadMyPurchases() {
  if (!token) return;
  try {
    const res = await fetch(`${API_BASE}/my-purchases`, { headers: authHeaders() });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to load");

    els.myPurchasesGrid.innerHTML = "";
    els.myPurchasesEmpty.classList.toggle("hidden", data.length > 0);

    data.forEach((p) => {
      const card = document.createElement("div");
      card.className = "art-card";
      card.innerHTML = `
        <div class="thumb-wrap">
          <img src="${API_BASE}${p.image_path}" alt="${escapeHtml(p.title)}" loading="lazy" />
        </div>
        <div class="art-card-body">
          <h3 class="art-card-title">${escapeHtml(p.title)}</h3>
          <div class="art-card-footer">
            <span class="art-card-price">${formatPrice(p.price)}</span>
          </div>
        </div>
      `;
      els.myPurchasesGrid.appendChild(card);
    });
  } catch (err) {
    showToast(err.message, true);
  }
}

// ============================================================
// Search + filters
// ============================================================

let searchDebounce;
els.searchInput.addEventListener("input", (e) => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => {
    currentSearch = e.target.value.trim();
    loadGallery();
  }, 350);
});

els.categoryFilters.addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
  chip.classList.add("active");
  currentCategory = chip.dataset.category;
  loadGallery();
});

// ============================================================
// Nav + modal wiring
// ============================================================

els.navLinks.forEach((link) => {
  link.addEventListener("click", (e) => {
    e.preventDefault();
    const view = link.dataset.view;
    if ((view === "my-art" || view === "my-purchases") && !token) {
      openAuth("login");
      showToast("Log in to view this page.");
      return;
    }
    switchView(view);
    els.navLinksWrap.classList.remove("open");
  });
});

els.hamburger.addEventListener("click", () => {
  els.navLinksWrap.classList.toggle("open");
});

document.querySelectorAll("[data-close]").forEach((btn) => {
  btn.addEventListener("click", () => closeModal($(btn.dataset.close)));
});

document.querySelectorAll(".modal-overlay").forEach((overlay) => {
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) closeModal(overlay);
  });
});

// ============================================================
// Init
// ============================================================

updateAuthUI();
loadGallery();