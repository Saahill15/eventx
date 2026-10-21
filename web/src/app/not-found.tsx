import { Button } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md px-6 py-24 text-center">
      <p className="font-display text-7xl font-black text-hive">404</p>
      <h1 className="mt-3 font-display text-2xl font-extrabold tracking-tight">We could not find that page</h1>
      <p className="mb-7 mt-2 text-neutral-500">It may have moved, or the event is no longer listed.</p>
      <Button href="/">Back to home</Button>
    </div>
  );
}
