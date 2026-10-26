// Cloudflare nüsxəsi (wrangler.jsonc): fayl kimi tapılan sorğular bura gəlmir. mehsullar/ yüklənmir (fayl limiti) — əsas saytdakı eyni səhifəyə.
const MAIN = "https://ilhamisayev16-cyber.github.io/harda-ucuz";

export default {
  async fetch(req, env) {
    const u = new URL(req.url);
    if (u.pathname.startsWith("/mehsullar/")) return Response.redirect(MAIN + u.pathname, 301);
    return env.ASSETS.fetch(req);
  },
};
