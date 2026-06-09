# 🌊 Vibe Coding with KRONOS

> **For people who build apps with AI — and don't want to learn the boring IT stuff.**
> Plain words: what this is, why it helps you, and how to set it up in about 5 minutes.
> No computer-science degree needed. If you can copy-paste, you can do this.

---

## The problem (you've felt this)

You're building something with an AI assistant. It writes code fast. It says:

> "✅ Done! Everything works."

…and later you find out:

- it never actually ran the tests,
- it skipped half of what it promised,
- the notes/docs are out of date,
- or the "fix" quietly broke something else.

The AI isn't lying on purpose — it's just **over-optimistic**. It *thinks* it's done. And by the
time you notice, you've already built three more things on top of the broken one. 😬

---

## What KRONOS does (one sentence)

**KRONOS is a referee that checks your AI's work before it gets saved — so "done" actually means done.**

It sits quietly in the background. Every task moves through 5 simple steps:

```
PLAN  →  CODE  →  TEST  →  DOCS  →  SAVE
 │        │        │        │         │
 plan it  build it run the  update    save it
          really   tests    the notes  for real
```

Right before your work is saved, KRONOS looks at each step and asks: **"Did this really happen?"**

- Is there a real plan?
- Did the code actually change?
- Did the tests actually run — and pass?
- Were the notes updated?

If the AI ticked a box it didn't earn, KRONOS **stops the save** and tells you what's missing.
You simply *can't* accidentally ship half-finished work.

---

## Why YOU want it (even if you're "not a real developer")

- 🧠 **You don't have to be the quality checker.** The referee checks the AI's homework for you.
- 😌 **No more "I thought it was done."** If it's not done, you find out *now* — not next week.
- 🗂️ **Your project stays tidy by itself** — every change has a plan, a test, updated notes, and history.
- 🛡️ **It never touches your code.** It only watches the moment you *save*. Worst case it says
  "wait — finish this first."

Think of it like a spell-checker. But instead of catching typos, it catches **unfinished work**.

---

## Set it up (5 minutes, just copy-paste)

KRONOS works with **[Claude Code](https://claude.com/claude-code)** — the AI coding tool that runs
in your terminal. (You need that installed first. If you already vibe-code with it, you're ready.)

**1. Download KRONOS**

```bash
git clone https://github.com/dzylab/kronos
cd kronos
```

**2. Run the installer**

```bash
./install.sh
```

**3. Turn it on**

The installer prints a small snippet. Copy it into your `~/.claude/settings.json` file — the
installer shows you exactly what to paste. (This is the line that says "hey, watch my saves.")

**4. Check it worked**

```bash
python ~/.claude/hooks/check-workflow.py --self-test
```

If you see **`36 passed`** — you're done. 🎉

*(You don't need to understand every step. Just run them top to bottom.)*

---

## How to use it day-to-day

Here's the secret: **you barely do anything. You just talk to your AI like normal.**

| You type (to your AI) | What happens |
|---|---|
| `/kronos-start build a login page` | The AI writes a short plan and starts tracking the task |
| `/kronos-next` | Move to the next step (code → test → docs → save) |
| `/kronos-status` | "Where are we?" — shows what's done and what's left |

The AI drives; you just steer. When it tries to save, the referee quietly checks everything first.

---

## "It blocked my save — help!" 🚧

Don't panic. That's KRONOS doing its job — it caught something unfinished.

1. **Read the message.** It says exactly what's missing (for example: *"the tests never ran"*).
2. **Ask your AI to finish that step.**
3. **Save again.** It lets you through.

For a genuine emergency (you *must* save this second), there's an escape hatch — but use it rarely.
KRONOS writes every use down, so nothing is ever hidden.

---

## Quick answers

**Do I need to understand how it works inside?**
No. Install it and let it watch. That's the whole point.

**Will it slow me down?**
A little. But it saves you from shipping broken work — which costs *way* more time than it saves.

**Is my code safe?**
Yes. KRONOS only acts when you *save* (a "commit"). It reads, it checks, it says yes or no.
It never edits your code.

**What about a tiny throwaway experiment?**
It only kicks in when you have an active task. No task = no checking. Nothing gets in your way.

**Does it cost anything / phone home?**
No. It's free, open-source, and runs entirely on your own machine.

---

## Want the full details?

- **[README.md](README.md)** — the complete overview.
- **[KRONOS.md](KRONOS.md)** — how the engine works, every option.
- **[THREAT_MODEL.md](THREAT_MODEL.md)** — honestly, what it does and does *not* protect against.

---

Happy vibe coding. 🌊 **Build fast — and actually finish.**
