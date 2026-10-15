# Posting cadence and anti-spam rules

- **One post per hour per account.** Twelve reels dropped at once from one account is exactly the pattern spam filters are built to catch. `queue_plan.py` refuses a spacing under one hour.
- **Instagram as Trial Reels.** Trial Reels are shown first to people who do not follow you, so every view is a stranger and a bad clip costs you nothing with your existing audience. Set `graduation_strategy` to MANUAL so you decide what graduates.
- **YouTube Shorts on the same cadence**, same slot as the Instagram post for the same clip so the two platforms are comparable.
- **Quiet hours.** Skip the hours your audience sleeps (`--quiet 23-06` in the local timezone). Do not read anything into slot time until you have 3 or more posts per hour bucket.
- **Order.** Lead with the clips you expect to travel (short quote hooks, number hooks), not the best clip. Keep a mix so one weak stretch does not run a whole day.
- **Approval gate.** `approved.json` is written by a human decision. The scheduler never guesses.
- **Scheduler.** Postiz (https://postiz.com) via its CLI: `postiz upload`, `postiz posts:create`. `postiz_schedule.py` prints the dry run first and stops on the first failure.
- Keep the subscription current. A lapsed scheduler on posting morning costs you the slot.
