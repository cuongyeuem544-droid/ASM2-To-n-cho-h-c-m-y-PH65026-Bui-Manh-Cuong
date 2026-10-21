/**
 * Utility for seamless cross-origin authentication and redirection
 * from Storefront (port 3000) to Admin Portal (port 5173 or port 8000).
 */

export function getAdminAuthQuery(): string {
  if (typeof window === "undefined") return "";
  try {
    const token = localStorage.getItem("pharmatrust_access_token");
    const refresh = localStorage.getItem("pharmatrust_refresh_token");
    if (!token) return "";
    const params = new URLSearchParams();
    params.set("token", token);
    if (refresh) params.set("refresh", refresh);
    return `?${params.toString()}`;
  } catch {
    return "";
  }
}

export function getAdminPortalUrl(preferredPort: 5173 | 8000 = 5173, path = ""): string {
  const query = getAdminAuthQuery();
  const cleanPath = path ? (path.startsWith("/") ? path : `/${path}`) : "/";
  const adminBase = process.env.NEXT_PUBLIC_ADMIN_URL || (typeof window !== "undefined" && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1" ? "https://h4care-api-staging.onrender.com" : `http://localhost:${preferredPort}`);
  return `${adminBase.replace(/\/+$/, "")}${cleanPath}${query}`;
}

/**
 * Actively checks which admin port is alive (8000 FastAPI SPA or 5173 Vite dev server)
 * and navigates to it with the credentials query attached.
 * If openInNewTab is true, opens in a new browser tab.
 */
export async function redirectToAdminPortal(path = "", openInNewTab = false): Promise<void> {
  if (typeof window === "undefined") return;

  const query = getAdminAuthQuery();
  const cleanPath = path ? (path.startsWith("/") ? path : `/${path}`) : "/";

  // Check port 5173 first with 300ms timeout
  let targetUrl = `http://localhost:8000${cleanPath}${query}`;
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 300);
    await fetch("http://localhost:5173/", { mode: "no-cors", signal: controller.signal });
    clearTimeout(timeoutId);
    targetUrl = `http://localhost:5173${cleanPath}${query}`;
  } catch {
    targetUrl = `http://localhost:8000${cleanPath}${query}`;
  }

  if (openInNewTab) {
    const newWindow = window.open(targetUrl, "_blank");
    if (!newWindow) {
      window.location.href = targetUrl;
    }
  } else {
    window.location.href = targetUrl;
  }
}
