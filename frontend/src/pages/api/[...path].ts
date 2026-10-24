import type { NextApiRequest, NextApiResponse } from "next";
import { proxyRequest } from "@/lib/server-proxy";

export const config = { api: { bodyParser: false, responseLimit: "2mb" } };

export default function handler(request: NextApiRequest, response: NextApiResponse) {
  return proxyRequest(request, response);
}
