# 🚀 Push to GitHub

The repo has been git-init'd, committed, and is **ready to push**.  The agent
could not run `gh repo create` itself (no GitHub CLI installed on the machine
at build time), so pick **one** of the three options below to upload.

The target repository name is **`Antonio-cccj/a-share-pairs-agent`**
(public).

---

## Option A — One-liner with `gh` CLI (recommended, ~30 s)

If you don't already have `gh` installed:

```powershell
# Windows
winget install --id GitHub.cli --silent --accept-package-agreements --accept-source-agreements
# (open a new PowerShell window after install so PATH refreshes)
```

Then:

```powershell
cd "C:\Users\Anton\Desktop\Quantitative research\event-driven-pairs-trading-cn"
gh auth login                  # browser-based OAuth
gh repo create Antonio-cccj/a-share-pairs-agent --public --source=. --push
```

That's it — the repo is online with CI auto-running.

---

## Option B — Manual `git remote add` + push

Create the empty repo at <https://github.com/new>:

- Owner: `Antonio-cccj`
- Repository name: `a-share-pairs-agent`
- Visibility: Public
- Leave **uncheck** "Initialize this repository with a README" (we already have one)

Then locally:

```powershell
cd "C:\Users\Anton\Desktop\Quantitative research\event-driven-pairs-trading-cn"
git branch -M main
git remote add origin https://github.com/Antonio-cccj/a-share-pairs-agent.git
git push -u origin main
```

You will be prompted for credentials.  If your GitHub account uses 2FA, generate a
[Personal Access Token (PAT)](https://github.com/settings/tokens) with `repo` scope
and paste it as the password.

---

## Option C — SSH key

```powershell
cd "C:\Users\Anton\Desktop\Quantitative research\event-driven-pairs-trading-cn"
git branch -M main
git remote add origin git@github.com:Antonio-cccj/a-share-pairs-agent.git
git push -u origin main
```

Requires that your SSH key is uploaded to <https://github.com/settings/keys>.

---

## Sanity check after push

```powershell
gh repo view Antonio-cccj/a-share-pairs-agent --web    # opens browser
# or
start https://github.com/Antonio-cccj/a-share-pairs-agent
```

The GitHub Actions CI badge in `README.md` should turn green within ~5 minutes.
