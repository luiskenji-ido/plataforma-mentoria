import type { ZodType } from "zod";

export class ValidationError extends Error {
  readonly statusCode = 400;
  constructor(readonly issues: { path: string; message: string }[]) {
    super(issues.map((i) => (i.path ? `${i.path}: ${i.message}` : i.message)).join("; "));
  }
}

/** Valida a entrada com Zod; erro 400 com a lista de campos (sem eco de valores). */
export function parse<T>(schema: ZodType<T>, value: unknown): T {
  const r = schema.safeParse(value);
  if (!r.success) {
    throw new ValidationError(r.error.issues.map((i) => ({ path: i.path.join("."), message: i.message })));
  }
  return r.data;
}
