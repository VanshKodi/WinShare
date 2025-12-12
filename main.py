import os
import sys
import json
import time
import string
import random
import shutil
import shlex
import ctypes
import subprocess
from InquirerPy import inquirer
from InquirerPy.separator import Separator

POWER_SHELL = shutil.which("pwsh") or shutil.which("powershell.exe") or shutil.which("powershell")

defaults_file = "defaults.json"
defaults = {
    "access": "FullAccess",
    "access_to": "Everyone",
    "UserName": "shareuser",
    "Password": "ChangeMe123!",
    "share_path": r"C:\Shared"
}

created_shares = {}

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def load_defaults():
    try:
        with open(defaults_file, "r") as f:
            data = json.load(f)
        if isinstance(data, dict) and "defaults" in data and isinstance(data["defaults"], dict):
            return data["defaults"]
    except Exception:
        pass
    return defaults.copy()

def save_defaults():
    try:
        with open(defaults_file, "w") as f:
            json.dump({"defaults": defaults}, f, indent=2)
        print("Defaults saved")
    except Exception as e:
        print("Failed to save defaults:", e)
    input("Press Enter to continue...")

def ask_path(prompt, default_val):
    print(f"{prompt} [{default_val}]")
    entered = input("> ").strip()
    return entered if entered else default_val

def is_admin():
    if sys.platform != "win32":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False

def ensure_admin():
    if sys.platform != "win32":
        print("This script is for Windows only.")
        sys.exit(1)
    if is_admin():
        return
    params = os.path.abspath(sys.argv[0])
    if len(sys.argv) > 1:
        params += " " + shlex.join(sys.argv[1:])
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    if int(ret) <= 32:
        print("Elevation failed or cancelled.")
        input("Press Enter to exit...")
        sys.exit(1)
    sys.exit(0)

def run_ps(cmd):
    if not POWER_SHELL:
        raise FileNotFoundError("PowerShell not found")
    args = [POWER_SHELL, "-NoProfile", "-NonInteractive", "-Command", cmd]
    return subprocess.run(args, capture_output=True, text=True)

def print_ps_result(res):
    print("Return code:", res.returncode)
    if res.stdout:
        print(res.stdout)
    if res.stderr:
        print("Errors:", res.stderr)

def generate_random_credentials(prefix="tmpuser", length=6):
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=length))
    username = f"{prefix}_{suffix}"
    password = "".join(random.choices(string.ascii_letters + string.digits + "!@#$%^&*-", k=12))
    return username, password

def user_exists(username):
    p = subprocess.run(["net", "user", username], capture_output=True, text=True)
    return p.returncode == 0

def create_local_user(username, password, disable_interactive=True):
    if user_exists(username):
        return True
    p = subprocess.run(["net", "user", username, password, "/add"], capture_output=True, text=True)
    if p.returncode != 0:
        return False
    if disable_interactive:
        subprocess.run(["net", "user", username, "/active:no"], capture_output=True, text=True)
    return True

def delete_local_user(username):
    if not user_exists(username):
        return True
    p = subprocess.run(["net", "user", username, "/delete"], capture_output=True, text=True)
    return p.returncode == 0

def get_shares():
    cmd = "Get-SmbShare | Select-Object Name,Path,Description | ConvertTo-Json -Compress"
    try:
        res = run_ps(cmd)
        if res.returncode != 0 or not res.stdout:
            return []
        data = res.stdout.strip()
        if not data:
            return []
        parsed = json.loads(data)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    except Exception:
        return []
    return []

def derive_share_name_from_path(path):
    if not path:
        return None
    p = path.rstrip("\\/")
    name = os.path.basename(p)
    if not name:
        name = "Share"
    return name

def create_share(name, path, grantee, access):
    safe_name = name.replace("'", "''")
    safe_path = path.replace("'", "''")
    if access.lower().startswith("f"):
        cmd = f"New-SmbShare -Name '{safe_name}' -Path '{safe_path}' -FullAccess '{grantee}'"
    else:
        cmd = f"New-SmbShare -Name '{safe_name}' -Path '{safe_path}' -ReadAccess '{grantee}'"
    return run_ps(cmd)

def revoke_everyone_if_exists(name):
    try:
        run_ps(f"Revoke-SmbShareAccess -Name '{name}' -AccountName 'Everyone' -Force")
    except Exception:
        pass

def default_share_flow():
    path =inquirer.text(message="Enter path of folder:").execute().strip()
    if not os.path.isdir(path):
        print("Path does not exist:", path)
        input("Press Enter to continue...")
        return
    name = derive_share_name_from_path(path)
    access = defaults.get("access")
    access_to = defaults.get("access_to")
    created_user = None
    if access_to == "default":
        uname = defaults.get("UserName")
        pwd = defaults.get("Password")
        ok = create_local_user(uname, pwd)
        if not ok:
            print("Failed to create/use default user:", uname)
            input("Press Enter to continue...")
            return
        grantee = uname
        created_user = None
    elif access_to == "ask_everytime":
        uname, pwd = generate_random_credentials("share")
        ok = create_local_user(uname, pwd)
        if not ok:
            print("Failed to create temporary user")
            input("Press Enter to continue...")
            return
        grantee = uname
        created_user = uname
    else:
        grantee = access_to
    res = create_share(name, path, grantee, access)
    print_ps_result(res)
    if created_user:
        created_shares[name] = created_user
    else:
        created_shares[name] = None
    input("Press Enter to continue...")

