# Modes, privacy and sign-in

Every storyboard sets `mode:`. The CLI refuses to render without it and enforces the rules below
when it validates the storyboard and again when it checks the finished video.

## Which mode?

| Situation | Mode |
|---|---|
| You show a client the system you built for them, with their own data | `handover` |
| Anyone else will see the video: portfolio, website, proposal, prospects | `public` |
| The real system, but with made-up data you seeded | `public` with `seeded_test_data: true` |
| A private copy of a client's app on your machine, with made-up data | `handover` with `local_copy: true` |
| You are not sure | `public` |

## Public mode

Public videos must not show real people, real clients or contact details.

- **Data.** Best: a demo replica with fictional data. Next: the real system with seeded test data.
  Last: the real system with every identifying element replaced or blurred.
- **Banned terms.** `banned_terms` lists words that must never appear: a client's name, a company,
  an email domain, real people. The check ignores case and matches inside words.
- **Contact details.** The validator also rejects email addresses, phone numbers (nine or more
  digits, ISO dates excepted) and web addresses. A web address is anything starting with
  `http://`, `https://` or `www.`, or a bare name ending in `.com`, `.net`, `.org`, `.io`, `.co`,
  `.ai`, `.app`, `.dev`, `.us`, `.uk`, `.biz`, `.info`, `.me`, `.xyz` or `.cloud`.
- **Allowed hosts.** `allowed_hosts` lists hosts that may appear, such as your demo app's own
  hostname. `localhost` and the local loopback address always pass.
- **Where it runs.** At validation, on every declared text (title, captions, slides, narration),
  including the text of a `cutdown` as it will be rendered and of each `variants:` entry. After
  recording, the gate runs the same scan on the text that was actually on each screen: visible
  text, page title, input values, and `placeholder`, `title` and `alt` attributes.
- **No sign-in unless seeded.** `auth` must be empty unless `seeded_test_data: true`.
- **Claims.** Narration states only facts you can trace. List the sources under `sources:`.
- **Delivery.** `private_link` is not allowed. `delivery.public: true` lets `studio publish` upload
  the video to your site (see [publishing.md](publishing.md)).

## Handover mode

A handover video shows a client their own system with their real records. It is private.

- **Audience.** The client who owns the system. Never a public site, a portfolio or a proposal.
- **Required.** `client` (a folder-safe slug), `auth` (a saved sign-in), `delivery.public` false.
- **Output.** `out/clients/<client>/<name>/`. The first handover render for a client also writes
  `out/clients/<client>/RETENTION.md`: the date, a note that the folder holds real data, and a blank
  "Received by" line for you to fill in. Delete the folder when the client no longer needs it.
- **Still masked.** Secrets are blurred in handover mode too (see below). Also mask data that belongs
  to people other than the client, with `redact` selectors.
- **Look.** A handover video is not framed unless you set `style.frame: true`. The theme, captions,
  subtitles, zoom and music settings apply either way.
- **Delivery.** The MP4 stays on your machine by default. You send it yourself. A private link on
  your own server is optional and needs an expiry date ([publishing.md](publishing.md)).

## Live systems are read-only by default

In handover mode, against a real system, the validator refuses steps that may write data:

- every `type` step, and
- every `click` step whose `target` or `text` contains one of these whole words, in any case:
  apply, send, delete, remove, save, submit, confirm, approve, decline, reject, archive, create,
  update, publish, post, merge, import, sync, run, undo, restore, pay, charge, invite, disconnect,
  revoke, reset.

To keep such a step, set `live_write: true` and `confirmed_by_owner: true` on it. The second flag
is your record that the system's owner agreed. `live_write: true` without it is an error in both
modes. Prefer the client's test or sandbox records for any write.

The check reads words, not behaviour. A click on a button with a neutral name can still write, and
`hover`, `wait_for`, `scroll`, `goto` and `pause` steps are not checked. Review every click yourself.

## local_copy

When the real system is live and the walkthrough must fill in forms, record a private copy of the
same release on your own machine instead, with made-up data:

```yaml
mode: handover
client: acme
local_copy: true
base_url: "http://localhost:3217"
```

`base_url` must be `localhost` or a loopback address. Nothing live is touched, so `auth` may be
empty and form steps need no `live_write`. The video is still handover: private, for that client.
Say in `intro_note` that the data is made up.

