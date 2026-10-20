/**
 * d20.web engine/core - TypeScript 版 mini-Cordis
 *
 * 参考 deepseek-harness 中 vendored 的 Cordis（TypeScript 插件框架）思想，为 D20 的
 * 浏览器扩展提供一套零依赖的「上下文 / 服务 / 依赖注入 / 事件 / 生命周期」模型：
 *
 * - Context : 服务容器 + 事件总线 + effect 生命周期。插件按稳定 key 挂到 ctx（如
 *   ctx.attributes / ctx.equipment）。服务以 key 形式动态可读（索引签名 + 动态赋值）。
 * - Service : 能力单位，声明 static inject 依赖；挂载后其他服务按 key 查找。
 * - 依赖注入: Context.mount 在挂载前校验 inject 依赖已就绪（加载顺序由依赖表达）。
 * - 事件     : emit / waterfall / serial / parallel 四种语义（见 EventBus）。
 * - 可逆副作用: ctx.effect(fn) 收集 disposer，ctx.dispose() / ctx.unmount(name) 逆序清理。
 *
 * 与 Cordis 的差异：D20 是单上下文纯 TS 应用，因此省略了 proxy 分支、isolate 作用域与
 * HMR；保留了对本重构最有价值的「显式装配 + 依赖声明 + 事件 + 可逆清理」。
 */

export class CordisError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CordisError";
  }
}

type Listener = (...args: any[]) => any;

export class EventBus {
  private _listeners: Record<string, Listener[]> = {};

  on(name: string, fn: Listener): () => void {
    (this._listeners[name] ||= []).push(fn);
    const self = this;
    return () => {
      const lst = self._listeners[name];
      if (lst) {
        const i = lst.indexOf(fn);
        if (i >= 0) lst.splice(i, 1);
      }
    };
  }

  off(name: string, fn: Listener): void {
    const lst = this._listeners[name];
    if (lst) {
      const i = lst.indexOf(fn);
      if (i >= 0) lst.splice(i, 1);
    }
  }

  emit(name: string, ...args: any[]): void {
    for (const fn of [...(this._listeners[name] || [])]) fn(...args);
  }

  waterfall(seed: any, name: string, ...args: any[]): any {
    const listeners = [...(this._listeners[name] || [])];
    const runner = (i: number, current: any): any => {
      if (i >= listeners.length) return current;
      return listeners[i](current, ...args, (next: any) => runner(i + 1, next));
    };
    return runner(0, seed);
  }

  serial(name: string, ...args: any[]): void {
    for (const fn of [...(this._listeners[name] || [])]) fn(...args);
  }

  async parallel(name: string, ...args: any[]): Promise<void> {
    await Promise.all((this._listeners[name] || []).map((fn) => fn(...args)));
  }
}

export interface ServiceContext {
  state: any;
  get(name: string): Service;
  has(name: string): boolean;
  provide(name: string, svc: Service): Service;
  mount(plugin: ServiceCtor, config?: any, name?: string): Service;
  unmount(name: string): void;
  on(name: string, fn: Listener): () => void;
  emit(name: string, ...args: any[]): void;
  waterfall(name: string, seed: any, ...args: any[]): any;
  serial(name: string, ...args: any[]): void;
  parallel(name: string, ...args: any[]): Promise<void>;
  effect(fn: () => any): () => void;
  dispose(): void;
  [key: string]: any; // 动态服务访问：ctx.skills / ctx.derived ...
}

export type ServiceCtor = (new (ctx: ServiceContext, config?: any) => Service) & {
  inject?: string[];
  serviceName?: string;
};

export class Context implements ServiceContext {
  private _services: Record<string, Service> = {};
  private _events = new EventBus();
  private _disposers: Array<Array<() => void>> = [];
  private _effectStack: Array<Array<() => void>> = [];
  state: any = null;
  fiber: Fiber;

  constructor() {
    this.fiber = new Fiber(this);
  }

  // ---- 服务注册 ----
  provide(name: string, service: Service): Service {
    this._services[name] = service;
    (this as any)[name] = service; // 动态可读：ctx.<name>
    return service;
  }

  get(name: string): Service {
    const svc = this._services[name];
    if (!svc) throw new CordisError(`service not found: ${name}`);
    return svc;
  }

  has(name: string): boolean {
    return name in this._services;
  }

  // ---- 插件挂载（依赖注入） ----
  mount(plugin: ServiceCtor, config?: any, name?: string): Service {
    const inject: string[] = (plugin as any).inject || [];
    for (const dep of inject) {
      if (!this._services[dep]) {
        throw new CordisError(
          `service '${name || plugin.name}' requires '${dep}' but it is not mounted yet`
        );
      }
    }
    const svc = new plugin(this, config || {});
    const sname = name || (plugin as any).serviceName || deriveName(plugin.name);
    svc.name = sname;
    this.provide(sname, svc);
    svc.apply();
    return svc;
  }

  unmount(name: string): void {
    const svc = this._services[name];
    if (!svc) return;
    svc.dispose();
    delete this._services[name];
    delete (this as any)[name];
  }

  // ---- 事件 ----
  on(name: string, fn: Listener): () => void {
    const disp = this._events.on(name, fn);
    if (this._effectStack.length) this._effectStack[this._effectStack.length - 1].push(disp);
    return disp;
  }

  emit(name: string, ...args: any[]): void {
    this._events.emit(name, ...args);
  }

  waterfall(name: string, seed: any, ...args: any[]): any {
    return this._events.waterfall(seed, name, ...args);
  }

  serial(name: string, ...args: any[]): void {
    this._events.serial(name, ...args);
  }

  parallel(name: string, ...args: any[]): Promise<void> {
    return this._events.parallel(name, ...args);
  }

  // ---- 可逆副作用 ----
  effect(fn: () => any): () => void {
    const collected: Array<() => void> = [];
    this._effectStack.push(collected);
    try {
      const result = fn();
      if (typeof result === "function") collected.push(result);
      else if (result && typeof (result as any)[Symbol.iterator] === "function")
        collected.push(...(result as Iterable<() => void>));
    } finally {
      this._effectStack.pop();
    }
    this._disposers.push(collected);
    return () => this._disposeList(collected);
  }

  private _disposeList(collected: Array<() => void>): void {
    for (const d of [...collected].reverse()) d();
  }

  dispose(): void {
    for (const lst of [...this._disposers].reverse()) this._disposeList(lst);
    this._disposers = [];
  }
}

export class Fiber {
  ctx: Context;
  name = "root";
  constructor(ctx: Context) {
    this.ctx = ctx;
  }
  effect(fn: () => any): () => void {
    return this.ctx.effect(fn);
  }
}

export class Service {
  static inject: string[] = [];
  inject: string[] = [];
  name = "";
  ctx: ServiceContext;
  config: any;

  constructor(ctx: ServiceContext, config?: any) {
    this.ctx = ctx;
    this.config = config || {};
  }

  apply(): void {
    /* 挂载钩子，子类可重写 */
  }

  /** 卸载钩子（可选）：逆序清理本服务申请的资源。 */
  dispose(): void {
    /* 默认空 */
  }
}

function deriveName(ctorName: string): string {
  return ctorName.toLowerCase().replace(/service$/, "");
}
