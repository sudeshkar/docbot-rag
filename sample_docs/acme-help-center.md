# Acme Cloud Help Center

Acme Cloud is a file storage and sharing service for small teams.

## Billing

### Plans and pricing

Acme Cloud has three plans. The Free plan includes 5 GB of storage for one user. The Team plan costs $8 per user per month and includes 1 TB of shared storage. The Business plan costs $15 per user per month and adds unlimited storage, SSO, and audit logs.

Annual billing saves 20% compared to monthly billing on the Team and Business plans.

### Refunds

You can request a full refund within 30 days of your first payment. Refunds are issued to the original payment method and usually appear within 5 to 7 business days. Refunds are not available for renewals after the first 30 days, but you can cancel at any time to stop future charges.

To request a refund, go to Settings > Billing > Request refund, or email billing@acme.example.

### Invoices

Invoices are generated on the first day of each billing cycle and emailed to the account owner. You can download past invoices as PDF from Settings > Billing > Invoices. To add a VAT number or company address, edit your billing profile before the next invoice is generated; existing invoices cannot be changed.

## Account and security

### Resetting your password

Click "Forgot password" on the sign-in page and enter your email address. The reset link is valid for 1 hour. If you don't receive the email within 5 minutes, check your spam folder or contact support.

### Two-factor authentication

Two-factor authentication (2FA) can be enabled in Settings > Security. Acme Cloud supports authenticator apps and hardware security keys (WebAuthn). SMS codes are not supported. Workspace admins on the Business plan can require 2FA for all members.

### Single sign-on

SSO with SAML 2.0 is available on the Business plan. Supported identity providers include Okta, Microsoft Entra ID, and Google Workspace. SCIM provisioning is supported for Okta and Entra ID.

## Files and sharing

### Upload limits

The maximum size for a single file is 5 GB on the Free plan and 50 GB on paid plans. Uploads larger than 100 MB are split into parts automatically and can resume if your connection drops.

### Sharing links

Any file or folder can be shared with a link. Links can be set to view-only or edit, protected with a password, and given an expiry date. Business plan admins can disable public links for the whole workspace.

### Deleted files and version history

Deleted files stay in the Trash for 30 days on the Free plan and 180 days on paid plans, after which they are permanently removed. Version history keeps the last 100 versions of each file on paid plans; the Free plan keeps 10 versions.

## Troubleshooting

### Sync is stuck

If the desktop app shows "Sync paused" or files are not updating, first check that you are signed in and have free storage left. Then quit and reopen the app. If the problem continues, go to Preferences > Advanced > Rebuild index. Error code E-401 means your session expired and you need to sign in again. Error code E-507 means your storage quota is full.

### Contacting support

Free plan users can get help through the community forum. Team and Business customers can email support@acme.example and get a reply within 24 hours on weekdays. Business customers also have live chat from 9am to 6pm Eastern Time.