def custom_share_flow():
    path = inquirer.text(
    message=f"Path [{defaults['share_path']}]:",
    default=defaults["share_path"],
    multiline=False,
    validate=lambda text: len(text.strip()) > 0
    ).execute().strip()
    
    if not os.path.isdir(path):
        print("Path does not exist:", path)
        input("Press Enter to continue...")
        return
    name = derive_share_name_from_path(path)
    access = inquirer.select(message="Access:", choices=["FullAccess", "Read"], default=defaults["access"]).execute()
    access_to = inquirer.select(message="Grant to:", choices=["Everyone", "default", "ask_everytime", "Specific user"], default=defaults["access_to"]).execute()
    grantee = None
    created_user = None
    if access_to == "default":
        uname = defaults.get("UserName")
        pwd = defaults.get("Password")
        ok = create_local_user(uname, pwd)
        if not ok:
            print("Failed to create/use default user:", uname)
            input("Press Enter to continue...")
            return
        grantee = uname
    elif access_to == "ask_everytime":
        uname, pwd = generate_random_credentials("share")
        ok = create_local_user(uname, pwd)
        if not ok:
            print("Failed to create temporary user")
            input("Press Enter to continue...")
            return
        grantee = uname
        created_user = uname
    elif access_to == "Specific user":
        grantee = inquirer.text(message="Enter account (e.g. MYPC\\User or User):").execute().strip()
        if not grantee:
            print("No grantee provided")
            input("Press Enter to continue...")
            return
    else:
        grantee = access_to
    res = create_share(name, path, grantee, access)
    print_ps_result(res)
    created_shares[name] = created_user
    input("Press Enter to continue...")

def remove_share_flow():
    shares = get_shares()
    if not shares:
        print("No SMB shares found")
        input("Press Enter to continue...")
        return
    choices = []
    for s in shares:
        nm = s.get("Name")
        pt = s.get("Path", "")
        choices.append(f"{nm}    ->    {pt}")
    choice = inquirer.select(message="Select share to remove:", choices=choices).execute()
    sel_name = choice.split()[0]
    confirm = inquirer.confirm(message=f"Remove share '{sel_name}'?", default=False).execute()
    if not confirm:
        return
    res = run_ps(f"Remove-SmbShare -Name '{sel_name}' -Force")
    print_ps_result(res)
    temp_user = created_shares.pop(sel_name, None)
    if temp_user:
        ok = delete_local_user(temp_user)
        if ok:
            print("Deleted temporary user", temp_user)
        else:
            print("Failed to delete temporary user", temp_user)
    input("Press Enter to continue...")

def list_shares_flow():
    shares = get_shares()
    if not shares:
        print("No SMB shares found")
    else:
        for s in shares:
            print(f"{s.get('Name')}  ->  {s.get('Path')}")
    input("Press Enter to continue...")

def change_defaults_flow():
    # Access (FullAccess or ReadAccess)
    access_choice = inquirer.select(
        message="Select access level:",
        choices=["FullAccess", "ReadAccess"],
        default=defaults.get("access", "FullAccess")
    ).execute()
    defaults["access"] = access_choice

    # access_to choices
    access_to_choice = inquirer.select(
        message="Select who to grant share access to:",
        choices=["Everyone", "default", "ask_everytime"],
        default=defaults.get("access_to", "Everyone")
    ).execute()
    defaults["access_to"] = access_to_choice

    # If access_to == default, ensure username/password are set (prompt if empty)
    if access_to_choice == "default":
        uname = defaults.get("UserName") or ""
        pwd = defaults.get("Password") or ""
        if not uname:
            uname = inquirer.text(message="Default share username:").execute().strip()
        else:
            uname = inquirer.text(message=f"Default share username [{uname}]:", default=uname).execute().strip() or uname
        # password: use secret prompt
        if not pwd:
            pwd = inquirer.secret(message="Default share password:").execute().strip()
        else:
            # let user re-enter or keep existing
            newpwd = inquirer.secret(message="Default share password (leave blank to keep):").execute().strip()
            if newpwd:
                pwd = newpwd
        defaults["UserName"] = uname
        defaults["Password"] = pwd

    # Ask for share_path using reliable ask_path helper (works with Windows paste)
    defaults["share_path"] = ask_path("Default share path", defaults.get("share_path", r"C:\Shared"))

    save_defaults()
    input("Defaults updated. Press Enter to continue...")

def share_menu():
    while True:
        clear_screen()
        header = Separator(f"Share menu — defaults: access={defaults['access']} | access_to={defaults['access_to']}")
        choice = inquirer.select(message="Choose:", choices=[header, "Use default settings", "Use custom settings", "Back"], default=None).execute()
        if choice is None or choice == "Back":
            clear_screen()
            return
        try:
            if choice == "Use default settings":
                default_share_flow()
            elif choice == "Use custom settings":
                custom_share_flow()
        except Exception as e:
            print("Error:", e)
            input("Press Enter to continue...")

def main_menu():
    while True:
        clear_screen()
        header = f"Defaults → access: {defaults['access']} | access_to: {defaults['access_to']}\n"
        choice = inquirer.select(message=header + "Main menu:", choices=["Share new folder", "Remove share", "List shares", "Change defaults", "Exit"], default=None).execute()
        if choice is None or choice == "Exit":
            break
        if choice == "Share new folder":
            share_menu()
        elif choice == "Remove share":
            remove_share_flow()
        elif choice == "List shares":
            list_shares_flow()
        elif choice == "Change defaults":
            change_defaults_flow()

if __name__ == "__main__":
    try:
        ensure_admin()
        loaded = load_defaults()
        defaults.update(loaded)
        main_menu()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print("Fatal error:", e)
        input("Press Enter to exit...")
