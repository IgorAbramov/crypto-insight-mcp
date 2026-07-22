# AML / KYC basics for crypto businesses

> Informal summary for demo purposes only. Not legal advice or a compliance
> manual. Regulatory expectations differ by jurisdiction and change often.

## The core idea

Anti-money-laundering (AML) rules require regulated businesses to know who
their customers are, understand the purpose of the relationship, monitor
activity for suspicious patterns, and report suspicions to the financial
intelligence unit. Crypto exchanges and custodial wallet providers are within
scope of AML regimes in most developed jurisdictions (in the EU via the
anti-money-laundering directives and their successors; globally the FATF
recommendations set the baseline).

## KYC — Know Your Customer

- **Identification and verification (CDD)**: collect name, date of birth,
  address and an identity document; verify authenticity (document checks,
  liveness/selfie matching, database checks).
- **Tiered onboarding**: many firms apply limits by verification level — e.g.
  small deposit/withdrawal limits at basic verification, higher limits after
  enhanced checks such as proof of address or source-of-funds documentation.
- **Enhanced due diligence (EDD)**: required for higher-risk customers —
  politically exposed persons (PEPs), customers from high-risk jurisdictions,
  unusually large or complex activity. Typically includes source-of-wealth
  checks and senior-management approval.
- **Ongoing due diligence**: customer data must be kept current; risk scores
  reviewed periodically, not only at onboarding.

## Screening and monitoring

- **Sanctions screening**: customers and counterparty wallet addresses are
  screened against sanctions lists (e.g. UN, EU, OFAC) at onboarding and
  continuously thereafter.
- **Transaction monitoring**: rule-based and behavioural monitoring for
  structuring, rapid pass-through flows, mixing-service exposure, darknet
  market exposure and other red flags. Blockchain-analytics tools score the
  risk of counterparty addresses.
- **Suspicious activity reporting**: when monitoring or manual review raises
  suspicion, the firm files a report (SAR/STR) with the competent authority
  and must avoid tipping off the customer.

## The Travel Rule

FATF Recommendation 16 (the "Travel Rule") requires virtual-asset service
providers to transmit originator and beneficiary information alongside
transfers above the applicable threshold, including transfers between VASPs.
In the EU this is implemented via the Transfer of Funds Regulation applying to
crypto-asset transfers. Practical impact: exchanges must exchange customer
data with counterparty VASPs through dedicated messaging protocols and treat
transfers to/from self-hosted wallets with additional checks.

## Record keeping and governance

AML programmes require a designated compliance officer (MLRO), documented
risk assessment of the business, staff training, independent audit of the
programme, and retention of KYC and transaction records for the legally
mandated period (commonly five years or more).
