import { AwsCatalog } from "./aws/catalog";
import { AwsSession } from "./aws/credentials";
import { AwsOperations } from "./aws/operations";
import { AwsPriceList, type PriceSource } from "./aws/pricing";
import { DockerImages } from "./deployment/docker";
import { httpCheck, type HttpCheck } from "./deployment/health";
import { OperationManager } from "./deployment/operations";
import { Workflows } from "./deployment/workflows";
import { StackService } from "./pulumi/stacks";
import { ConfigStore } from "./services/configStore";
import { runProcess, type Runner } from "./services/process";
import type { Settings } from "./settings";

export interface AppContext {
  settings: Settings;
  session: AwsSession;
  catalog: AwsCatalog;
  aws: AwsOperations;
  prices: PriceSource;
  stacks: StackService;
  store: ConfigStore;
  operations: OperationManager;
  workflows: Workflows;
  runner: Runner;
  http: HttpCheck;
}

export function createContext(settings: Settings, overrides: Partial<AppContext> = {}): AppContext {
  const session = overrides.session ?? new AwsSession();
  const runner = overrides.runner ?? runProcess;
  const aws = overrides.aws ?? new AwsOperations(session);
  const prices = overrides.prices ?? new AwsPriceList(session);
  const stacks = overrides.stacks ?? new StackService(settings.stateDir, session);
  const operations = overrides.operations ?? new OperationManager(settings.stateDir);
  const http = overrides.http ?? httpCheck;
  const workflows =
    overrides.workflows ??
    new Workflows({ session, stacks, aws, docker: new DockerImages(runner), runner, http, prices, repoRoot: settings.repoRoot, operations });
  return {
    settings,
    session,
    catalog: overrides.catalog ?? new AwsCatalog(session),
    aws,
    prices,
    stacks,
    store: overrides.store ?? new ConfigStore(settings.stateDir),
    operations,
    workflows,
    runner,
    http,
  };
}
