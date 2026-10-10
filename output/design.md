# Campus Customs Ops Desk: Design Notes

The dashboard (`frontend/`, React + Vite + TypeScript) is meant to feel like a bright, tidy shop counter: a clean **white desk** with **pink ink** for everything that matters. (It started black-and-pink. After using it, the user asked for a white background and a signature area that's easier to find. Both changes are described below.) Paper tickets sit on the left, the team works in the middle, and the cash drawer and pen sit on the right. Each choice below is there so a manager can understand the shop in five seconds and enjoy spending an afternoon at it.

Screenshots: `output/screenshots/desk_idle.png`, `desk_running.png`, and `desk_ticket101_resolved.png`.

## How to start it

```bash
# terminal 1: the backend (Problem 7)
cd backend && source ../.venv/bin/activate && uvicorn main:app --reload --port 8000
# terminal 2: the desk
cd frontend && npm run dev
```

`npm run dev` opens the browser automatically. The front end talks to `http://localhost:8000` (set in `frontend/.env` as `VITE_API_URL`). The backend allows the Vite origin `http://localhost:5173`, plus any other `localhost` port in case 5173 is already busy.

## Layout: three columns, read left to right like the work itself

| Left: **Ticket rail** | Center: **The floor** | Right: **The pen and the drawer** |
|---|---|---|
| The three tickets as paper stubs | The selected ticket's key numbers, the agent team, and then what each agent did | **Sign here** (approvals waiting for your signature), then live "desk chatter" |

- **The order matches the job:** pick a ticket, watch the team, sign the money. Your eye moves the same direction as the work, so the layout itself teaches you how to use it.
- **A sticky top bar holds the two things you must never lose track of:** the **How the desk works** steps and the **Checking balance**.

## Making the signature impossible to miss

In testing, the user said it took a long time to find where to sign, so signing now has four ways in:
1. **A full-width pink banner** sits under the header whenever anything is waiting: "3 payments need your signature · $3,248.00 · **Sign now**". It stays pinned while you scroll.
2. **"Sign now" scrolls to the tray**, flashes it pink twice, and puts the cursor in the signature box if you haven't signed yet. Header step ③ "Sign off payments" does the same thing.
3. **The tray is titled "Sign here"** with a pulsing count badge, a pink border, and a pink wash while anything is pending.
4. **The signature box looks like a signature line**: a pink-framed card labeled *Your signature*. Your name appears in a handwriting font on a dark rule, like signing a cheque. It pulses until you type a name.

On narrower windows (laptop width and below), the whole **Sign here** tray moves to the top of the page, beside the tickets instead of below them. That's the most likely reason it was hard to find before.

## Easy to follow

- **Three numbered steps in the header:** ① Pick a ticket ② Start the agent team ③ Sign off payments. The step you're on glows pink, and finished steps turn mint with a check. The board always tells you what to do next.
- **Plain-English everywhere:** tools are translated into verbs a manager understands. `check_stock` becomes "Checked the shelves," `get_cash_position` becomes "Checked the cash drawer," and `request_payment` becomes "Queued a payment for you to approve."
- **Every empty state is an instruction,** never a blank box. For example, "Nothing to sign. When an agent prepares a payment or purchase order, it will wait here for you."
- **Friendly guardrails:** the Start button explains itself ("About 30–60 seconds. Nothing is sent and no money moves without you"). It turns into a live timer ("Agents at work · 28s") and is disabled while another ticket is running. Approve is disabled until you type your name, and a hint says so.
- **Backend offline?** A red banner shows the exact command to start it.

## Numbers you can read across the room

- **Checking balance:** about 44 px, monospaced, tabular figures, dark on a soft pink card. Under it are **Waiting for approval** and **If all approved**, so you see today's cash and tomorrow's cash together. If approving everything would go negative, that line turns red.
- **Ticket figures:** the hero row shows each ticket's numbers as large tiles: quantity, invoice amount, rent, and "Due in 2 days." Urgent ones (an overdue invoice, rent due within 3 days) get a pink border and pink glow.
- **Approval cards:** each one shows its amount at about 38 px, plus **"Checking after this: $2,560.00"**, so you know the consequence *before* you sign.
- **Stubs and agent cards:** quantities, sizes, tool-call counts, and assignment counts are bold monospace.

## How the agents read differently

Each agent has **its own colour, icon, and one-line job title**, so you recognise them without reading:

| Agent | Icon | Colour | Why |
|---|---|---|---|
| Boss | Crown | Hot pink (the brand colour) | The lead. Round avatar with a halo, and the largest card |
| Inventory | Stacked boxes | Amber | Warm "stock room" tone |
| Accounting | Calculator | Mint | Money that is fine |
| Facilities | Building | Sky blue | The physical space |
| Customer Service | Speech bubble with a heart | Lavender | Soft and friendly, like the drafts it writes |

- **The floor plan is the org chart:** Boss sits at the head desk, and a "wire" runs down to the four specialists. While a specialist is working, **its wire lights up in its colour and pulses**, so parallel hand-offs show up as two or three wires glowing at once.
- **Every agent card has a live speech bubble** (what it's doing *right now*, such as "Checked if the vendor will ship · vendor id 1") and a **status pill**: Idle (coffee cup), Thinking (animated dots), Working (wrench), Done (check), or Stuck (warning).
  - Active cards glow in their colour and the avatar gently bobs. Idle agents fade back, so your eye lands on whoever is working.
- **Desk chatter** (right column) is a timeline with one coloured dot per agent. Hand-offs read as "**Boss → Inventory**: …", and final answers are highlighted.

## How resolved tickets show up

- **Rubber stamp:** when a run finishes, the backend marks the ticket resolved. The stub gets a tilted pink **RESOLVED** stamp that thumps in with a slight overshoot, the status pill turns mint ("Resolved"), and the text dims so open work stands out.
- **Celebration:** a short burst of pink confetti, plus a toast: "Ticket #101 resolved. Check the summary and any payments waiting for you."
- **Approvals stay visible:** "Resolved" means the *team's* work is done. Anything that still needs a human appears on the stub ("2 payments need your signature") and in the tray, so a resolved ticket never hides an unpaid bill.
- **"What each agent did":** after the run, each agent gets a card with its colour stripe. It shows the agent's final words, chips for the tools it used (×2 for repeats), who it handed off to, and in pink what "Needs your OK." Boss's card spans the full width and lists the next steps for the human.
- **Drafts look like paper:** they're pinned to the board as slightly tilted cream note cards, labeled **"Draft #1 · not sent"**, so it's obvious nothing was emailed.

## How cash shows up

- **One cash display:** the till in the top right is the single source of truth, from `GET /api/cash` (the `cash_accounts` checking balance).
- **Pending requests are cheques:** each one on the right is a dashed-border cheque with diagonal "security paper" stripes. It shows the amount, what it's for ("Invoice #501 · Bulldog Print Co"), who prepared it, and their reason.
- **Approving takes two clicks on purpose:** **Approve** becomes **"Yes, pay $840.00"**. The card names who's signing ("Signing as …", remembered in the browser).
- **When a payment goes through,** the till **counts down** to the new balance over about 1.4 seconds, a pink **"−$840.00"** tag drops off the drawer, and a toast confirms "Checking went from $3,400.00 to $2,560.00." The payment then moves to **Signed & paid** with the signer's name.
- **Cards that can't be paid warn you first:** if a cheque would overdraw the account, it turns red and says "not enough cash, so this will be refused." If you try anyway, the backend refuses (409) and the toast explains why. Balances never go negative.

## Creative touches that make it feel like a place

- **Paper stubs with punched notches** on both sides, like tickets torn from a spike. Selecting one lifts it with a pink outline, and a running ticket pulses.
- **White desk, pink ink:** pure white background, white cards with soft shadows, and hot pink (#e6197a) only where action or money is involved. Agent colours were darkened (amber #d97706, mint #0f9f77, blue #2f6fe0, violet #8b45e0) so their names stay readable on white.
- **Motion that carries meaning:** bobbing avatars mean "working," pulsing wires mean "hand-off," a count-down means "money left," and a stamp and confetti mean "done." Nothing animates just for decoration.
- **Toasts written in a human voice:** "Boss is reading ticket #101…", "Fresh start: the database is back to the original values."
- **Shareable view:** the URL remembers the open ticket (`#ticket=101`), so a refresh or shared link opens the same view.
- **Easy reset:** the reset button lives quietly in the footer and asks for confirmation, describing exactly what will happen first.

## Accessibility and practicality

- **Contrast:** dark text on white, plus darker pink and agent colours, keeps text readable.
- **Colour is never the only signal:** agents also have icons and names, states have icons and words, and urgent figures have borders as well as colour.
- **Layout adapts:** three columns on a wide screen, two on a laptop, one on a narrow window.
- **No external services or fonts**, only system fonts plus `lucide-react` icons. The page polls the backend every 1.2 s during a run and every 8 s otherwise, so it stays live without hammering anything.
