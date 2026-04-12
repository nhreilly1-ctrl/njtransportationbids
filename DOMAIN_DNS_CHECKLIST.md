# Domain / DNS checklist

## Before you add the domain
- Decide whether your primary domain will be:
  - root domain: `yourdomain.com`
  - or `www.yourdomain.com`
- Keep the Render `onrender.com` URL active until your custom domain works.

## In Render
1. Open the web service.
2. Go to **Settings**.
3. Scroll to **Custom Domains**.
4. Click **Add Custom Domain**.
5. Enter your chosen domain.
6. Save.
7. Copy the DNS records Render tells you to create. citeturn884376search2

## In Cloudflare
1. Register or transfer the domain in Cloudflare Registrar. citeturn884376search10
2. Open the DNS settings for the zone.
3. Add the exact records Render requires.
4. Remove any `AAAA` records during Render custom-domain setup, because Render uses IPv4 and warns that `AAAA` records can cause unexpected behavior. citeturn884376search2
5. Wait a few minutes for propagation.

## Back in Render
1. Click **Verify** next to the domain.
2. Wait for verification and TLS issuance.
3. Test both the root and `www` version.
4. After it works, optionally disable the default `onrender.com` subdomain. citeturn884376search2

## Good practice
- Launch on the Render subdomain first.
- Add the custom domain only after the app, health check, and database seed are working.
