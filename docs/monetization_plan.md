# 🧩 FMU Gateway — First Revenue Plan (v1.0)

**Objective:**  
Generate first real revenue from FMU Gateway within 7 days by enabling pay-per-simulation microtransactions through Stripe.

**Goal:**  
✅ Publicly accessible hosted API  
✅ Stripe live payments working  
✅ At least 1 paid simulation completed

---

## 🔹 Phase 1 — Launch Pay-Per-Simulation MVP

### 🎯 Goal
Enable Stripe payments and run the first FMU simulation for a paying user.

### ✅ Deliverables
- Public `/simulate` endpoint (Fly.io or Render)
- Stripe checkout flow working (redirect + token validation)
- README + landing page updated with payment instructions
- First Stripe transaction confirmed

### 🧠 Tasks

| ID | Task | Owner | Description / Notes | ETA |
|----|------|--------|---------------------|-----|
| 1.1 | **Enable Stripe** | Dev | Set `STRIPE_ENABLED=True` in `.env` and ensure API keys loaded from environment variables | Day 1 |
| 1.2 | **Add /pay endpoint** | Dev | Implement endpoint to create Stripe Checkout session → returns `checkout_url` | Day 1 |
| 1.3 | **Integrate 402 flow** | Dev | Update `/simulate` to return 402 + Stripe payment link when no valid payment token provided | Day 2 |
| 1.4 | **Store payment tokens** | Dev | On successful Stripe webhook, issue a short-lived JWT or session token tied to the paid simulation | Day 2 |
| 1.5 | **Test end-to-end flow** | QA / Agent | Upload small FMU, pay via Stripe test mode, confirm simulation result + Stripe payment success | Day 3 |
| 1.6 | **Deploy to Fly.io** | DevOps | `fly deploy` with `STRIPE_ENABLED=True`, `STRIPE_SECRET_KEY`, `STRIPE_PUBLIC_KEY` | Day 3 |
| 1.7 | **Update README.md** | Docs | Add: pricing, curl example, Stripe instructions, “Run a Simulation for £1” link | Day 4 |
| 1.8 | **Create Landing Page (1-pager)** | Marketing | Simple page (Carrd / Notion / WordPress) linking to GitHub & simulate API | Day 4 |
| 1.9 | **Post soft launch on LinkedIn / Reddit** | Kev | Share: “FMU Gateway — run any FMU online for £1 per simulation.” Include example and link | Day 5 |
| 1.10 | **Track first payment** | Ops | Confirm Stripe dashboard shows at least 1 live transaction | Day 7 |

---

## 🔹 Phase 2 — Add Prepaid Credit System (Optional but Fast Upsell)

### 🎯 Goal
Let users buy multiple simulations upfront and avoid paying each time.

### ✅ Deliverables
- `/buy-credits` endpoint
- `users` + `credits` table in SQLite
- Token deduction logic before each `/simulate`

### 🧠 Tasks

| ID | Task | Owner | Description / Notes | ETA |
|----|------|--------|---------------------|-----|
| 2.1 | **Add database table** | Dev | `user_id`, `credits_remaining`, `stripe_customer_id` | +1 day |
| 2.2 | **Create /buy-credits endpoint** | Dev | Stripe checkout → adds 10 credits per £10 purchase | +1 day |
| 2.3 | **Integrate credit logic** | Dev | Each simulation consumes 1 credit | +1 day |
| 2.4 | **Update README** | Docs | Explain how to purchase credits and run simulations | +1 day |

---

## 🔹 Phase 3 — Promote & Scale Traffic

### 🎯 Goal
Get first 10 paid simulations; build visibility in the AI + engineering ecosystem.

### ✅ Deliverables
- Public announcement
- Free trials for influencers / early adopters
- Simple analytics tracking usage

### 🧠 Tasks

| ID | Task | Owner | Description / Notes | ETA |
|----|------|--------|---------------------|-----|
| 3.1 | **Create short promo post** | Marketing | LinkedIn & X: “Run Modelica/Simulink FMUs instantly — pay per run.” | Day 7 |
| 3.2 | **Contact niche users** | Kev | DM 3–5 engineering AI tool builders or simulation groups | Day 7 |
| 3.3 | **Add basic analytics** | Dev | Count total simulations + total revenue in SQLite | Day 7 |
| 3.4 | **Publish Medium article / Devpost** | Marketing | “Building a Micro-Billing Simulation API in 5 Days” | Day 8 |

---

## 🔹 Phase 4 — Measure, Learn, Iterate

### 🎯 Goal
Collect data, validate demand, prepare for subscriptions or a paid FMU library.

### ✅ Metrics
- # of simulations run  
- # of paid users  
- Conversion rate from free → paid  
- Cost per simulation (compute vs. revenue)

### 🧠 Tasks

| ID | Task | Owner | Description / Notes | ETA |
|----|------|--------|---------------------|-----|
| 4.1 | **Collect metrics** | Ops | Log simulation counts, revenue, cost | Ongoing |
| 4.2 | **Adjust pricing** | Kev | Tune price point once usage patterns known | Ongoing |
| 4.3 | **Identify repeat users** | Ops | Contact them for feedback → possible enterprise leads | Ongoing |

---

## 🪙 Suggested Starting Price

| Tier | Price | Description |
|------|--------|-------------|
| **Single Simulation** | £1 / run | Pay-as-you-go, via Stripe checkout |
| **Credit Pack (10 runs)** | £8 | Discounted prepaid credits |
| **Enterprise Pilot** | £100 / month | 250 runs + email support |

---

## 🧭 Recommended Tools / Agents to Use

| Tool / Agent | Role | Example Prompt |
|---------------|------|----------------|
| **Cursor (Grok4 Fast)** | Write Stripe checkout code & API patches | “Implement Stripe Checkout in FastAPI for /simulate, returning 402 on unpaid calls.” |
| **GitHub Copilot / Codex** | Auto-generate unit tests | “Create pytest cases for FMU upload and simulation payment flow.” |
| **Fly.io CLI Agent** | Deploy Gateway with env vars | `fly deploy --env STRIPE_ENABLED=True` |
| **Stripe Dashboard Agent** | Monitor payments and usage | “List all successful charges in last 24 h.” |
| **Marketing Agent** | Create LinkedIn / Reddit post | “Write short launch post for £1 per simulation FMU Gateway.” |

---

## 🏁 Success Definition

✅ Live gateway reachable at public URL  
✅ Stripe payments verified working  
✅ At least one completed **paid** simulation  
✅ Post-launch traction (10 simulations total)  
✅ Ready foundation for subscriptions and marketplace
