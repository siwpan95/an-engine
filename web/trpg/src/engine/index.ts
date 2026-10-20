/**
 * d20.web engine - 统一导出 + Cordis 风格插件入口
 *
 * 把 D20 整体作为一个 Cordis 插件挂入任意宿主 Context：apply(ctx, options) -> disposer。
 * 宿主 ctx 必须遵循 engine/core 的 ServiceContext 契约。这与 deepseek-harness 中
 * `ctx.plugin(plugin, options)` 把能力挂进宿主上下文的语义一致。
 */
import { Context, ServiceContext, CordisError } from "./core";
import { Character, CharacterState } from "./character";
import { COMPOSITION, CompositionEntry } from "./composition";
import { loadComposition } from "./loader";
import {
  DEFAULT_STARTING_CP, DEFAULT_MAX_DISADVANTAGE_CP,
} from "./data";

export * from "./core";
export * from "./data";
export * from "./attributes";
export * from "./equipment";
export * from "./perks";
export * from "./techniques";
export * from "./skills";
export * from "./dice";
export * from "./derived";
export * from "./combat";
export * from "./sheet";
export * from "./character";
export * from "./composition";
export * from "./loader";
export * from "./slots";
export * from "./feats";
export * from "./race";
export * from "./background";
export * from "./rest";

export interface D20Options {
  startingCp?: number;
  maxDisadvantageCp?: number;
}

/**
 * Cordis 风格插件入口：把 D20 全部子系统挂入宿主 ctx。
 * 返回 disposer，调用即按逆序卸载这 9 个服务（不影响宿主其它服务）。
 */
export function d20Plugin(ctx: ServiceContext, options: D20Options = {}): () => void {
  if (ctx.state == null) {
    ctx.state = new CharacterState(
      options.startingCp ?? DEFAULT_STARTING_CP,
      options.maxDisadvantageCp ?? DEFAULT_MAX_DISADVANTAGE_CP
    );
  }
  const mountedIds: string[] = [];
  for (const entry of COMPOSITION) {
    if (ctx.has(entry.id)) continue;
    ctx.mount(entry.service, entry.config || {}, entry.id);
    mountedIds.push(entry.id);
  }
  return () => {
    for (const id of [...mountedIds].reverse()) ctx.unmount(id);
  };
}

/** 在宿主 ctx 中仅挂载/卸载单个服务（web-cordis 风格的运行时热插拔）。 */
export function mountService(ctx: ServiceContext, entry: CompositionEntry): void {
  if (ctx.has(entry.id)) throw new CordisError(`service already mounted: ${entry.id}`);
  if (entry.inject.some((d) => !ctx.has(d)))
    throw new CordisError(`service '${entry.id}' requires missing deps`);
  ctx.mount(entry.service, entry.config || {}, entry.id);
}

export function unmountService(ctx: ServiceContext, id: string): void {
  ctx.unmount(id);
}

export { Context, Character, CharacterState, COMPOSITION };
