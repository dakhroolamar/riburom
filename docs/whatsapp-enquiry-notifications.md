# RI BUROM WhatsApp Enquiry Notifications

This integration sends a WhatsApp alert to the RI BUROM Operations recipient when a public enquiry is successfully persisted.

## Production architecture

1. Visitor submits the public enquiry form.
2. RI BUROM stores the enquiry first.
3. The visitor receives the in-page confirmation.
4. The notification worker sends an email and/or WhatsApp alert without blocking the visitor.
5. Staff open the Operations Workspace for the full enquiry.

The WhatsApp path uses a Twilio WhatsApp sender and an approved WhatsApp Content Template. This is the production-safe path for business-initiated notifications outside an active WhatsApp customer-service window.

## Twilio setup

1. Create or use a Twilio account.
2. Register a WhatsApp sender through Twilio's WhatsApp Self Sign-up flow.
3. Connect the sender to the organisation's Meta Business Portfolio / WhatsApp Business Account.
4. In Twilio Console, open Content Template Builder.
5. Create a template named something like `ri_burom_new_enquiry`.
6. Submit it for WhatsApp approval as a Utility template if Twilio/Meta's classification is appropriate for the user-initiated enquiry notification.
7. After approval, copy the template Content SID beginning with `HX`.

### Suggested template

**Name:** `ri_burom_new_enquiry`

**Language:** English

**Category:** Utility

**Body:**

> New RI BUROM enquiry received from {{1}}. Experience: {{2}}. Travel dates: {{3}}. Travellers: {{4}}. Contact: {{5}}. Message: {{6}}. Please review the full enquiry in the RI BUROM Operations Workspace.

Use representative sample values when submitting the template for approval.

## Render environment variables

Add these to the RI BUROM production service in Render. Never commit the credentials to GitHub.

```text
NOTIFICATION_PHONE=+91XXXXXXXXXX
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_WHATSAPP_FROM=whatsapp:+91XXXXXXXXXX
TWILIO_WHATSAPP_CONTENT_SID=HXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

`NOTIFICATION_PHONE` is the staff recipient. It should be in E.164 format. `TWILIO_WHATSAPP_FROM` is the registered WhatsApp sender.

## Testing

Use the Twilio Sandbox only for initial development/testing if a production sender is not ready. For production, use the registered WhatsApp sender and approved template.

Submit one harmless test enquiry on the live RI BUROM website and verify:

- the public confirmation appears;
- the enquiry appears in Operations;
- the WhatsApp notification arrives;
- the notification contains the visitor name, experience, dates, traveller count, phone and message;
- the full enquiry remains available in Operations.

## Security

Do not put `TWILIO_AUTH_TOKEN` in source code, `.env.example`, GitHub commits, screenshots, or chat. Store it only in Render environment variables or another secret manager.
