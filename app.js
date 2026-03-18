const { useEffect, useState } = React;
const html = htm.bind(React.createElement);

const trustItems = [
  {
    title: "Mobile verification",
    body: "Every account is phone-verified so activity creators always have a reachable participant list.",
  },
  {
    title: "ID badges",
    body: "College or workplace verification adds a visible trust layer for higher-confidence meetups.",
  },
  {
    title: "Controlled messaging",
    body: "No open-ended DMs. Communication stays within the activity context until participants are approved.",
  },
  {
    title: "Reports & blocking",
    body: "One-tap reporting and blocking help protect the community in real time.",
  },
  {
    title: "Limited group size",
    body: "Smaller, curated groups improve safety, reliability, and the quality of the experience.",
  },
  {
    title: "Reputation score",
    body: "Reliable participation builds a stronger score, which improves match quality over time.",
  },
];

const roadmapItems = [
  "AI smart suggestions for better activity recommendations",
  "Real-time city activity maps and heat zones",
  "Corporate team-building and office networking mode",
  "Premium clans for verified enthusiasts and early access",
];

async function apiFetch(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Something went wrong.");
  }

  return payload;
}

function initials(name) {
  return name
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function formatTime(time) {
  const [hour, minute] = String(time || "06:00")
    .split(":")
    .map(Number);
  const suffix = hour >= 12 ? "PM" : "AM";
  const normalized = hour % 12 || 12;
  return `${normalized}:${String(minute).padStart(2, "0")} ${suffix}`;
}

function formatTimestamp(timestamp) {
  const value = new Date(timestamp);
  return value.toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formFromActivity(activity, filters) {
  return {
    title: activity?.title || "Sunrise trek to Sinhgad",
    category: filters?.category || activity?.category || "Trek",
    time: activity?.time || "06:00",
    location: activity?.location || "Pune",
    skillLevel: activity?.skillLevel || "Intermediate",
    slots: activity?.slots || 5,
    notes: activity?.notes || "",
    radius: filters?.radiusKm || activity?.radiusKm || 12,
    verifiedOnly:
      filters?.verifiedOnly !== undefined ? filters.verifiedOnly : activity?.verifiedOnly ?? true,
    womenOnly:
      filters?.womenOnly !== undefined ? filters.womenOnly : activity?.womenOnly ?? false,
  };
}

function App() {
  const [dashboard, setDashboard] = useState(null);
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function loadDashboard(params = {}, syncForm = false) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        query.set(key, String(value));
      }
    });

    const suffix = query.toString() ? `?${query.toString()}` : "";
    const payload = await apiFetch(`/api/dashboard${suffix}`);
    setDashboard(payload);
    if (syncForm || !form) {
      setForm(formFromActivity(payload.currentActivity, payload.filters));
    }
  }

  useEffect(() => {
    loadDashboard({}, true).catch((loadError) => setError(loadError.message));
  }, []);

  useEffect(() => {
    if (!form) return undefined;
    const timeoutId = window.setTimeout(() => {
      loadDashboard(
        {
          category: form.category,
          radius: form.radius,
          verifiedOnly: form.verifiedOnly,
          womenOnly: form.womenOnly,
        },
        false,
      ).catch(() => {});
    }, 180);

    return () => window.clearTimeout(timeoutId);
  }, [form?.category, form?.radius, form?.verifiedOnly, form?.womenOnly]);

  async function handleSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = await apiFetch("/api/activities", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setDashboard(payload);
      setForm(formFromActivity(payload.currentActivity, payload.filters));
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setBusy(false);
    }
  }

  async function decideRequest(requestId, action) {
    setBusy(true);
    setError("");
    try {
      const payload = await apiFetch(`/api/requests/${requestId}/decision`, {
        method: "POST",
        body: JSON.stringify({ action }),
      });
      setDashboard(payload);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  async function inviteUser(userId) {
    setBusy(true);
    setError("");
    try {
      const payload = await apiFetch("/api/invitations", {
        method: "POST",
        body: JSON.stringify({
          userId,
          activityId: dashboard.currentActivity?.id,
        }),
      });
      setDashboard(payload);
    } catch (inviteError) {
      setError(inviteError.message);
    } finally {
      setBusy(false);
    }
  }

  if (!dashboard || !form) {
    return html`
      <div className="loading-shell">
        <div className="loading-card">
          <span className="pulse-dot"></span>
          <strong>Loading SYNCANS...</strong>
        </div>
      </div>
    `;
  }

  const current = dashboard.currentActivity;
  const previewingFilters =
    current &&
    (form.category !== current.category ||
      Number(form.radius) !== Number(current.radiusKm) ||
      Boolean(form.verifiedOnly) !== Boolean(current.verifiedOnly) ||
      Boolean(form.womenOnly) !== Boolean(current.womenOnly));
  const slotsLeft = Math.max((current?.slots || 0) - (current?.approvedCount || 0), 0);

  return html`
    <div className="page-shell">
      <header className="hero">
        <nav className="topbar">
          <div className="brand">
            <span className="brand-mark">S</span>
            <div>
              <p className="eyebrow">Real-time activity matching</p>
              <h1>SYNCANS</h1>
            </div>
          </div>
          <div className="topbar-actions">
            <a className="ghost-button" href="#trust">Safety First</a>
            <a className="primary-button" href="#create">Post An Intent</a>
          </div>
        </nav>

        <section className="hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">Don't cancel plans. Sync with clans.</p>
            <h2>Find people nearby who want to do the same thing, right now.</h2>
            <p className="hero-text">
              This full-stack version keeps the concept deck's flow but now runs on a real API
              and SQLite data model. Activities, requests, and notifications persist across reloads.
            </p>

            <div className="hero-actions">
              <a className="primary-button" href="#create">Create Activity</a>
              <a className="secondary-button" href="#board">See Live Matches</a>
            </div>

            <div className="hero-stats">
              <article>
                <strong>${dashboard.metrics.matchCount}</strong>
                <span>Nearby matches in preview</span>
              </article>
              <article>
                <strong>${dashboard.metrics.requestCount}</strong>
                <span>Pending approvals</span>
              </article>
              <article>
                <strong>${dashboard.metrics.trustScore.toFixed(1)}</strong>
                <span>Current trust score</span>
              </article>
            </div>
          </div>

          <aside className="signal-panel">
            <div className="panel-header">
              <p className="eyebrow">Live city signal</p>
              <span className="pulse-dot"></span>
            </div>
            <h3>Current activity snapshot</h3>
            <div className="signal-list">
              <article>
                <span className="signal-category trek">${current.category}</span>
                <div>
                  <strong>${current.title}</strong>
                  <p>${current.location} • ${formatTime(current.time)}</p>
                </div>
              </article>
              <article>
                <span className="signal-category startup">Radius</span>
                <div>
                  <strong>${current.radiusKm} km discovery</strong>
                  <p>${current.verifiedOnly ? "Verified-only" : "Open"} matching is active</p>
                </div>
              </article>
              <article>
                <span className="signal-category study">Crew</span>
                <div>
                  <strong>${slotsLeft} slots left</strong>
                  <p>${current.approvedCount} approved so far</p>
                </div>
              </article>
            </div>
          </aside>
        </section>
      </header>

      ${error
        ? html`
            <div className="status-banner error-banner">
              <strong>Action blocked.</strong>
              <span>${error}</span>
            </div>
          `
        : null}

      ${previewingFilters
        ? html`
            <div className="status-banner info-banner">
              <strong>Preview mode.</strong>
              <span>
                The match board is showing draft filters from the form. Submit the activity to make
                them live.
              </span>
            </div>
          `
        : null}

      <main>
        <section className="category-band">
          <div className="section-heading">
            <p className="eyebrow">Popular activities</p>
            <h3>Choose the mood. The backend updates the match pool.</h3>
          </div>
          <div className="category-chips">
            ${dashboard.categories.map(
              (category) => html`
                <button
                  key=${category.name}
                  className=${`chip ${form.category === category.name ? "active" : ""}`}
                  type="button"
                  onClick=${() => setForm({ ...form, category: category.name })}
                >
                  <span>${category.name}</span>
                  <small>${category.icon}</small>
                </button>
              `,
            )}
          </div>
        </section>

        <section className="workspace-grid" id="create">
          <section className="card">
            <div className="section-heading">
              <p className="eyebrow">Step 1</p>
              <h3>Post your intent</h3>
            </div>

            <form className="activity-form" onSubmit=${handleSubmit}>
              <label>
                Activity title
                <input
                  type="text"
                  value=${form.title}
                  maxLength="70"
                  onChange=${(event) => setForm({ ...form, title: event.target.value })}
                  required
                />
              </label>

              <div className="form-grid">
                <label>
                  Category
                  <select
                    value=${form.category}
                    onChange=${(event) => setForm({ ...form, category: event.target.value })}
                  >
                    ${dashboard.categories.map(
                      (category) =>
                        html`<option key=${category.name} value=${category.name}>${category.name}</option>`,
                    )}
                  </select>
                </label>

                <label>
                  Start time
                  <input
                    type="time"
                    value=${form.time}
                    onChange=${(event) => setForm({ ...form, time: event.target.value })}
                    required
                  />
                </label>
              </div>

              <div className="form-grid">
                <label>
                  Location
                  <input
                    type="text"
                    value=${form.location}
                    onChange=${(event) => setForm({ ...form, location: event.target.value })}
                    required
                  />
                </label>

                <label>
                  Skill level
                  <select
                    value=${form.skillLevel}
                    onChange=${(event) => setForm({ ...form, skillLevel: event.target.value })}
                  >
                    <option>Beginner friendly</option>
                    <option>Intermediate</option>
                    <option>Advanced</option>
                  </select>
                </label>
              </div>

              <div className="form-grid">
                <label>
                  Slots
                  <input
                    type="number"
                    min="2"
                    max="10"
                    value=${form.slots}
                    onChange=${(event) => setForm({ ...form, slots: Number(event.target.value) })}
                  />
                </label>

                <label>
                  Gear / notes
                  <input
                    type="text"
                    maxLength="120"
                    value=${form.notes}
                    onChange=${(event) => setForm({ ...form, notes: event.target.value })}
                  />
                </label>
              </div>

              <label>
                Discovery radius: <strong>${form.radius} km</strong>
                <input
                  type="range"
                  min="5"
                  max="25"
                  value=${form.radius}
                  onChange=${(event) => setForm({ ...form, radius: Number(event.target.value) })}
                />
              </label>

              <div className="toggle-grid">
                <label className=${`toggle-card ${form.verifiedOnly ? "toggle-card-active" : ""}`}>
                  <input
                    type="checkbox"
                    checked=${form.verifiedOnly}
                    onChange=${(event) =>
                      setForm({ ...form, verifiedOnly: event.target.checked })
                    }
                  />
                  <div>
                    <strong>Verified users only</strong>
                    <span>Filter the match pool to people with mobile verification.</span>
                  </div>
                </label>

                <label className=${`toggle-card ${form.womenOnly ? "toggle-card-active" : ""}`}>
                  <input
                    type="checkbox"
                    checked=${form.womenOnly}
                    onChange=${(event) => setForm({ ...form, womenOnly: event.target.checked })}
                  />
                  <div>
                    <strong>Women's visibility filter</strong>
                    <span>Limit discovery to women for higher-confidence group creation.</span>
                  </div>
                </label>
              </div>

              <button className="primary-button full-width" type="submit" disabled=${busy}>
                ${busy ? "Saving..." : "Notify nearby users"}
              </button>
            </form>
          </section>

          <aside className="card">
            <div className="section-heading">
              <p className="eyebrow">Step 2</p>
              <h3>Matching signal board</h3>
            </div>

            <div className="metric-grid">
              <article>
                <span>Nearby matches</span>
                <strong>${dashboard.metrics.matchCount}</strong>
              </article>
              <article>
                <span>Pending requests</span>
                <strong>${dashboard.metrics.requestCount}</strong>
              </article>
              <article>
                <span>Trust score</span>
                <strong>${dashboard.metrics.trustScore.toFixed(1)}</strong>
              </article>
            </div>

            <section className="activity-highlight">
              <p className="eyebrow">Live activity</p>
              <h4>${current.title}</h4>
              <p>${current.category} • ${current.location} • ${formatTime(current.time)}</p>
              <div className="badge-row">
                <span className="pill">${current.skillLevel}</span>
                <span className="pill">${current.radiusKm} km radius</span>
                <span className="pill">${slotsLeft} slots left</span>
              </div>
              <p>${current.notes}</p>
            </section>

            <section className="notification-stack">
              <div className="section-heading slim">
                <p className="eyebrow">Instant notifications</p>
              </div>
              <div className="notification-feed">
                ${dashboard.notifications.map(
                  (note) => html`
                    <article key=${note.id} className="notification">
                      <strong>${note.title}</strong>
                      <p>${note.body}</p>
                      <span className="eyebrow">${formatTimestamp(note.timestamp)}</span>
                    </article>
                  `,
                )}
              </div>
            </section>
          </aside>
        </section>

        <section className="board-grid" id="board">
          <section className="card">
            <div className="section-heading">
              <p className="eyebrow">Step 3</p>
              <h3>Approve the right people</h3>
            </div>
            <div className="request-list">
              ${dashboard.requestQueue.length
                ? dashboard.requestQueue.map(
                    (request) => html`
                      <article key=${request.id} className="request-card">
                        <div className="header-row">
                          <div className="panel-header">
                            <div className="avatar">${initials(request.person.name)}</div>
                            <div>
                              <h4>${request.person.name}</h4>
                              <div className="request-meta">
                                <span className="chip-static">${request.person.distanceKm} km away</span>
                                <span className="chip-static">${request.person.reputation.toFixed(1)} rep</span>
                                <span className="chip-static">
                                  ${request.person.idVerified ? "ID verified" : "Phone verified"}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                        <p>${request.message}</p>
                        <p>${request.person.bio}</p>
                        <div className="request-actions">
                          <button
                            className="action-button approve"
                            type="button"
                            onClick=${() => decideRequest(request.id, "approve")}
                            disabled=${busy}
                          >
                            Approve
                          </button>
                          <button
                            className="action-button decline"
                            type="button"
                            onClick=${() => decideRequest(request.id, "decline")}
                            disabled=${busy}
                          >
                            Decline
                          </button>
                        </div>
                      </article>
                    `,
                  )
                : html`
                    <div className="empty-state">
                      All join requests are handled. Your crew is locked in.
                    </div>
                  `}
            </div>
          </section>

          <section className="card">
            <div className="section-heading">
              <p className="eyebrow">Nearby users</p>
              <h3>People ready for the same plan</h3>
            </div>
            <div className="match-grid">
              ${dashboard.nearbyUsers.length
                ? dashboard.nearbyUsers.map(
                    (person) => html`
                      <article key=${person.id} className="match-card">
                        <div className="header-row">
                          <div className="panel-header">
                            <div className="avatar">${initials(person.name)}</div>
                            <div>
                              <h4>${person.name}</h4>
                              <div className="match-meta">
                                <span className="chip-static">${person.availability}</span>
                                <span className="chip-static">${person.distanceKm} km away</span>
                              </div>
                            </div>
                          </div>
                        </div>
                        <p>${person.vibe} • ${person.bio}</p>
                        <div className="badge-row">
                          <span className="pill">${person.category}</span>
                          <span className="pill">${person.reputation.toFixed(1)} reputation</span>
                          <span className="pill">${person.idVerified ? "ID badge" : "Phone verified"}</span>
                        </div>
                        <button
                          className="secondary-button mini-button"
                          type="button"
                          onClick=${() => inviteUser(person.id)}
                          disabled=${busy}
                        >
                          Invite to activity
                        </button>
                      </article>
                    `,
                  )
                : html`
                    <div className="empty-state">
                      No nearby matches for these filters yet. Widen the radius or switch categories.
                    </div>
                  `}
            </div>
          </section>
        </section>

        <section className="card trust-card" id="trust">
          <div className="section-heading">
            <p className="eyebrow">Security & trust</p>
            <h3>Safe, structured, instant matching.</h3>
          </div>
          <div className="trust-grid">
            ${trustItems.map(
              (item) => html`
                <article key=${item.title}>
                  <strong>${item.title}</strong>
                  <p>${item.body}</p>
                </article>
              `,
            )}
          </div>
        </section>

        <section className="future-grid">
          <section className="card">
            <div className="section-heading">
              <p className="eyebrow">Business model</p>
              <h3>Free launch first, premium upgrades next.</h3>
            </div>
            <div className="timeline">
              <article>
                <span>Phase 1</span>
                <strong>Community growth</strong>
                <p>Free posting, limited daily notifications, and strong moderation in launch cities.</p>
              </article>
              <article>
                <span>Phase 2</span>
                <strong>Monetization</strong>
                <p>Premium visibility boosts, unlimited posting, sponsored events, and brand partnerships.</p>
              </article>
            </div>
          </section>

          <section className="card">
            <div className="section-heading">
              <p className="eyebrow">Future scope</p>
              <h3>Built to reduce loneliness at city scale.</h3>
            </div>
            <div className="roadmap">
              ${roadmapItems.map((item) => html`<article key=${item}>${item}</article>`)}
            </div>
          </section>
        </section>
      </main>
    </div>
  `;
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(html`<${App} />`);
