import { useState } from "react";

const GATES = [
  { id: "salary", label: "Salary floor met", description: "Your monthly base floor. Hard no if unverified or below." },
  { id: "location", label: "Geography / remote compatible", description: "Role location or remote policy is workable for Helsinki family life." },
  { id: "live", label: "Role is real and live", description: "Active process with a concrete role. Speculative interest, pipeline placeholders, and internal-preference hiring all fail here." },
  { id: "dealbreaker", label: "No obvious dealbreakers", description: "No ethical, reputational, or structural red flags that would make you walk away regardless of score." },
];

const FACTORS = [
  {
    id: "epistemic", label: "Epistemic fit", weight: 0.20, tier: "load-bearing",
    description: "Does the org believe outcomes matter more than output? Do they manage uncertainty through evidence, treat discovery as real work, and update when reality contradicts the plan?",
    pitfallPrompt: "What specific scenario would reveal this is actually a 4? Name the canary — when would you know?",
  },
  {
    id: "translation", label: "Translation tax", weight: 0.18, tier: "load-bearing",
    description: "How much energy spent explaining, aligning, reframing basic product reality? High score = low tax. Low score = your job is mostly internal theatre and political mediation.",
    pitfallPrompt: "What structural feature of this org would make translation tax unbearable within 90 days?",
  },
  {
    id: "political", label: "Political safety", weight: 0.15, tier: "load-bearing",
    description: "Can you operate as yourself? Can you show reality without it being weaponised? Or will you need constant self-editing, shielding, and defensive navigation?",
    pitfallPrompt: "Who in this org could make your situation untenable, and under what conditions would they?",
  },
  {
    id: "sustainability", label: "Sustainability", weight: 0.14, tier: "load-bearing",
    description: "Is the role livable over time for your health, family, and nervous system? The question is recoverability — not just intensity. Demanding is fine. Systematically depleting is not.",
    pitfallPrompt: "What's the realistic worst-case travel, pace, or pressure scenario — and what does it do to the rest of your life?",
  },
  {
    id: "mandate", label: "Mandate", weight: 0.11, tier: "high",
    description: "What can you actually decide? Can you say no? Is accountability matched by real decision rights, or is the role advisory and constantly overruled?",
  },
  {
    id: "learning", label: "Learning loops", weight: 0.09, tier: "high",
    description: "Does feedback exist AND does the org demonstrably update on it? Both conditions must hold. Metrics without behaviour change is still a watermelon.",
  },
  {
    id: "interest", label: "Work interest", weight: 0.05, tier: "standard",
    description: "Is the domain, problem, or mission genuinely interesting — not just acceptable? You named this as a condition. It belongs in the score.",
  },
  {
    id: "culture", label: "Culture / good faith", weight: 0.05, tier: "standard",
    description: "Are people basically honest, respectful, acting in good faith? Score only what isn't already captured in political safety. Nice ≠ functional.",
  },
  {
    id: "growth", label: "Growth & optionality", weight: 0.03, tier: "standard",
    description: "Will this compound your trajectory through learning, scope, credibility, or doors it opens? Excludes compensation (that's a gate).",
  },
];

const CONFIDENCE = {
  H: { label: "H", title: "High — verified or lived", color: "#6ba87a", bg: "#6ba87a22" },
  M: { label: "M", title: "Medium — estimated from signals", color: "#c8a96e", bg: "#c8a96e22" },
  L: { label: "L", title: "Low — unverifiable without being inside", color: "#c87a6b", bg: "#c87a6b22" },
};

const TIER_META = {
  "load-bearing": { label: "Load-bearing", color: "#c8a96e" },
  "high": { label: "High weight", color: "#8bb4c8" },
  "standard": { label: "Standard", color: "#8b9e8b" },
};

