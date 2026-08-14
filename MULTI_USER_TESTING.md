# RI BUROM Multi-User Control Room Test

After installing dependencies and creating `.env`, start the app with `python app.py`.

## First Owner login

The first Owner is created automatically only when the database contains no users.
Use:

- `INITIAL_OWNER_USERNAME`
- `INITIAL_OWNER_NAME`
- `ADMIN_PASSWORD_HASH`

Then log in at `/admin/login`.

## Test roles

1. Create a **Content Manager** account.
2. Create an **Enquiries / Booking** account.
3. Log out of the Owner account.
4. Log in as Content Manager.

Content Manager should see and use:

- Tours
- Media
- About Us
- Team

It should receive **403 Access Denied** for user management and enquiry actions.

5. Log out and log in as Enquiries / Booking.

That account should see the enquiry inbox and be able to mark/delete messages, but should not be able to add/edit/delete tours, team members, About content, hero images, or users.

6. Log back in as Owner.

Owner should have access to all sections, including User Management and Recent Activity.

## Password tests

- Every user can change their own password under **My Account**.
- Owner can reset another user's password.
- A password shorter than 12 characters must be rejected.
- The last active Owner cannot be deactivated or demoted.
- A user cannot delete their own account.

## Audit log tests

Verify that Owner can see records for:

- login
- logout
- password change/reset
- user creation/update/deactivation
- tour creation/update/deletion
- team changes
- About changes
- hero image changes
- enquiry status/delete actions

## Production safety test

For deployment, use:

```text
APP_ENV=production
SECRET_KEY=<strong-secret>
ADMIN_PASSWORD_HASH=<generated-hash>
```

Do not deploy without `SECRET_KEY` and `ADMIN_PASSWORD_HASH`.

For a multi-worker Gunicorn deployment, configure a shared Redis backend for `RATELIMIT_STORAGE_URI`.

## Branding and content CMS tests

### Header and hero logos

1. Log in as Owner or Content Manager.
2. Open **Branding / Logo Display**.
3. Upload a wordmark image, a separate logo mark, and a separate hero logo.
4. Open the public site and confirm the header shows the wordmark first and logo mark second.
5. Move the four logo-size sliders and save.
6. Refresh the public site and confirm the display sizes changed without changing the uploaded files.
7. Test the reset button.

### About page

1. Edit the Nature, Culture and Community headings and text.
2. Add text to both extra About sections and leave both enabled.
3. Save and verify all content appears on `/about`.
4. Disable one extra section and verify only the enabled section remains publicly visible.
5. Add your logo explanation and designer credit.
6. Upload a real PDF and verify the public PDF link opens.
7. Remove the PDF and verify the link disappears.

### Blog

1. Add an external HTTPS blog URL.
2. Add a title, excerpt and optional image.
3. Enable the blog feature and homepage display.
4. Confirm the story appears on the homepage and the button opens the external URL in a new tab.
5. Disable homepage display and verify it disappears from the homepage.

### Footer and Instagram

1. Edit the footer contact information and copyright line.
2. Paste the Instagram URL and save.
3. Verify the direct Instagram button points to the supplied URL.
4. Verify a QR code is automatically generated and visible when QR display is enabled.
5. Disable QR display and verify it disappears without removing the Instagram link.
6. Clear the Instagram URL and save; confirm the Instagram button and QR code disappear.
