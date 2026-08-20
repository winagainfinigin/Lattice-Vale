# LatticeVale v14.3.37 — Controlled Update / Repair

This release makes update behavior explicit and separates three operations that older documentation could blur together.

## Resume / repair

Resume / repair remains preservation-first and local-first between refresh windows. It **may update installer-managed software** when the normal managed-refresh interval is due, when an older install has no refresh marker, or when LatticeVale changes the managed-refresh policy revision. It does not broadly upgrade unrelated Ubuntu packages.

## Update / repair installer-managed software

A new existing-stack installer choice forces the current bundle's managed software refresh immediately. The mode:

- reuses saved component/profile choices;
- requires a successful `manage.sh backup` before refresh;
- bypasses the periodic age gate for that run;
- refreshes targeted Ubuntu prerequisites and the managed Docker package set;
- reconciles/pulls the component references declared by the bundle;
- rebuilds QMD and Honcho when selected;
- advances the audited Honcho source only when the checkout is proven installer-owned;
- preserves explicit custom image/source overrides where ownership is not proven;
- preserves application databases, identities, profiles, credentials, model data, vault/workspace files, and normal persistent state;
- does not install or update separately owned native Windows Ollama;
- finishes by running the normal staged repair/live verification path.

If the update is interrupted after the refresh marker is created, a later Resume / repair continues the pending managed refresh.

## What “update” means

The controlled updater aligns an installation with **this LatticeVale bundle's declared references**, not arbitrary internet `latest` versions. A newer fixed Hermes or Synapse tag is adopted when a newer LatticeVale bundle declares it. Floating major/channel references may resolve to a newer digest within the configured reference when pulled.

`./manage.sh update` remains available as a separate advanced upstream-refresh workflow. It pulls the current configured references and may advance Honcho to repository `HEAD`; it should not be confused with the reproducible Windows installer update mode.

## v14.3.38 integration-policy migration

The controlled software updater remains a v14.3.37 feature, but v14.3.38 also advances the **integrations checkpoint revision**. Therefore the Kanban/skill policy update does **not** require choosing the forced software updater: a normal mutating Resume / repair will re-run the integrations stage once after adopting v14.3.38. Change components, Reconfigure, Advanced recovery, and Update / repair also receive the same current policy. Fresh installs receive it during their first integrations stage. The migration preserves explicit skill-write approval and does not rewrite user-owned profile configs.