const getVerdict = (score, loadBearingFailed, doubleWarning, allGatesPassed, isRealAlternative) => {
  if (isRealAlternative) return { label: "Real Alternative", color: "#8bb4c8", desc: "Self-generated platform — benchmark, not competitor" };
  if (!allGatesPassed) return { label: "Gate Fail", color: "#c87a6b", desc: "Stopped at prerequisites" };
  if (score === null) return { label: "Incomplete", color: "#555", desc: "Score all factors to see verdict" };
  if (doubleWarning) return { label: "Pass", color: "#c87a6b", desc: "Two load-bearing factors ≤3 — presumptive pass regardless of total" };
  if (loadBearingFailed.length > 0) return { label: "Warning", color: "#c8936b", desc: `Load-bearing factor(s) ≤4: ${loadBearingFailed.join(", ")}` };
  if (score >= 7) return { label: "Strong", color: "#6ba87a", desc: "Passes gates, beats real alternative, no load-bearing warnings" };
  if (score >= 5.5) return { label: "Viable", color: "#c8a96e", desc: "Passes gates but doesn't clearly beat real alternative — hold lightly" };
  if (score >= 4) return { label: "Watchlist", color: "#c8936b", desc: "Insufficient evidence or not live enough — monitor, don't pursue" };
  return { label: "Pass", color: "#c87a6b", desc: "Clearly loses to real alternative" };
};

