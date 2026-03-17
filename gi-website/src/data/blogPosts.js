export const posts = [
  {
    slug: 'building-with-llms',
    title: 'Building Real Products with LLMs',
    date: '2026-03-10',
    category: 'AI & Engineering',
    excerpt:
      'Large language models are no longer just demos — here's what I've learned after shipping an LLM-powered feature to production.',
    content: `
Large language models have gone from research curiosity to production staple in under two years. Having shipped an LLM-powered feature, here are the lessons that stuck with me.

## Start with the failure modes

Before you build, enumerate what can go wrong. LLMs hallucinate, they're non-deterministic, and they can be steered by adversarial inputs. Design your UX to handle partial or wrong answers gracefully.

## Structured outputs are your friend

Instead of free-form text, ask the model to respond in JSON or with clearly delimited sections. This makes downstream parsing reliable and reduces the surface area for surprises.

## Evaluate, evaluate, evaluate

The biggest mistake is shipping without a proper eval suite. Create a golden set of inputs and expected outputs early, and run it on every model change. What gets measured gets managed.

## Cost and latency matter

A 2-second response feels fast in a chat UI but agonizing in a form field. Profile your latency, batch where possible, and cache aggressively.

Building with LLMs is like hiring a brilliant but unpredictable colleague — you need strong scaffolding around them to make it work in production.
    `.trim(),
  },
  {
    slug: 'minimalist-software-design',
    title: 'The Case for Minimalist Software Design',
    date: '2026-02-22',
    category: 'Design & Philosophy',
    excerpt:
      'Every feature you add is a feature someone has to learn, maintain, and eventually delete. A reflection on building less, better.',
    content: `
The best software I've ever used does very few things — and does them exceptionally well.

## Complexity compounds

Each new feature adds its own surface area, its own edge cases, and its own documentation burden. Two features don't add two problems; they can multiply them. The interaction between features is where bugs hide.

## Users want outcomes, not features

When you dig into what users actually want, it's rarely a specific button. It's a result. The job of a designer is to find the shortest, clearest path to that result — even if that means fewer controls.

## How to resist feature creep

- Say "not now" instead of "no" — it's easier to revisit than undo
- Ask "what problem does this solve?" before any new feature is specced
- Delete before you add: could an existing feature, improved, do the same job?

Minimalism in software isn't about aesthetics. It's about respect — for the user's attention, and for the next developer who has to read the code.
    `.trim(),
  },
  {
    slug: 'google-cloud-for-solo-devs',
    title: 'Google Cloud for Solo Developers',
    date: '2026-02-05',
    category: 'Cloud & DevOps',
    excerpt:
      'Firebase, Cloud Run, and BigQuery as a three-layer stack that punches well above its weight for a single developer.',
    content: `
Running production infrastructure solo sounds daunting, but Google Cloud's managed services let a single developer operate systems that would have needed an ops team a decade ago.

## My three-layer stack

**Firebase Hosting** — zero-config CDN for static frontends. \`firebase deploy\` and you're done. Free tier covers most hobby projects.

**Cloud Run** — serverless containers that scale to zero. No Kubernetes complexity. Write a Dockerfile, push to Artifact Registry, and deploy. You only pay for actual request time.

**BigQuery** — the analytics superpower. Petabyte-scale SQL that costs cents for small workloads. Feed it with scheduled queries or Dataflow, query it with Data Studio or a Jupyter notebook.

## What I'd add next

When you need a database, Cloud SQL (managed Postgres) is the natural next step. For async jobs, Cloud Tasks or Pub/Sub. These compose well — each piece is replaceable as you grow.

The biggest win is not having to manage servers. Every hour not spent on infra is an hour spent on product.
    `.trim(),
  },
]