## Signing in

Reach a system behind a sign-in with a saved session. You sign in yourself. The tool never types
a password and never reads what you type.

```
studio login acme-crm        # a visible browser opens; you sign in, including any 2FA
studio render walkthrough.yaml
studio logout acme-crm       # deletes the saved session
```

- **Which page opens.** `login_url`, else `base_url`, of the storyboard in the workspace that has
  `auth: acme-crm` (it looks at `*.yaml` in the workspace and in `storyboards/`). Or pass `--url`.
- **Saving.** The session saves by itself once you are off the login page with no password field for
  about six seconds. You can also press Enter in the terminal, or close the tab.
- **Where it lives.** One file per name, outside any project folder, never uploaded:
  - Windows: `%LOCALAPPDATA%\demo-studio\auth\<name>.json`
  - macOS: `~/Library/Application Support/demo-studio/auth/<name>.json`
  - Linux: `$XDG_DATA_HOME/demo-studio/auth/<name>.json` (default `~/.local/share/demo-studio/auth/`)
- **Permissions.** On Windows `studio login` restricts the file to your user. On macOS and Linux it
  sets the file mode to 600. Treat the file like a password: whoever holds it is signed in as you.
- **After each render.** Apps rotate their tokens while you record, so the file is rewritten with
  the refreshed session. Only cookies and storage entries whose names look like sign-in data are
  kept (names containing token, session, auth, jwt, credential, oidc, msal, or Firebase and
  Supabase sign-in keys). Other stored data is dropped. If the result is over 1 MB the old file is
  kept and a warning is printed.
- **Expiry.** If a password field shows up during a render, the render stops and tells you to run
  `studio login <name>` again.
- **Cleanup.** Run `studio logout <name>` when the work is done. It deletes the file.

## Secrets that are always masked

These rules are built in and apply in both modes. Your `redact` lists add to them.

**Elements blurred by selector:**
- password fields
- any element with a `data-secret` attribute
- inputs whose `name` contains `secret`, `token`, `apikey` or `api_key`
- card number and card security code inputs (`autocomplete` of `cc-number` or `cc-csc`)

**Text blurred by pattern.** If an element's text, or an input's value, contains any of these, the
element is blurred:
- API keys that start with `sk-`, Stripe keys (`sk_`, `pk_` or `rk_` with `live` or `test`)
- AWS access key ids, Google API keys, Slack tokens (`xox...`)
- GitHub tokens (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`)
- JSON web tokens (starting `eyJ`)
- hex strings of 32 or more characters
- numbers of 13 to 19 digits, with spaces or dashes allowed (card numbers; long ids can match too)
- IBANs
- webhook URLs (Slack hooks, and addresses containing `/webhook` or `/hooks/`)
- URL parameters named `token`, `key`, `secret`, `sig`, `signature`, `apikey`, `api_key` or
  `access_token` with a value of six or more characters

Patterns ignore case. Text shorter than six characters is skipped.

**How it works.** A script runs in the page before the app's own scripts. It scans text and input
values on load, on every DOM change and every 0.4 s, and blurs the element with a 10 px CSS blur
before it paints. Each element is blurred and reported once, so the counts in `masked.json` and in
the Masked section of `REPORT.md` are per step: an element is listed under the step during which it
was first blurred, not again under every later step. A page that reloads starts a new document, so
its elements can be reported again. Selector blurs are not counted.

**What it does not cover.** The script runs in the top page only. It does not look inside iframes or
shadow DOM, open or closed, and it cannot see text inside images, canvas or video. A secret split
across several elements, or shorter than six characters, can slip past the patterns. The frame
review in the [quality gate](quality-gate.md) is the check for all of these.

`strings.json` in the output folder holds the visible text of every screen, with pattern matches
replaced by `[masked]`. Text hidden only by a selector is not removed from that file. Keep the
output folder private, especially in handover mode.

## Delivery

| Mode | Default | Optional |
|---|---|---|
| `public` | Local files until `delivery.public: true`, then `studio publish` writes to your site | none |
| `handover` | The MP4 stays local; you send it | A private link: ssh target with Caddy, an expiry date required |

`studio publish` never puts a handover video on the public site. See [publishing.md](publishing.md).
