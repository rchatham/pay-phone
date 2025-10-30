# Secrets Management with 1Password

Complete guide for managing credentials and secrets using 1Password CLI.

## Overview

The payphone project uses **1Password CLI** on your local development machine to securely manage:
- Raspberry Pi SSH credentials
- API keys (OpenAI, Twilio, Weather, etc.)
- Configuration secrets

**Key principle**: Secrets are stored in 1Password on your local machine and injected to the Pi during deployment. The Raspberry Pi does NOT have 1Password CLI installed.

## Prerequisites

### 1. Install 1Password CLI

**Mac:**
```bash
brew install --cask 1password-cli
```

**Linux:**
```bash
curl -sS https://downloads.1password.com/linux/keys/1password.asc | \
  sudo gpg --dearmor --output /usr/share/keyrings/1password-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/1password-archive-keyring.gpg] https://downloads.1password.com/linux/debian/$(dpkg --print-architecture) stable main" | \
  sudo tee /etc/apt/sources.list.d/1password.list

sudo apt update && sudo apt install 1password-cli
```

**Verify installation:**
```bash
op --version
```

### 2. Sign in to 1Password

```bash
eval $(op signin)
```

You'll be prompted for your 1Password account details.

## Setup 1Password Items

### Create Raspberry Pi Credentials

1. **Open 1Password app**
2. **Create new item**:
   - **Vault**: Personal (or your preferred vault)
   - **Type**: Login or Server
   - **Title**: `Payphone-Pi`
   - **Fields**:
     - `username`: pi (or your custom username)
     - `password`: your Raspberry Pi password
     - `host`: payphone.local (or IP address)
     - `port`: 22

3. **Optional: SSH Key**:
   - Add a field: `ssh_private_key` (file attachment or text)
   - Upload your private SSH key

### Create API Keys Item (Optional)

If you plan to use cloud APIs:

1. **Create new item**:
   - **Vault**: Personal
   - **Type**: API Credential or Password
   - **Title**: `Payphone-APIs`

2. **Add sections and fields**:
   - Section: `OpenAI`
     - `api_key`: your OpenAI API key
   - Section: `Twilio`
     - `account_sid`: your Twilio account SID
     - `auth_token`: your Twilio auth token
     - `phone_number`: your Twilio phone number
   - Section: `Weather`
     - `api_key`: your weather API key

## Using Secrets in Your Workflow

### Load Secrets from 1Password

Before deploying or accessing the Pi, load secrets:

```bash
# From project root
source scripts/load_secrets.sh
```

This exports environment variables:
- `PI_HOST`
- `PI_USER`
- `PI_PASSWORD`
- `PI_SSH_KEY_PATH` (if applicable)
- `OPENAI_API_KEY` (if configured)
- `TWILIO_ACCOUNT_SID` (if configured)
- etc.

### Deploy with Secrets

```bash
# Load secrets
source scripts/load_secrets.sh

# Deploy code + inject secrets
make deploy

# Or use direct script
./scripts/deploy_to_pi.sh
```

### Sync Only Secrets (No Code)

Update secrets on Pi without deploying code:

```bash
source scripts/load_secrets.sh
make sync-secrets

# Or with service restart
./scripts/sync_config.sh --restart
```

### SSH to Pi

```bash
source scripts/load_secrets.sh
make ssh

# Or direct
./scripts/ssh_to_pi.sh
```

## 1Password References

### Reference Format

References use the format: `op://vault/item/field`

**Examples:**
```bash
# Raspberry Pi password
op://Personal/Payphone-Pi/password

# OpenAI API key
op://Personal/Payphone-APIs/OpenAI/api_key

# SSH key
op://Personal/Payphone-Pi/ssh_private_key
```

### Customizing References

Edit `scripts/load_secrets.sh` to match your 1Password structure:

```bash
# Example: Different vault or item name
export PI_HOST=$(op read "op://Work/RaspberryPi/host" 2>/dev/null || echo "raspberrypi.local")
export PI_USER=$(op read "op://Work/RaspberryPi/username" 2>/dev/null || echo "pi")
```

## Security Best Practices

### 1. Never Commit Secrets

The `.gitignore` file is configured to exclude:
- `.env` files
- SSH keys (`*.pem`, `*.key`, `id_rsa*`)
- Temporary key files

