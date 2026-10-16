// index.html-dəki tək inline skriptin SHA-256 hash-ini CSP-yə yazır (script-src 'unsafe-inline' əvəzinə).
// Skriptdə hər dəyişiklikdən sonra: node scripts/csp_hash.js   (yoxlamaq üçün: node scripts/csp_hash.js --check; testlər də yoxlayır)
const fs = require("fs"), crypto = require("crypto"), path = require("path");
const file = path.join(__dirname, "..", "index.html");
const html = fs.readFileSync(file, "utf8");
const inline = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
if (inline.length !== 1) { console.error("index.html-də tam 1 inline <script> olmalıdır, tapıldı: " + inline.length); process.exit(1); }
const hash = "sha256-" + crypto.createHash("sha256").update(inline[0][1], "utf8").digest("base64");
const re = /script-src 'self'(?: 'sha256-[A-Za-z0-9+\/=]+')?(?: 'unsafe-inline')?;/;
if (!re.test(html)) { console.error("CSP-də script-src tapılmadı"); process.exit(1); }
const out = html.replace(re, `script-src 'self' '${hash}';`);
if (process.argv.includes("--check")) { if (out !== html) { console.error("CSP hash köhnəlib: node scripts/csp_hash.js işlədin"); process.exit(1); } console.log("CSP hash düzdür"); }
else { fs.writeFileSync(file, out); console.log(out === html ? "dəyişiklik yoxdur" : "CSP yeniləndi: " + hash); }
