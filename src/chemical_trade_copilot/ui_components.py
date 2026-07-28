APP_CSS = """
<style>
:root {
  --ctc-paper: #F2EFE7;
  --ctc-surface: #FBFAF6;
  --ctc-ink: #102B27;
  --ctc-green: #316A5D;
  --ctc-mint: #E1EBE6;
  --ctc-gold: #A78349;
  --ctc-line: #D7D0C3;
  --ctc-text: #465750;
}
.stApp { background: var(--ctc-paper); color: var(--ctc-ink); }
[data-testid="stMainBlockContainer"] { max-width: 1040px; padding-top: 3rem; }
h1, h2, h3 { font-family: Georgia, "Times New Roman", serif !important; color: var(--ctc-ink) !important; }
h1 { letter-spacing: -0.025em; line-height: 1.06 !important; }
p, label, [data-testid="stCaptionContainer"] { color: var(--ctc-text); }
hr { border-color: var(--ctc-line) !important; }
.stTextArea textarea { background: var(--ctc-surface); border-color: var(--ctc-line); color: var(--ctc-ink); }
.stTextArea textarea:focus { border-color: var(--ctc-green); box-shadow: 0 0 0 1px var(--ctc-green); }
.stButton > button[kind="primary"] { background: var(--ctc-ink); border-color: var(--ctc-ink); }
.stButton > button:not([kind="primary"]) { border-color: var(--ctc-ink); color: var(--ctc-ink); }
.ctc-eyebrow { color: var(--ctc-green); font: 700 11px Inter, "Segoe UI", sans-serif; letter-spacing: .15em; text-transform: uppercase; }
.ctc-decision-line { display:grid; grid-template-columns:repeat(4,1fr); border-top:1px solid var(--ctc-line); border-bottom:1px solid var(--ctc-line); margin:24px 0 8px; }
.ctc-decision { padding:14px 12px; border-right:1px solid var(--ctc-line); font:12px Inter,"Segoe UI",sans-serif; color:var(--ctc-text); }
.ctc-decision:last-child { border-right:0; }
.ctc-decision b { display:block; margin-top:4px; color:var(--ctc-ink); font-size:13px; }
.ctc-dot { display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--ctc-green); margin-right:6px; }
.ctc-dot.open { background:var(--ctc-gold); }
.ctc-fact { border:1px solid var(--ctc-line); border-radius:12px; overflow:hidden; background:var(--ctc-surface); margin:12px 0; }
.ctc-fact-head,.ctc-source { display:flex; justify-content:space-between; gap:12px; padding:11px 14px; background:var(--ctc-mint); color:var(--ctc-green); font-size:11px; }
.ctc-fact-grid { display:grid; grid-template-columns:repeat(3,1fr); }
.ctc-fact-cell { padding:17px; border-right:1px solid var(--ctc-line); color:var(--ctc-text); font-size:12px; }
.ctc-fact-cell:last-child { border-right:0; }
.ctc-fact-cell b { display:block; color:var(--ctc-ink); font:700 14px Inter,"Segoe UI",sans-serif; font-style:normal; font-variant-numeric:tabular-nums; }
.ctc-warning { border-left:3px solid var(--ctc-gold); background:#ECE7DC; padding:12px 15px; color:#70614D; font-size:12px; }
.ctc-checklist { list-style:none; padding:0; margin:0; }
.ctc-checklist li { padding:9px 0; border-bottom:1px solid var(--ctc-line); color:var(--ctc-text); font-size:13px; }
.ctc-checklist li:before { content:"□"; margin-right:9px; color:var(--ctc-green); }
.ctc-guardrail { border-left:3px solid #8D4B3B; background:#F3E5DF; padding:12px 15px; color:#754B40; font-size:12px; }
@media (max-width: 820px) {
  .ctc-decision-line,.ctc-fact-grid { grid-template-columns:1fr; }
  .ctc-decision,.ctc-fact-cell { border-right:0; border-bottom:1px solid var(--ctc-line); }
}
</style>
"""


def build_copy_button_html() -> str:
    return """
<div class="ctc-copy-email">
  <button type="button" aria-label="Copy English email">Copy English email</button>
  <span aria-live="polite"></span>
</div>
<style>
.ctc-copy-email { display:flex; justify-content:flex-end; align-items:center; gap:10px; }
.ctc-copy-email button { border:0; border-radius:8px; background:#102B27; color:white;
  padding:10px 15px; font:700 12px Inter,"Segoe UI",sans-serif; cursor:pointer; }
.ctc-copy-email button:focus-visible { outline:3px solid #A78349; outline-offset:2px; }
.ctc-copy-email span { color:#316A5D; font:600 11px Inter,"Segoe UI",sans-serif; }
</style>
<script>
(function() {
  const root = document.currentScript.previousElementSibling.previousElementSibling;
  const button = root.querySelector("button");
  const status = root.querySelector("span");
  button.addEventListener("click", async function() {
    const textarea = document.querySelector('textarea[aria-label="Editable English email"]');
    if (!textarea) { status.textContent = "Email editor not found"; return; }
    await navigator.clipboard.writeText(textarea.value);
    status.textContent = "Copied";
  });
})();
</script>
""".strip()
