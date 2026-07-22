# Crypto custody basics

> Informal summary for demo purposes only. Not legal, security or investment
> advice.

## What custody means

Custody of crypto-assets is control over the private keys that authorise
transfers. Whoever holds the keys effectively controls the assets, so custody
design is first and foremost key-management design, wrapped in operational
and legal controls.

## Wallet tiers

- **Cold storage**: private keys generated and kept on devices that never
  touch the internet (hardware security modules, air-gapped signers, paper or
  metal backups in vaults). Used for the bulk of client assets; withdrawals
  are slow by design and require manual ceremonies.
- **Warm wallets**: keys online but behind strong controls and limited
  balances; used to buffer between cold storage and daily operations.
- **Hot wallets**: keys available to automated systems to serve real-time
  withdrawals. Balances are deliberately kept to a small fraction of total
  assets, continuously topped up from colder tiers.

## Key-management techniques

- **Multisignature (multisig)**: on-chain scheme requiring M-of-N keys to
  sign; compromise of a single key is not sufficient to move funds.
- **MPC / threshold signatures**: the key never exists in one place; parties
  jointly compute a signature from key shares. Popular with institutional
  custodians because it is chain-agnostic and produces standard signatures.
- **HSMs**: dedicated tamper-resistant hardware that stores keys and enforces
  signing policy; often combined with MPC or multisig.
- **Backups and recovery**: geographically distributed, access-controlled
  backups of key material or key shares; documented, rehearsed recovery
  ceremonies.

## Operational controls

- Segregation of duties and four-eyes (or more) approval for withdrawals
  above thresholds.
- Withdrawal allowlists, velocity limits and delayed large withdrawals.
- Address-generation and deposit-attribution controls to keep client balances
  accurate.
- Monitoring and alerting on wallet balances and unusual outflows.
- Regular penetration testing and third-party security audits.

## Client-asset protection

- **Segregation**: client assets held separately from the firm's own assets,
  in clearly designated wallets, so that client property is identifiable in
  insolvency. Regulatory regimes (e.g. MiCA for EU CASPs) make segregation
  and custody-policy disclosure mandatory.
- **Proof of reserves**: periodic cryptographic attestations (e.g.
  Merkle-tree inclusion proofs plus on-chain reserve addresses) that the
  custodian holds assets covering client liabilities. A useful transparency
  tool, though it shows a snapshot and does not by itself prove absence of
  hidden liabilities.
- **Insurance**: crime/specie policies covering theft of keys from covered
  storage tiers; coverage limits and exclusions matter more than headline
  numbers.

## Risk themes for portfolio holders

Concentrating a large share of holdings with a single custodian, in a single
wallet tier, or in a single asset increases operational and counterparty
risk. Standard mitigations include distributing assets across custody
arrangements, keeping long-term holdings in cold storage, and reviewing the
custodian's segregation, audit and insurance disclosures.
