import type { Config, Context } from "@netlify/functions";

export default async (_req: Request, _context: Context) => {
  return Response.json({
    ok: true,
    service: "netlify-demo",
    timestamp: new Date().toISOString(),
    message: "Serverless function routed via netlify.toml",
  });
};

export const config: Config = {
  path: "/api/status",
};
