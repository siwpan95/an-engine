/**
 * d20.web engine/loader - 从 cordis.yml 风格组合文件装配子系统
 *
 * 借鉴 deepseek-harness 的 plugin-loader / include：
 * - 每行一个服务条目：id / service(构造器) / config / inject / disabled
 * - 运行时也可从 YAML 文本加载（极简 YAML 解析兜底，支持本组合文件所需子集）
 * 加载器按 inject 依赖做拓扑排序后挂载；缺失依赖直接报错（misconfiguration fails loud）。
 */
import { CordisError, ServiceContext, ServiceCtor } from "./core";
import { CompositionEntry, COMPOSITION } from "./composition";

// ---------------------------------------------------------------------------
//  极简 YAML 解析（无外部依赖；支持本组合文件所需的子集：块映射/块序列/流列表/标量/注释）
// ---------------------------------------------------------------------------
function stripComment(line: string): string {
  let inS = false;
  let inD = false;
  let out = "";
  for (const ch of line) {
    if (ch === "'" && !inD) inS = !inS;
    else if (ch === '"' && !inS) inD = !inD;
    else if (ch === "#" && !inS && !inD) break;
    else out += ch;
  }
  return out;
}

function parseScalar(s: string): any {
  s = s.trim();
  if (s === "" || s === "~" || s.toLowerCase() === "null") return null;
  if ((s[0] === '"' && s.endsWith('"')) || (s[0] === "'" && s.endsWith("'"))) return s.slice(1, -1);
  const low = s.toLowerCase();
  if (low === "true") return true;
  if (low === "false") return false;
  if (/^-?\d+$/.test(s)) return parseInt(s, 10);
  if (/^-?\d+\.\d+$/.test(s)) return parseFloat(s);
  return s;
}

function parseFlowSeq(s: string): any[] {
  const inner = s.trim().slice(1, -1).trim();
  if (!inner) return [];
  return inner.split(",").map((x) => parseScalar(x));
}

function minimalYamlLoad(text: string): any {
  const items: Array<[number, string]> = [];
  for (const raw of text.split("\n")) {
    const stripped = stripComment(raw);
    if (stripped.trim() === "") continue;
    const indent = stripped.length - stripped.trimStart().length;
    items.push([indent, stripped.trim()]);
  }
  let pos = 0;
  function parseMapping(curInd: number): any {
    const d: any = {};
    while (pos < items.length) {
      const [ind, content] = items[pos];
      if (ind < curInd || content.startsWith("- ")) break;
      if (ind > curInd) break;
      const idx = content.indexOf(":");
      const key = content.slice(0, idx).trim();
      let val = content.slice(idx + 1).trim();
      pos++;
      if (val === "") {
        if (pos < items.length && items[pos][0] > curInd) {
          const cind = items[pos][0];
          d[key] = items[pos][1].startsWith("- ") ? parseSequence(cind) : parseMapping(cind);
        } else d[key] = null;
      } else if (val.startsWith("[") && val.endsWith("]")) d[key] = parseFlowSeq(val);
      else d[key] = parseScalar(val);
    }
    return d;
  }
  function parseSequence(curInd: number): any[] {
    const seq: any[] = [];
    while (pos < items.length) {
      const [ind, content] = items[pos];
      if (ind !== curInd || !(content.startsWith("- ") || content === "-")) break;
      let item = content.startsWith("- ") ? content.slice(2).trim() : "";
      pos++;
      if (item === "") {
        if (pos < items.length && items[pos][0] > curInd) {
          const cind = items[pos][0];
          seq.push(items[pos][1].startsWith("- ") ? parseSequence(cind) : parseMapping(cind));
        } else seq.push(null);
      } else if (item.includes(":") && !item.startsWith("[") && !item.startsWith('"')) {
        const idx = item.indexOf(":");
        const key = item.slice(0, idx).trim();
        let val = item.slice(idx + 1).trim();
        const m: any = {};
        const itemInd = curInd + 2;
        if (val === "") {
          if (pos < items.length && items[pos][0] > curInd) {
            const cind = items[pos][0];
            m[key] = items[pos][1].startsWith("- ") ? parseSequence(cind) : parseMapping(cind);
          } else m[key] = null;
        } else if (val.startsWith("[") && val.endsWith("]")) m[key] = parseFlowSeq(val);
        else m[key] = parseScalar(val);
        while (pos < items.length && items[pos][0] === itemInd && !items[pos][1].startsWith("- ")) {
          const [k2, v2] = items[pos][1].split(":").map((x) => x.trim());
          pos++;
          if (v2 === "") {
            if (pos < items.length && items[pos][0] > itemInd) {
              const c2 = items[pos][0];
              m[k2] = items[pos][1].startsWith("- ") ? parseSequence(c2) : parseMapping(c2);
            } else m[k2] = null;
          } else if (v2.startsWith("[") && v2.endsWith("]")) m[k2] = parseFlowSeq(v2);
          else m[k2] = parseScalar(v2);
        }
        seq.push(m);
      } else seq.push(parseScalar(item));
    }
    return seq;
  }
  if (!items.length) return null;
  return items[0][1].startsWith("- ") ? parseSequence(items[0][0]) : parseMapping(0);
}

