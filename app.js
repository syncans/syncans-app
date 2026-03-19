const { useEffect, useState } = React;
const html = htm.bind(React.createElement);

window.addEventListener("error", (event) => {
  const root = document.getElementById("root");
  if (!root) return;
  root.innerHTML = `<pre style="padding:24px;color:#8b1e00;white-space:pre-wrap;font:14px monospace;">${event.message}</pre>`;
});

window.addEventListener("unhandledrejection", (event) => {
  const root = document.getElementById("root");
  if (!root) return;
  root.innerHTML = `<pre style="padding:24px;color:#8b1e00;white-space:pre-wrap;font:14px monospace;">${String(event.reason)}</pre>`;
});

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

function formFromActivity(activity, filters, profile) {
  return {
    title: activity?.title || "Sunrise trek to Sinhgad",
    category: filters?.category || activity?.category || profile?.favoriteCategories?.[0] || "Trek",
    time: activity?.time || "06:00",
    location: activity?.location || profile?.homeCity || "Pune",
    skillLevel: activity?.skillLevel || "Intermediate",
    slots: activity?.slots || 5,
    notes: activity?.notes || "",
    radius: filters?.radiusKm || activity?.radiusKm || profile?.defaultRadiusKm || 12,
    verifiedOnly:
      filters?.verifiedOnly !== undefined
        ? filters.verifiedOnly
        : activity?.verifiedOnly ?? profile?.defaultVerifiedOnly ?? true,
    womenOnly:
      filters?.womenOnly !== undefined ? filters.womenOnly : activity?.womenOnly ?? false,
  };
}

function profileFromPayload(profile) {
  return {
    organizerName: profile?.organizerName || "SYNCANS Organizer",
    homeCity: profile?.homeCity || "Pune",
    defaultRadiusKm: profile?.defaultRadiusKm || 12,
    defaultVerifiedOnly: profile?.defaultVerifiedOnly ?? true,
    favoriteCategories: profile?.favoriteCategories || ["Trek", "Study"],
    safetyNote:
      profile?.safetyNote || "Prefer verified groups, daylight meetups, and small batches.",
  };
}

