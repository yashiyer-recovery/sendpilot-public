# FIX THIS BEFORE SCALING SENDS — SPF/DMARC

The 2026-07-02 deliverability check found placement seeds from **all three inboxes
landing in spam**, and SPF failing everywhere. DKIM passes. A booking pipeline
that lands in spam books zero meetings — this is the highest-leverage 15 minutes
in this whole system.

Add these TXT records at each domain's DNS host:

## zorbe.ai  (the workhorse — do this one first)
| Host | Type | Value |
|------|------|-------|
| `@` | TXT | `v=spf1 include:_spf.google.com ~all` |
| `_dmarc` | TXT | `v=DMARC1; p=none; rua=mailto:yash@zorbe.ai; fo=1` |

## zorbeai.com
Existing SPF omits Google — **replace** the current SPF record (don't add a second
one; two SPF records = permanent fail) so it includes `include:_spf.google.com`:
| Host | Type | Value |
|------|------|-------|
| `@` | TXT | `v=spf1 include:_spf.google.com ~all` (merge any existing includes into this one record) |
| `_dmarc` | TXT | `v=DMARC1; p=none; rua=mailto:yash@zorbeai.com; fo=1` |

## tryzorbe.com
| Host | Type | Value |
|------|------|-------|
| `@` | TXT | `v=spf1 include:_spf.google.com ~all` |
| `_dmarc` | TXT | `v=DMARC1; p=none; rua=mailto:yash@tryzorbe.com; fo=1` |

## Verify (an hour after adding; propagation can take up to 24-48h)
```bash
dig +short TXT zorbe.ai | grep spf1
dig +short TXT _dmarc.zorbe.ai
dig +short TXT zorbeai.com | grep spf1
dig +short TXT tryzorbe.com | grep spf1
```
Then send a seed to a fresh Gmail you own and check "Show original" — SPF, DKIM,
and DMARC should all read PASS.

After ~2 weeks of clean DMARC reports, tighten `p=none` → `p=quarantine`.