export default function JobScorerV3() {
  const [roleName, setRoleName] = useState("");
  const [isRealAlternative, setIsRealAlternative] = useState(false);
  const [gates, setGates] = useState({});
  const [scores, setScores] = useState({});
  const [confidence, setConfidence] = useState({});
  const [pitfalls, setPitfalls] = useState({});
  const [notes, setNotes] = useState({});
  const [showNotes, setShowNotes] = useState({});
  const [realAlternative, setRealAlternative] = useState("");
  const [proveWrong, setProveWrong] = useState("");

  const allGatesPassed = GATES.every(g => gates[g.id] === true);
  const anyGateFailed = GATES.some(g => gates[g.id] === false);
  const scoredCount = FACTORS.filter(f => scores[f.id] !== undefined).length;
  const allScored = scoredCount === FACTORS.length;

  const weightedScore = FACTORS.reduce((acc, f) => acc + (scores[f.id] ?? 0) * f.weight, 0);
  const finalScore = allScored ? weightedScore : null;

  const loadBearingFailed = FACTORS
    .filter(f => f.tier === "load-bearing" && (scores[f.id] ?? 10) <= 4)
    .map(f => f.label);

  const doubleWarning = FACTORS
    .filter(f => f.tier === "load-bearing" && (scores[f.id] ?? 10) <= 3)
    .length >= 2;

  const loadBearingHighWithoutPitfall = FACTORS
    .filter(f => f.tier === "load-bearing" && (scores[f.id] ?? 0) >= 7 && !pitfalls[f.id]?.trim());

  const verdict = getVerdict(finalScore, loadBearingFailed, doubleWarning, allGatesPassed, isRealAlternative);

  const confidenceCounts = Object.values(confidence).reduce((acc, v) => {
    acc[v] = (acc[v] || 0) + 1; return acc;
  }, {});

  return (
    <div style={{ minHeight: "100vh", background: "#141414", color: "#e8e4dc", fontFamily: "'Georgia', serif", paddingBottom: 80 }}>

      {/* Header */}
      <div style={{ background: "#1a1a1a", borderBottom: "1px solid #2d2d2d", padding: "28px 24px 20px" }}>
        <div style={{ fontSize: 10, letterSpacing: "0.18em", color: "#555", textTransform: "uppercase", marginBottom: 6 }}>Job Scoring · v3</div>
        <div style={{ fontSize: 20, color: "#e8e4dc", letterSpacing: "-0.02em", marginBottom: 4 }}>Role Evaluator</div>
        <div style={{ fontSize: 11, color: "#444", marginBottom: 16 }}>Gates → Factors → Pitfall checks → Verdict</div>
        <input value={roleName} onChange={e => setRoleName(e.target.value)} placeholder="Role / company name..."
          style={{ width: "100%", background: "#222", border: "1px solid #333", borderRadius: 4, padding: "10px 12px", color: "#e8e4dc", fontSize: 14, fontFamily: "inherit", outline: "none", boxSizing: "border-box", marginBottom: 10 }} />
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#666", cursor: "pointer" }}>
          <input type="checkbox" checked={isRealAlternative} onChange={e => setIsRealAlternative(e.target.checked)} />
          This is a self-generated platform / real alternative (independent / advisory path)
        </label>
      </div>

      {/* Gates */}
      <div style={{ padding: "24px 24px 0" }}>
        <div style={{ fontSize: 10, letterSpacing: "0.2em", color: "#555", textTransform: "uppercase", marginBottom: 6 }}>① Gates — pass/fail prerequisites</div>
        <div style={{ fontSize: 11, color: "#444", marginBottom: 16 }}>Any failed gate = stop. No score justifies overriding a prerequisite.</div>
        {GATES.map(g => {
          const val = gates[g.id];
          return (
            <div key={g.id} style={{ background: "#1c1c1c", border: `1px solid ${val === false ? "#5a2d2d" : val === true ? "#2d4a35" : "#252525"}`, borderRadius: 6, padding: "14px 16px", marginBottom: 10 }}>
              <div style={{ fontSize: 14, color: "#e8e4dc", marginBottom: 4 }}>{g.label}</div>
              <div style={{ fontSize: 12, color: "#555", marginBottom: 12 }}>{g.description}</div>
              <div style={{ display: "flex", gap: 8 }}>
                {[{ v: true, label: "Pass", bg: "#2d4a35", active: "#3d6647", text: "#6ba87a" },
                  { v: false, label: "Fail", bg: "#5a2d2d", active: "#7a3d3d", text: "#c87a6b" },
                  { v: null, label: "?", bg: "#252525", active: "#333", text: "#888" }].map(({ v, label, bg, active, text }) => (
                  <button key={String(v)} onClick={() => setGates(p => ({ ...p, [g.id]: v }))}
                    style={{ padding: "6px 18px", borderRadius: 4, border: "none", background: val === v ? active : bg, color: val === v ? text : "#555", fontSize: 12, cursor: "pointer", fontFamily: "inherit" }}>
                    {label}
                  </button>
                ))}
              </div>
            </div>
          );
        })}
        {anyGateFailed && (
          <div style={{ background: "#3a1a1a", border: "1px solid #7a3d3d", borderRadius: 6, padding: "12px 16px", marginTop: 4, fontSize: 13, color: "#c87a6b" }}>
            ✕ Gate failed — stop here. No role score justifies overriding a prerequisite.
          </div>
        )}
      </div>

      {/* Factors */}
      <div style={{ padding: "28px 24px 0", opacity: anyGateFailed ? 0.3 : 1, pointerEvents: anyGateFailed ? "none" : "auto", transition: "opacity 0.3s" }}>
        <div style={{ fontSize: 10, letterSpacing: "0.2em", color: "#555", textTransform: "uppercase", marginBottom: 6 }}>② Scored factors</div>
        <div style={{ fontSize: 11, color: "#444", marginBottom: 6 }}>Rate 1–10. Set confidence. Complete pitfall checks for load-bearing factors ≥7.</div>
        <div style={{ fontSize: 11, color: "#c8a96e", marginBottom: 20 }}>⚠ Two load-bearing factors ≤3 = presumptive pass regardless of total score.</div>

        {FACTORS.map(f => {
          const s = scores[f.id];
          const c = confidence[f.id];
          const tier = TIER_META[f.tier];
          const needsPitfall = f.tier === "load-bearing" && (s ?? 0) >= 7;
          const pitfallMissing = needsPitfall && !pitfalls[f.id]?.trim();
          const isDoubleWarningContributor = f.tier === "load-bearing" && (s ?? 10) <= 3;

          return (
            <div key={f.id} style={{
              background: "#1c1c1c",
              border: `1px solid ${isDoubleWarningContributor ? "#7a3d3d" : pitfallMissing ? "#5a3a1a" : "#252525"}`,
              borderRadius: 6, padding: "14px 16px", marginBottom: 10,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
                <div style={{ fontSize: 14, color: "#e8e4dc" }}>{f.label}</div>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  {isDoubleWarningContributor && <span style={{ fontSize: 9, color: "#c87a6b", background: "#c87a6b18", padding: "2px 6px", borderRadius: 3 }}>DOUBLE WARNING RISK</span>}
                  <span style={{ fontSize: 10, color: tier.color }}>{Math.round(f.weight * 100)}%</span>
                  <span style={{ fontSize: 9, color: tier.color, background: tier.color + "18", padding: "2px 6px", borderRadius: 3, textTransform: "uppercase", letterSpacing: "0.1em" }}>{tier.label}</span>
                </div>
              </div>
              <div style={{ fontSize: 12, color: "#555", marginBottom: 12 }}>{f.description}</div>

              <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 10 }}>
                {[1,2,3,4,5,6,7,8,9,10].map(n => {
                  const isSelected = s === n;
                  const btnColor = n <= 3 ? "#c87a6b" : n <= 6 ? "#c8a96e" : "#6ba87a";
                  return (
                    <button key={n} onClick={() => setScores(p => ({ ...p, [f.id]: n }))}
                      style={{ width: 32, height: 32, borderRadius: 4, border: "none", background: isSelected ? btnColor : "#252525", color: isSelected ? "#141414" : "#555", fontSize: 13, cursor: "pointer", fontFamily: "inherit", fontWeight: isSelected ? "bold" : "normal" }}>
                      {n}
                    </button>
                  );
                })}
              </div>

              {s !== undefined && (
                <div style={{ width: "100%", height: 3, background: "#2a2a2a", borderRadius: 2, marginBottom: 12 }}>
                  <div style={{ width: `${(s / 10) * 100}%`, height: "100%", background: s <= 3 ? "#c87a6b" : s <= 6 ? "#c8a96e" : "#6ba87a", borderRadius: 2, transition: "width 0.3s" }} />
                </div>
              )}

              <div style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 10, color: "#444", marginBottom: 6, letterSpacing: "0.08em", textTransform: "uppercase" }}>Confidence</div>
                <div style={{ display: "flex", gap: 6 }}>
                  {Object.entries(CONFIDENCE).map(([key, meta]) => (
                    <button key={key} onClick={() => setConfidence(p => ({ ...p, [f.id]: key }))}
                      style={{ padding: "4px 10px", borderRadius: 4, border: `1px solid ${c === key ? meta.color : "#333"}`, background: c === key ? meta.bg : "transparent", color: c === key ? meta.color : "#444", fontSize: 11, cursor: "pointer", fontFamily: "inherit" }}
                      title={meta.title}>
                      {key} — {meta.title.split("—")[1].trim()}
                    </button>
                  ))}
                </div>
              </div>

              {needsPitfall && (
                <div style={{ marginTop: 4 }}>
                  <div style={{ fontSize: 10, color: pitfallMissing ? "#c8a96e" : "#444", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6 }}>
                    {pitfallMissing ? "⚠ Pitfall check required (load-bearing ≥7)" : "✓ Pitfall check"}
                  </div>
                  <textarea value={pitfalls[f.id] || ""} onChange={e => setPitfalls(p => ({ ...p, [f.id]: e.target.value }))}
                    placeholder={f.pitfallPrompt} rows={2}
                    style={{ width: "100%", background: "#1a1a1a", border: `1px solid ${pitfallMissing ? "#5a3a1a" : "#333"}`, borderRadius: 4, padding: "8px 10px", color: "#bbb", fontSize: 12, fontFamily: "inherit", outline: "none", resize: "vertical", boxSizing: "border-box" }} />
                </div>
              )}

              <button onClick={() => setShowNotes(p => ({ ...p, [f.id]: !p[f.id] }))}
                style={{ marginTop: 8, background: "none", border: "none", color: "#333", fontSize: 11, cursor: "pointer", padding: 0, fontFamily: "inherit" }}>
                {showNotes[f.id] ? "− hide notes" : "+ notes"}
              </button>
              {showNotes[f.id] && (
                <textarea value={notes[f.id] || ""} onChange={e => setNotes(p => ({ ...p, [f.id]: e.target.value }))}
                  placeholder="What drove this score..." rows={2}
                  style={{ marginTop: 6, width: "100%", background: "#222", border: "1px solid #333", borderRadius: 4, padding: "8px 10px", color: "#999", fontSize: 12, fontFamily: "inherit", outline: "none", resize: "vertical", boxSizing: "border-box" }} />
              )}
            </div>
          );
        })}
      </div>

      {/* Verdict */}
      {(allGatesPassed || isRealAlternative) && (
        <div style={{ margin: "28px 24px 0", background: "#1a1a1a", border: `1px solid ${verdict.color}33`, borderRadius: 8, padding: "24px 20px" }}>
          <div style={{ fontSize: 10, letterSpacing: "0.2em", color: "#555", textTransform: "uppercase", marginBottom: 16 }}>
            ③ Verdict {roleName ? `— ${roleName}` : ""}
          </div>

          <div style={{ display: "flex", alignItems: "baseline", gap: 16, marginBottom: 8 }}>
            <div style={{ fontSize: 52, color: verdict.color, fontWeight: "normal", lineHeight: 1 }}>
              {isRealAlternative ? "—" : finalScore !== null ? finalScore.toFixed(1) : "—"}
            </div>
            <div>
              <div style={{ fontSize: 20, color: verdict.color, fontWeight: "normal" }}>{verdict.label}</div>
              <div style={{ fontSize: 11, color: "#555", marginTop: 4 }}>{verdict.desc}</div>
            </div>
          </div>

          {!allScored && !isRealAlternative && (
            <div style={{ fontSize: 12, color: "#444", marginBottom: 16 }}>
              {FACTORS.length - scoredCount} factor{FACTORS.length - scoredCount !== 1 ? "s" : ""} unscored.
            </div>
          )}

          {Object.keys(confidence).length > 0 && (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 20 }}>
              {Object.entries(CONFIDENCE).map(([key, meta]) => (
                confidenceCounts[key] ? (
                  <div key={key} style={{ fontSize: 11, color: meta.color, background: meta.bg, padding: "4px 10px", borderRadius: 4 }}>
                    {confidenceCounts[key]}× {meta.title.split("—")[0].trim()} confidence
                  </div>
                ) : null
              ))}
            </div>
          )}

          {allScored && !isRealAlternative && (
            <>
              <div style={{ marginBottom: 16 }}>
                {[...FACTORS].sort((a, b) => (scores[b.id] * b.weight) - (scores[a.id] * a.weight)).map(f => {
                  const c = confidence[f.id];
                  const cMeta = c ? CONFIDENCE[c] : null;
                  return (
                    <div key={f.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 7, fontSize: 12 }}>
                      <span style={{ color: "#777", display: "flex", alignItems: "center", gap: 6 }}>
                        {f.label}
                        {cMeta && <span style={{ fontSize: 9, color: cMeta.color, background: cMeta.bg, padding: "1px 5px", borderRadius: 2 }}>{c}</span>}
                      </span>
                      <span style={{ color: "#e8e4dc" }}>
                        {scores[f.id]}/10 × {Math.round(f.weight * 100)}% = <strong style={{ color: TIER_META[f.tier].color }}>{(scores[f.id] * f.weight).toFixed(2)}</strong>
                      </span>
                    </div>
                  );
                })}
              </div>

              {doubleWarning && (
                <div style={{ background: "#3a1a1a", border: "1px solid #c87a6b", borderRadius: 5, padding: "12px 14px", marginBottom: 12, fontSize: 12, color: "#c87a6b" }}>
                  ✕ Two or more load-bearing factors scored ≤3. Presumptive pass regardless of total. The number is no longer the point.
                </div>
              )}

              {!doubleWarning && loadBearingFailed.length > 0 && (
                <div style={{ background: "#3a1a1a", border: "1px solid #7a3d3d", borderRadius: 5, padding: "12px 14px", marginBottom: 12, fontSize: 12, color: "#c87a6b" }}>
                  ⚠ Load-bearing factor{loadBearingFailed.length > 1 ? "s" : ""} ≤4: {loadBearingFailed.join(", ")}. A high total doesn't fix this.
                </div>
              )}

              {loadBearingHighWithoutPitfall.length > 0 && (
                <div style={{ background: "#2a2010", border: "1px solid #5a4010", borderRadius: 5, padding: "12px 14px", marginBottom: 12, fontSize: 12, color: "#c8a96e" }}>
                  ⚠ Pitfall check incomplete: {loadBearingHighWithoutPitfall.map(f => f.label).join(", ")}. Scores ≥7 on load-bearing factors require a named downside scenario.
                </div>
              )}
            </>
          )}

          {finalScore !== null && finalScore >= 6 && !isRealAlternative && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 10, color: "#444", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>
                What would prove this score wrong — and when would you know?
              </div>
              <textarea value={proveWrong} onChange={e => setProveWrong(e.target.value)}
                placeholder="Name the canary. Be specific about the early signal and the timeline."
                rows={3}
                style={{ width: "100%", background: "#222", border: "1px solid #2d2d2d", borderRadius: 4, padding: "10px 12px", color: "#bbb", fontSize: 12, fontFamily: "inherit", outline: "none", resize: "vertical", boxSizing: "border-box" }} />
            </div>
          )}

          <div>
            <div style={{ fontSize: 10, color: "#444", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>
              Real alternative to taking this role
            </div>
            <textarea value={realAlternative} onChange={e => setRealAlternative(e.target.value)}
              placeholder="Not the next best job on the list. What do you actually do if you pass on this? Be specific."
              rows={2}
              style={{ width: "100%", background: "#222", border: "1px solid #2d2d2d", borderRadius: 4, padding: "10px 12px", color: "#bbb", fontSize: 12, fontFamily: "inherit", outline: "none", resize: "vertical", boxSizing: "border-box" }} />
          </div>
        </div>
      )}
    </div>
  );
}
