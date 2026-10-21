import { Button } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md px-6 py-28 text-center">
      <p className="font-display text-8xl font-bold tracking-tight">404</p>
      <h1 className="mt-3 font-display text-2xl font-bold tracking-tight">We could not find that page</h1>
      <p className="mb-8 mt-2 text-mute">It may have moved, or the event is no longer listed.</p>
      <Button href="/" size="lg">Back to home</Button>
    </div>
  );
}
