import type { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: '*', allow: '/' },
    sitemap: 'https://rosplus.kchin1977.chatgpt.site/sitemap.xml',
    host: 'https://rosplus.kchin1977.chatgpt.site',
  };
}