function App() {
  const [dashboard, setDashboard] = useState(null);
  const [form, setForm] = useState(null);
  const [profileForm, setProfileForm] = useState(null);
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
      setForm(formFromActivity(payload.currentActivity, payload.filters, payload.profile));
    }
    if (syncForm || !profileForm) {
      setProfileForm(profileFromPayload(payload.profile));
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
      setForm(formFromActivity(payload.currentActivity, payload.filters, payload.profile));
      setProfileForm(profileFromPayload(payload.profile));
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleProfileSave(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = await apiFetch("/api/profile", {
        method: "POST",
        body: JSON.stringify(profileForm),
      });
      setDashboard(payload);
      setProfileForm(profileFromPayload(payload.profile));
      setForm((currentForm) => ({
        ...(currentForm || {}),
        location: payload.profile.homeCity,
        radius: payload.profile.defaultRadiusKm,
        verifiedOnly: payload.profile.defaultVerifiedOnly,
      }));
    } catch (profileError) {
      setError(profileError.message);
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

  function reuseActivity(activity) {
    setForm({
      title: activity.title,
      category: activity.category,
      time: activity.time,
      location: activity.location,
      skillLevel: activity.skillLevel,
      slots: activity.slots,
      notes: activity.notes,
      radius: activity.radiusKm,
      verifiedOnly: activity.verifiedOnly,
      womenOnly: activity.womenOnly,
    });
    document.querySelector("#create")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function applySuggestion(suggestion) {
    setForm((currentForm) => ({
      ...currentForm,
      title: suggestion.title,
      category: suggestion.category,
      location: suggestion.location,
      radius: suggestion.radiusKm,
      slots: suggestion.slots,
      verifiedOnly: suggestion.verifiedOnly,
    }));
    document.querySelector("#create")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function toggleFavorite(category) {
    const current = new Set(profileForm.favoriteCategories);
    if (current.has(category)) {
      current.delete(category);
    } else {
      current.add(category);
    }
    const next = Array.from(current).slice(0, 4);
    setProfileForm({
      ...profileForm,
      favoriteCategories: next.length ? next : [category],
    });
  }

  if (!dashboard || !form || !profileForm) {
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
  const slotsLeft = Math.max((current?.slots || 0) - (current?.approvedCount || 0), 0);
  const previewingFilters =
    current &&
    (form.category !== current.category ||
      Number(form.radius) !== Number(current.radiusKm) ||
      Boolean(form.verifiedOnly) !== Boolean(current.verifiedOnly) ||
      Boolean(form.womenOnly) !== Boolean(current.womenOnly));

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
            <a className="ghost-button" href="#profile">Organizer Defaults</a>
            <a className="primary-button" href="#create">Post An Intent</a>
          </div>
        </nav>

        <section className="hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">Don't cancel plans. Sync with clans.</p>
            <h2>Turn spontaneous plans into real nearby meetups.</h2>
            <p className="hero-text">
              SYNCANS now saves organizer defaults, keeps activity history, and offers one-tap reuse
              so frequent plans feel fast instead of repetitive.
            </p>

            <div className="hero-actions">
              <a className="primary-button" href="#create">Create Activity</a>
              <a className="secondary-button" href="#history">Reuse Past Plan</a>
            </div>

            <div className="hero-stats">
              <article>
                <strong>${dashboard.metrics.matchCount}</strong>
                <span>Nearby matches right now</span>
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
              <p className="eyebrow">Organizer summary</p>
              <span className="pulse-dot"></span>
            </div>
            <h3>${profileForm.organizerName}</h3>
            <div className="signal-list">
              <article>
                <span className="signal-category startup">City</span>
                <div>
                  <strong>${profileForm.homeCity}</strong>
                  <p>Primary launch zone for matching and defaults</p>
                </div>
              </article>
              <article>
                <span className="signal-category trek">Favorites</span>
                <div>
                  <strong>${profileForm.favoriteCategories.join(", ")}</strong>
                  <p>Used for quick suggestions and reusable activity templates</p>
                </div>
              </article>
              <article>
                <span className="signal-category study">Safety</span>
                <div>
                  <strong>${profileForm.defaultRadiusKm} km default</strong>
                  <p>${profileForm.safetyNote}</p>
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
              <span>The live board is showing your draft filters until you publish the activity.</span>
            </div>
          `
        : null}

      <main>
        <section className="card" id="profile">
          <div className="section-heading">
            <p className="eyebrow">Organizer defaults</p>
            <h3>Save your city, safety rules, and favorite categories.</h3>
          </div>

          <form className="activity-form" onSubmit=${handleProfileSave}>
            <div className="form-grid">
              <label>
                Organizer name
                <input
                  type="text"
                  value=${profileForm.organizerName}
                  onChange=${(event) =>
                    setProfileForm({ ...profileForm, organizerName: event.target.value })}
                  required
                />
              </label>
              <label>
                Home city
                <input
                  type="text"
                  value=${profileForm.homeCity}
                  onChange=${(event) => setProfileForm({ ...profileForm, homeCity: event.target.value })}
                  required
                />
              </label>
            </div>

            <div className="form-grid">
              <label>
                Default radius
                <input
                  type="number"
                  min="5"
                  max="25"
                  value=${profileForm.defaultRadiusKm}
                  onChange=${(event) =>
                    setProfileForm({
                      ...profileForm,
                      defaultRadiusKm: Number(event.target.value),
                    })}
                />
              </label>
              <label>
                Safety note
                <input
                  type="text"
                  value=${profileForm.safetyNote}
                  onChange=${(event) =>
                    setProfileForm({ ...profileForm, safetyNote: event.target.value })}
                />
              </label>
            </div>

            <label className=${`toggle-card ${profileForm.defaultVerifiedOnly ? "toggle-card-active" : ""}`}>
              <input
                type="checkbox"
                checked=${profileForm.defaultVerifiedOnly}
                onChange=${(event) =>
                  setProfileForm({
                    ...profileForm,
                    defaultVerifiedOnly: event.target.checked,
                  })}
              />
              <div>
                <strong>Verified-only by default</strong>
                <span>Use this as the standard rule for fresh activities.</span>
              </div>
            </label>

            <div className="section-heading slim">
              <p className="eyebrow">Favorite categories</p>
            </div>
            <div className="category-chips">
              ${dashboard.categories.map(
                (category) => html`
                  <button
                    key=${category.name}
                    className=${`chip ${
                      profileForm.favoriteCategories.includes(category.name) ? "active" : ""
                    }`}
                    type="button"
                    onClick=${() => toggleFavorite(category.name)}
                  >
                    <span>${category.name}</span>
                    <small>${category.icon}</small>
                  </button>
                `,
              )}
            </div>

            <button className="primary-button full-width" type="submit" disabled=${busy}>
              ${busy ? "Saving..." : "Save organizer defaults"}
            </button>
          </form>
        </section>

        <section className="card">
          <div className="section-heading">
            <p className="eyebrow">Smart suggestions</p>
            <h3>Quick-start plans tailored to your niche.</h3>
          </div>
          <div className="match-grid">
            ${dashboard.suggestions.map(
              (suggestion) => html`
                <article key=${suggestion.id} className="match-card">
                  <h4>${suggestion.title}</h4>
                  <p>${suggestion.location} | ${suggestion.radiusKm} km | ${suggestion.slots} slots</p>
                  <div className="badge-row">
                    <span className="pill">${suggestion.category}</span>
                    <span className="pill">${suggestion.verifiedOnly ? "Verified default" : "Open discovery"}</span>
                  </div>
                  <button
                    className="secondary-button mini-button"
                    type="button"
                    onClick=${() => applySuggestion(suggestion)}
                  >
                    Use template
                  </button>
                </article>
              `,
            )}
          </div>
        </section>

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
              <p className="eyebrow">Create activity</p>
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
                      setForm({ ...form, verifiedOnly: event.target.checked })}
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
              <p className="eyebrow">Matching signal board</p>
              <h3>Live activity status</h3>
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
              <p>${current.category} | ${current.location} | ${formatTime(current.time)}</p>
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

        <section className="card" id="history">
          <div className="section-heading">
            <p className="eyebrow">Activity history</p>
            <h3>Reuse what already works.</h3>
          </div>
          <div className="match-grid">
            ${dashboard.history.map(
              (activity) => html`
                <article key=${activity.id} className="match-card">
                  <h4>${activity.title}</h4>
                  <p>${activity.location} | ${formatTime(activity.time)} | ${activity.category}</p>
                  <div className="badge-row">
                    <span className="pill">${activity.status}</span>
                    <span className="pill">${activity.radiusKm} km</span>
                    <span className="pill">${activity.approvedCount} approved</span>
                  </div>
                  <button
                    className="secondary-button mini-button"
                    type="button"
                    onClick=${() => reuseActivity(activity)}
                  >
                    Reuse this plan
                  </button>
                </article>
              `,
            )}
          </div>
        </section>

        <section className="board-grid" id="board">
          <section className="card">
            <div className="section-heading">
              <p className="eyebrow">Approvals</p>
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
                : html`<div className="empty-state">All join requests are handled. Your crew is locked in.</div>`}
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
                        <p>${person.vibe} | ${person.bio}</p>
                        <div className="badge-row">
                          <span className="pill">${person.category}</span>
                          <span className="pill">${person.city}</span>
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
      </main>
    </div>
  `;
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(html`<${App} />`);
