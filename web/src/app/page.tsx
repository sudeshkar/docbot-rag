import Link from "next/link";
import Logo from "@/components/Logo";

const features = [
  ["Grounded answers", "Every answer cites the exact passage it came from. No source, no answer."],
  ["Hybrid retrieval", "Semantic vector search plus keyword search, fused with reciprocal rank fusion."],
  ["Smart chunking", "Heading-aware, recursive, semantic or fixed. Pick per bot and compare with evals."],
  ["Gap analytics", "See the questions your docs couldn't answer, so you know what to write next."],
];

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 py-6 sm:px-6">
      <header className="flex items-center justify-between">
        <Logo />
        <nav className="flex gap-2 text-sm">
          <Link href="/login" className="rounded-lg px-3 py-2 text-ink-2 hover:bg-surface-2">Log in</Link>
          <Link href="/signup" className="rounded-lg bg-accent px-3 py-2 font-medium text-accent-ink">Get started</Link>
        </nav>
      </header>

      <section className="flex flex-1 flex-col justify-center py-16">
        <h1 className="max-w-2xl text-4xl font-semibold tracking-tight sm:text-5xl">
          A support bot that only answers from your docs.
        </h1>
        <p className="mt-4 max-w-xl text-lg text-ink-2">
          Upload PDFs or crawl your help center. Get an embeddable chat widget that answers with citations,
          and a dashboard of the questions it couldn&apos;t answer.
        </p>
        <div className="mt-8 flex gap-3">
          <Link href="/signup" className="rounded-lg bg-accent px-5 py-2.5 font-medium text-accent-ink">Create a bot</Link>
          <Link href="/login" className="rounded-lg border border-line px-5 py-2.5 font-medium hover:bg-surface-2">Log in</Link>
        </div>

        <div className="mt-16 grid gap-4 sm:grid-cols-2">
          {features.map(([title, body]) => (
            <div key={title} className="rounded-xl border border-line p-5">
              <h2 className="font-medium">{title}</h2>
              <p className="mt-1 text-sm text-ink-2">{body}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
