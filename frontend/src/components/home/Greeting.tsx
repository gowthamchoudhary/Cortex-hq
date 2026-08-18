import { greetingForHour } from "@/lib/format";

export function Greeting({ name }: { name: string }) {
  const greeting = greetingForHour(new Date().getHours());
  return (
    <div>
      <h1 className="text-[28px] font-semibold tracking-tight text-foreground">
        {greeting}, {name} 👋
      </h1>
      <p className="mt-1.5 text-[14.5px] text-muted-foreground">
        Here's what's happening across your organization.
      </p>
    </div>
  );
}
