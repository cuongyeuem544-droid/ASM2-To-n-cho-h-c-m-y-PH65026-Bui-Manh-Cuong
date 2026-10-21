/**
 * Utility for redirection from Storefront to Admin Portal.
 * Uses NEXT_PUBLIC_ADMIN_URL environment variable.
 * Does NOT transmit access or refresh tokens via URL query (OWASP compliance).
 */

export function getAdminPortalBaseUrl(): string {
  if (typeof process !== "undefined" && process.env.NEXT_PUBLIC_ADMIN_URL) {
    return process.env.NEXT_PUBLIC_ADMIN_URL.replace(/\/+$/, "");
  }
  return "http://localhost:5173";
}

/**
 * Returns empty string to prevent transmitting JWT credentials via URL query parameters.
 * Retained for backwards compatibility with existing call sites.
 */
export function getAdminAuthQuery(): string {
  return "";
}

export function getAdminPortalUrl(preferredPort: 5173 | 8000 = 5173, path = ""): string {
  const cleanPath = path ? (path.startsWith("/") ? path : `/${path}`) : "/";
  const adminBase = getAdminPortalBaseUrl();
  return `${adminBase}${cleanPath}`;
}

/**
 * Navigates to the Admin Portal using NEXT_PUBLIC_ADMIN_URL without token query parameters.
 * If openInNewTab is true, opens in a new browser tab.
 */
export async function redirectToAdminPortal(path = "", openInNewTab = false): Promise<void> {
  if (typeof window === "undefined") return;

  const targetUrl = getAdminPortalUrl(5173, path);

  if (openInNewTab) {
    const newWindow = window.open(targetUrl, "_blank");
    if (!newWindow) {
      window.location.href = targetUrl;
    }
  } else {
    window.location.href = targetUrl;
  }
}