export function parseYaml(text: string): any {
  try {
    // 浏览器中若有 js-yaml 可在此优先；此处用零依赖兜底解析。
    return minimalYamlLoad(text);
  } catch {
    throw new CordisError("failed to parse composition yaml");
  }
}

// ---------------------------------------------------------------------------
//  组合加载
// ---------------------------------------------------------------------------
function isDisabled(entry: CompositionEntry, _vars: Record<string, any>): boolean {
  const dis = entry.disabled;
  if (typeof dis === "boolean") return dis;
  // 浏览器扩展（MV3）CSP 默认禁止 eval；js: 条件组合在浏览器侧不参与，降级为「不禁用」。
  if (typeof dis === "string" && dis.startsWith("js:")) return false;
  return Boolean(dis);
}

function topoSort(entries: CompositionEntry[]): CompositionEntry[] {
  const byId: Record<string, CompositionEntry> = {};
  for (const e of entries) byId[e.id] = e;
  const visited = new Set<string>();
  const ordered: CompositionEntry[] = [];
  const visit = (e: CompositionEntry) => {
    if (visited.has(e.id)) return;
    visited.add(e.id);
    for (const dep of e.inject) if (dep in byId) visit(byId[dep]);
    ordered.push(e);
  };
  for (const e of entries) visit(e);
  return ordered;
}

/** 把装配条目挂载到 ctx（按 inject 拓扑排序）。 */
export function loadComposition(
  ctx: ServiceContext,
  entries: CompositionEntry[] = COMPOSITION,
  _options?: any
): void {
  const ordered = topoSort(entries);
  for (const entry of ordered) {
    if (isDisabled(entry, {})) continue;
    ctx.mount(entry.service, entry.config || {}, entry.id);
  }
}

/** 从 YAML 文本加载组合（service 字段解析为已注册的构造器表）。 */
const SERVICE_REGISTRY: Record<string, ServiceCtor> = {};
for (const e of COMPOSITION) (SERVICE_REGISTRY as any)[e.service.name] = e.service;

export function loadCompositionYaml(ctx: ServiceContext, text: string): void {
  const doc = parseYaml(text);
  const list: any[] = Array.isArray(doc) ? doc : doc?.services ?? [];
  const entries: CompositionEntry[] = list.map((e) => {
    const ctor = (SERVICE_REGISTRY as any)[e.service];
    if (!ctor) throw new CordisError(`unknown service class: ${e.service}`);
    return { id: e.id, service: ctor, inject: e.inject || [], config: e.config, disabled: e.disabled };
  });
  loadComposition(ctx, entries);
}
