"""Generate a password hash for the RI BUROM initial Owner or password reset workflow."""
import getpass
from werkzeug.security import generate_password_hash

password = getpass.getpass('Password: ')
confirm = getpass.getpass('Confirm password: ')
if not password or password != confirm:
    raise SystemExit('Passwords are empty or do not match.')
if len(password) < 12:
    raise SystemExit('Password must be at least 12 characters long.')
print('\nADMIN_PASSWORD_HASH=' + generate_password_hash(password))
