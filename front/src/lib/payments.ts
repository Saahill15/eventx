import type { Checkout } from "./types";

type CashfreeSdk = (opts: { mode: "sandbox" | "production" }) => { checkout: (o: { paymentSessionId: string; redirectTarget?: string }) => Promise<unknown> };
declare global { interface Window { Cashfree?: CashfreeSdk } }

const SDK = "https://sdk.cashfree.com/js/v3/cashfree.js";

function loadSdk(): Promise<CashfreeSdk> {
  return new Promise((resolve, reject) => {
    if (window.Cashfree) return resolve(window.Cashfree);
    const tag = document.createElement("script");
    tag.src = SDK;
    tag.async = true;
    tag.onload = () => (window.Cashfree ? resolve(window.Cashfree) : reject(new Error("The payment page could not be loaded.")));
    tag.onerror = () => reject(new Error("The payment page could not be loaded. Check your connection and try again."));
    document.head.appendChild(tag);
  });
}

/** Take the person to the gateway's page to pay. They come back to /payments/return, which asks the server what happened. */
export async function openCheckout(c: Checkout): Promise<void> {
  const Cashfree = await loadSdk();
  await Cashfree({ mode: c.env }).checkout({ paymentSessionId: c.payment_session_id, redirectTarget: "_self" });
}
