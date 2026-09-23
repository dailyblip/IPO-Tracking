/** Standalone, fictional-data preview. No Supabase credentials or real records. */
import { readFileSync, writeFileSync, readdirSync } from "node:fs";
import { resolve, extname } from "node:path";
import { details, overview } from "../server/demo.js";
const out = process.argv[2];
if (!out) throw new Error("Pass an output HTML path");
const assets = resolve("dist/assets");
const files = readdirSync(assets);
const js = readFileSync(
  resolve(assets, files.find((x) => x.endsWith(".js"))!),
  "utf8",
);
let css = readFileSync(
  resolve(assets, files.find((x) => x.endsWith(".css"))!),
  "utf8",
);
for (const file of files.filter((x) => extname(x) === ".woff2"))
  css = css.replaceAll(
    "/assets/" + file,
    "data:font/woff2;base64," +
      readFileSync(resolve(assets, file)).toString("base64"),
  );
const payload = JSON.stringify({ details, overview: overview() }).replaceAll(
  "<",
  "\\u003c",
);
const bridge = `const fixtures=${payload};const nativeFetch=window.fetch.bind(window);window.fetch=async(input,init)=>{const url=new URL(String(input),location.href);if(!url.pathname.startsWith('/api/'))return nativeFetch(input,init);let result;const q=url.searchParams;const path=url.pathname;const summary=d=>{const {people,source,...r}=d;return r};if(path==='/api/config')result={demo:true,configured:false};else if(path==='/api/overview')result=fixtures.overview;else if(path==='/api/saved')result={ids:[]};else if(path==='/api/offerings'){const ids=(q.get('ids')||'').split(',');const rows=fixtures.details.filter(d=>(q.get('saved')!=='1'||ids.includes(d.id))&&(!q.get('stage')||d.stage===q.get('stage'))&&(!Number(q.get('min'))||(d.value!==null&&d.value>=Number(q.get('min'))))&&(d.company+' '+d.ticker).toLowerCase().includes((q.get('q')||'').toLowerCase()));const page=Number(q.get('page')||1);result={items:rows.slice((page-1)*25,page*25).map(summary),total:rows.length,page,pageSize:25};}else if(path.startsWith('/api/offerings/'))result=fixtures.details.find(d=>d.id===path.split('/').pop());else if(path==='/api/people/search'){const needle=(q.get('q')||'').toLowerCase();const rows=fixtures.details.flatMap(d=>d.people.filter(p=>(!q.get('relationship')||p.relationship===q.get('relationship'))&&(p.name+' '+p.biography).toLowerCase().includes(needle)).map(p=>({id:d.id+':'+p.id,person:p,company:d.company,offeringId:d.id,stage:d.stage,matchType:p.name.toLowerCase().includes(needle)?'Name match':'Biography text match',evidence:{...p.source,excerpt:p.biography}})));const page=Number(q.get('page')||1);result={items:rows.slice((page-1)*25,page*25),total:rows.length,page,pageSize:25};}return new Response(JSON.stringify(result||{error:'Preview record not found'}),{status:result?200:404,headers:{'Content-Type':'application/json'}});};`;
writeFileSync(
  resolve(out),
  `<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>IPO Roll — Interactive sample preview</title><style>${css}</style></head><body><div id="root"></div><script>${bridge.replaceAll("</script", "<\\/script")}</script><script type="module">${js.replaceAll("</script", "<\\/script")}</script></body></html>`,
);
console.log("Saved standalone sample preview");
