// 엔진 회귀 시험 — 의뢰공문 폴더의 ODT 전부를 추출해 기준 결과와 칸 단위로 비교한다.
// 사용: node 시험/엔진_회귀.js <의뢰공문폴더> [기준결과.json]
//   기준결과를 주지 않으면 결과를 시험/결과/회귀_날짜.json 으로 저장만 한다(처음 한 번 → 이후 기준으로 사용).
const { E, fs, path, list, odt, check, summary } = require('./공통.js');
(async () => {
  const dir = process.argv[2], base = process.argv[3];
  if (!dir) { console.log('사용: node 시험/엔진_회귀.js <의뢰공문폴더> [기준결과.json]'); process.exit(2); }
  const res = []; for (const f of list(dir, /\.odt$/i)) { try { res.push(await odt(f)); } catch (e) { console.log('읽기 실패', f.name, e.message); } }
  E.markDuplicates(res);
  const out = {}; for (const r of res) out[r.doc.파일명] = r.rows.map(x => { const o = {}; for (const c of E.COLUMNS) o[c] = x[c] == null ? '' : x[c]; return o; });
  const od = path.join(__dirname, '결과'); fs.mkdirSync(od, { recursive: true });
  const of = path.join(od, `회귀_${new Date().toISOString().slice(0, 10)}.json`); fs.writeFileSync(of, JSON.stringify(out, null, 1));
  console.log(`공문 ${res.length}건 · 행 ${Object.values(out).reduce((a, r) => a + r.length, 0)}개 → ${path.relative(process.cwd(), of)}`);
  if (!base) return;
  const B = JSON.parse(fs.readFileSync(base, 'utf8')); let n = 0, d = 0;
  for (const k of new Set([...Object.keys(B), ...Object.keys(out)])) {
    const a = B[k] || [], b = out[k] || [];
    if (a.length !== b.length) { d++; console.log(`  행 수 다름: ${k} (${a.length} → ${b.length})`); continue; }
    a.forEach((x, i) => { for (const c of Object.keys(x)) { n++; if (x[c] !== (b[i] || {})[c]) { d++; if (d <= 20) console.log(`  다름: ${k} ${i + 1}행 ${c}: "${x[c]}" → "${(b[i] || {})[c]}"`); } } });
  }
  check(d === 0, `기준 결과와 비교: 칸 ${n}개`, `차이 ${d}`);
  summary();
})();
