import { api } from "./client";

export const searchApi = {
  search: (q: string, type = "all", cursor?: string) =>
    api.get("/search", { params: { q, type, cursor, limit: 20 } }).then((r) => r.data),
};
