# Install URL Setup

The install URL `https://install.clawos.io` redirects to the GitHub raw URL of `install.sh`.

## Cloudflare Worker Setup

Create a new Worker with this code:

```javascript
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    // Redirect to GitHub raw install.sh
    const GITHUB_RAW = 'https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh';
    
    return Response.redirect(GITHUB_RAW, 302);
  }
};
```

## DNS Setup

1. Add a CNAME record: `install.clawos.io` → `your-worker.your-subdomain.workers.dev`
2. Enable Cloudflare proxy (orange cloud)

## Rotating the URL

If you need to change the underlying URL:

1. Update the Worker code with the new redirect target
2. Deploy the Worker
3. No DNS changes needed

## Testing

```bash
curl -I https://install.clawos.io
# Should return 302 redirect to raw GitHub URL
```

## Fallback

If the custom domain fails, users can always use the direct GitHub URL:
```bash
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh | bash
```
