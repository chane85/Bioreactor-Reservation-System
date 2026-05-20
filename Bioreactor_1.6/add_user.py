"""
CLI for managing users in users.yaml.

Usage:
    python add_user.py add        # interactive: prompts for username, password, role
    python add_user.py update     # change a user's password
    python add_user.py remove     # delete a user
    python add_user.py list       # show all users and roles

Passwords are hashed with PBKDF2-SHA256 (200,000 iterations) — no external deps.
Never paste plaintext passwords into the YAML directly.
"""
import sys
import getpass
import os
import yaml

# Reuse hash_password from auth.py — same module, same algo guaranteed
from auth import hash_password

USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.yaml")
VALID_ROLES = ['viewer', 'editor', 'admin']


def load_config():
    with open(USERS_FILE) as f:
        return yaml.safe_load(f)

def _pbkdf2_representer(dumper, data):
    """Force double-quotes on PBKDF2 hash strings to prevent YAML scanner errors on '$'."""
    if data.startswith('pbkdf2_sha256$'):
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, _pbkdf2_representer)


def save_config(config):
    with open(USERS_FILE, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
def add_user():
    config = load_config()
    users = config['credentials']['usernames']

    username = input("Username: ").strip()
    if not username:
        print("❌ Username cannot be empty.")
        return
    if username in users:
        print(f"❌ User '{username}' already exists. Use 'update' to change password.")
        return

    first = input("First name: ").strip() or username
    last = input("Last name: ").strip() or ""
    email = input("Email: ").strip() or f"{username}@example.com"

    print(f"Roles available: {VALID_ROLES}")
    role = input("Role (viewer/editor/admin): ").strip().lower()
    if role not in VALID_ROLES:
        print(f"❌ Invalid role. Must be one of {VALID_ROLES}.")
        return

    pw1 = getpass.getpass("Password: ")
    pw2 = getpass.getpass("Confirm password: ")
    if pw1 != pw2:
        print("❌ Passwords do not match.")
        return
    if len(pw1) < 8:
        print("❌ Password must be at least 8 characters.")
        return

    users[username] = {
        'email': email,
        'first_name': first,
        'last_name': last,
        'password': hash_password(pw1),
        'roles': [role],
    }
    save_config(config)
    print(f"✅ User '{username}' added with role '{role}'.")


def update_user():
    config = load_config()
    users = config['credentials']['usernames']

    username = input("Username to update: ").strip()
    if username not in users:
        print(f"❌ User '{username}' not found.")
        return

    pw1 = getpass.getpass("New password: ")
    pw2 = getpass.getpass("Confirm new password: ")
    if pw1 != pw2:
        print("❌ Passwords do not match.")
        return
    if len(pw1) < 8:
        print("❌ Password must be at least 8 characters.")
        return

    users[username]['password'] = hash_password(pw1)
    save_config(config)
    print(f"✅ Password updated for '{username}'.")


def remove_user():
    config = load_config()
    users = config['credentials']['usernames']

    username = input("Username to remove: ").strip()
    if username not in users:
        print(f"❌ User '{username}' not found.")
        return
    confirm = input(f"Type '{username}' to confirm deletion: ").strip()
    if confirm != username:
        print("❌ Confirmation did not match. Aborted.")
        return
    del users[username]
    save_config(config)
    print(f"✅ User '{username}' removed.")


def list_users():
    config = load_config()
    users = config['credentials']['usernames']
    if not users:
        print("(no users)")
        return
    print(f"{'Username':<20} {'Roles':<25} {'Email'}")
    print("-" * 70)
    for u, info in users.items():
        roles = ', '.join(info.get('roles', []))
        print(f"{u:<20} {roles:<25} {info.get('email','')}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1].lower()
    if cmd == 'add':
        add_user()
    elif cmd == 'update':
        update_user()
    elif cmd == 'remove':
        remove_user()
    elif cmd == 'list':
        list_users()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == '__main__':
    main()