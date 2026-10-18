import axios from "axios";

import { env } from "@/lib/env";

export const apiClient = axios.create({
  baseURL: env.apiBaseUrl,
  timeout: 30_000,
});

apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    if (!err.response) {
      err.message = `API indisponível (${env.apiBaseUrl}). Verifique se o uvicorn está rodando.`;
    }
    return Promise.reject(err);
  },
);
