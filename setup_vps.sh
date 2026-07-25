#!/bin/bash
# ==============================================================================
# Box-4 Backend Initial VPS Provisioning Script (Ubuntu / Debian)
# ==============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}==============================================================================${NC}"
echo -e "${YELLOW} Provisioning VPS Server for Box-4 Backend ${NC}"
echo -e "${YELLOW}==============================================================================${NC}"

# 1. Update system packages
echo -e "${GREEN}--> Updating system packages...${NC}"
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install essential dependencies
echo -e "${GREEN}--> Installing core utilities (curl, git, ufw, certbot)...${NC}"
sudo apt-get install -y \
    curl \
    wget \
    git \
    ufw \
    certbot \
    python3-certbot-nginx \
    ca-certificates \
    gnupg \
    lsb-release

# 3. Install Docker and Docker Compose plugin
if ! command -v docker &> /dev/null; then
    echo -e "${GREEN}--> Installing Docker Engine & Docker Compose plugin...${NC}"
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    sudo usermod -aG docker $USER
    echo -e "${GREEN}--> Docker installed successfully.${NC}"
else
    echo -e "${GREEN}--> Docker is already installed.${NC}"
fi

# 4. Configure Firewall (SSH, HTTP, HTTPS)
echo -e "${GREEN}--> Configuring UFW firewall rules...${NC}"
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# Make scripts executable
chmod +x deploy.sh entrypoint.sh 2>/dev/null || true

echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN} VPS provisioning complete! ${NC}"
echo -e "${GREEN} Log out and log back in for Docker group permissions to apply. ${NC}"
echo -e "${GREEN}==============================================================================${NC}"
