# Example daily agent prompt

Replace the bracketed values before registering this in a browser-capable agent
scheduler. This is an instruction template, not an installed automation.

```text
Operate the Instagram publication workflow for [authorized account] using the
repository at [local repository path]. Read docs/OPERATIONS.md,
docs/LOOP_ENGINEERING.md, and local config.json. Treat this run as one bounded
loop iteration: observe, decide, claim, act, verify, persist, then wait for the
next trigger. Inspect python3 agent.py status and run python3 agent.py tick.

Inspect unresolved PUBLISHING and VERIFY_REQUIRED records across dates before
new submissions. The CLI's current-date checks alone do not reconcile older
uncertain outcomes. Current browser observations and durable records must guide
recovery; conversation memory is not sufficient evidence.

Respect the configured timezone, current local date, pause control, and one-post
daily limit. When formal brand content is not ready, retain the current state and
stop. Do not repeat technical tests or invent business claims and assets.

When approved brand rules and media are available, prepare reviewed production
manifests in inbox with ready=true. Verify facts and media rights. For a due job,
claim it in the ledger and perform the browser workflow with the current tool
documentation and the owner's authorized account session.

Immediately before Share, run the final check. Submit once, observe the platform
result, reopen the actual post, and record only real verified evidence. An
uncertain result requires reconciliation before any retry.

Do not expose credentials or commit private evidence and runtime state. Do not
create paid services, send private messages, or reply to comments unless separately
authorized. Keep unchanged pending states quiet; report a real publication,
failure, material recovery, or action needed from the owner.

Record planned time, actual run time, decision, job ID, resulting state, and any
real publication/evidence reference locally for the next iteration. Distinguish
schedule registration, actual invocation, local execution, and verified publication.
Do not present the local claim mechanism as an end-to-end exactly-once guarantee.
```
