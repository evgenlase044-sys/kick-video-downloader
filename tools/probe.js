// Temporary source probe: prints exact source of named functions + grep hits.
const fs = require("fs");
function lineOf(src, idx) { return src.slice(0, idx).split("\n").length; }
function extract(src, name) {
  const rx = new RegExp("(^|\\n)([ \\t]*)((async\\s+)?function\\s+" + name + "\\s*\\(|(const|let|var)\\s+" + name + "\\s*=)", "g");
  const out = [];
  let m;
  while ((m = rx.exec(src))) {
    const start = m.index + (m[1] ? 1 : 0);
    let i = src.indexOf("{", start), depth = 0, j = i;
    for (; j < src.length; j++) {
      const ch = src[j];
      if (ch === "{") depth++;
      else if (ch === "}") { depth--; if (depth === 0) break; }
    }
    let end = src.indexOf("\n", j); if (end < 0) end = src.length;
    out.push({ line: lineOf(src, start), text: src.slice(start, end + 1) });
  }
  return out;
}
const [file, ...names] = process.argv.slice(2);
const src = fs.readFileSync(file, "utf8").replace(/^\uFEFF/, "");
console.log("FILE " + file + " bytes=" + fs.statSync(file).size + " crlf=" + src.includes("\r\n") + " lines=" + src.split("\n").length);
for (const n of names) {
  const hits = extract(src, n);
  console.log("\n#### def " + n + " (" + hits.length + ")");
  for (const h of hits) { console.log("```js  // line " + h.line); process.stdout.write(h.text.replace(/\r/g, "")); console.log("```"); }
}