**Always verify before committing:**
```bash
git status
git diff
```

### 2. Use Session Tokens

1Password sessions expire for security. Refresh when needed:

```bash
eval $(op signin)
```

### 3. Limit Secret Scope

Only load secrets when needed:
```bash
# Bad - secrets in shell history
export API_KEY="sk-..."

# Good - load from 1Password when needed
source scripts/load_secrets.sh
```

### 4. Rotate Credentials Regularly

Update in 1Password, then sync:
```bash
# Update in 1Password app
# Then sync to Pi
source scripts/load_secrets.sh
make sync-secrets
```

### 5. Use SSH Keys Over Passwords

**Generate SSH key:**
```bash
ssh-keygen -t ed25519 -C "payphone-pi" -f ~/.ssh/id_ed25519_payphone
```

**Add to Pi:**
```bash
ssh-copy-id -i ~/.ssh/id_ed25519_payphone.pub pi@payphone.local
```

**Store in 1Password:**
- Copy private key content
- Add to `Payphone-Pi` item as `ssh_private_key` field

**Update load_secrets.sh:**
```bash
export PI_SSH_KEY_PATH=~/.ssh/id_ed25519_payphone
```

## Troubleshooting

### "op: command not found"

Install 1Password CLI (see Prerequisites above).

### "Not signed in to 1Password"

```bash
eval $(op signin)
```

### "Item not found"

Check item exists in 1Password:
```bash
op item list | grep Payphone
```

Verify reference path:
```bash
op read "op://Personal/Payphone-Pi/username"
```

### Scripts Can't Find Secrets

Ensure you've sourced (not executed) load_secrets.sh:
```bash
# Correct (exports to current shell)
source scripts/load_secrets.sh

# Wrong (exports to subshell only)
./scripts/load_secrets.sh
```

### SSH Key Not Working

Check key permissions:
```bash
chmod 600 /tmp/payphone_ssh_key
```

Verify key is loaded:
```bash
ls -la $PI_SSH_KEY_PATH
```

### Secrets Not Syncing to Pi

Test connection first:
```bash
source scripts/load_secrets.sh
./scripts/ssh_to_pi.sh "echo 'Connected'"
```

Check /etc/payphone/.env on Pi:
```bash
./scripts/ssh_to_pi.sh "cat /etc/payphone/.env"
```

## Workflow Examples

### Daily Development

```bash
# Morning: Load secrets once
source scripts/load_secrets.sh

# Make code changes...

# Deploy
make deploy

# Check status
make pi-status

# View logs
make pi-logs
```

### Adding New API Key

1. **Add to 1Password**:
   - Open `Payphone-APIs` item
   - Add new section/field

2. **Update load_secrets.sh**:
   ```bash
   export NEW_API_KEY=$(op read "op://Personal/Payphone-APIs/NewService/api_key" 2>/dev/null || echo "")
   ```

3. **Update inject_secrets.sh**:
   ```bash
   if [ -n "$NEW_API_KEY" ]; then
       ENV_CONTENT+=$'\n\nNEW_API_KEY='"$NEW_API_KEY"
   fi
   ```

4. **Sync to Pi**:
   ```bash
   source scripts/load_secrets.sh
   make sync-secrets
   ```

### Team Collaboration

Each team member:
1. Has their own 1Password account
2. Creates their own `Payphone-Pi` item with their Pi credentials
3. Loads secrets individually: `source scripts/load_secrets.sh`
4. Deploys to their own Pi or shared test Pi

## Alternative: Manual .env File

If you prefer not to use 1Password:

1. **Create .env file locally**:
   ```bash
   cp .env.template .env
   nano .env  # Fill in values
   ```

2. **Never commit .env**:
   ```bash
   # Already in .gitignore
   git status  # Verify .env not listed
   ```

3. **Manually copy to Pi**:
   ```bash
   scp .env pi@payphone.local:/etc/payphone/.env
   ```

**Note**: This is less secure - secrets are stored in plaintext on disk.

---

**Next:** See [DEVELOPMENT.md](DEVELOPMENT.md) for development workflow and [WALKTHROUGH.md](WALKTHROUGH.md) for a complete tutorial.
