#!/bin/bash
# ==============================================================================
# Box-4 Backend SSL Renewal & Auto-Renewal Setup Script (Let's Encrypt)
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

DOMAIN="box4realestate.cloud"
WWW_DOMAIN="www.box4realestate.cloud"
WEBROOT="/var/www/certbot"
NGINX_CONTAINER="realestate_prod_nginx"
HOOK_PATH="/etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh"

echo -e "${YELLOW}==============================================================================${NC}"
echo -e "${YELLOW} Renewing Let's Encrypt SSL & Configuring Zero-Downtime Auto-Renewal ${NC}"
echo -e "${YELLOW}==============================================================================${NC}"

# 1. Ensure webroot directory exists for ACME HTTP-01 challenges
echo -e "${GREEN}--> Creating ACME webroot directory at ${WEBROOT}...${NC}"
sudo mkdir -p "${WEBROOT}"

# 2. Install Certbot deploy hook so Docker Nginx reloads automatically after any renewal
echo -e "${GREEN}--> Installing Certbot deploy hook at ${HOOK_PATH}...${NC}"
sudo mkdir -p /etc/letsencrypt/renewal-hooks/deploy
sudo tee "${HOOK_PATH}" > /dev/null <<EOF
#!/bin/bash
if docker ps --format '{{.Names}}' | grep -q "^${NGINX_CONTAINER}\$"; then
    docker exec ${NGINX_CONTAINER} nginx -s reload
fi
EOF
sudo chmod +x "${HOOK_PATH}"

# 3. Determine docker compose command
DOCKER_COMPOSE_CMD="docker compose"
if ! docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
fi

ENV_FILE=".env.prod"
if [ ! -f ".env.prod" ] && [ -f ".env" ]; then
    ENV_FILE=".env"
fi

# 4. Recreate Nginx container so it mounts /var/www/certbot and loads updated nginx.conf
echo -e "${GREEN}--> Updating Nginx container with ACME webroot mount...${NC}"
$DOCKER_COMPOSE_CMD -f docker-compose.prod.yml --env-file "${ENV_FILE}" up -d nginx

# 5. Renew certificate using webroot (replaces standalone config with zero-downtime webroot)
echo -e "${GREEN}--> Requesting/renewing SSL certificate via webroot...${NC}"
if sudo certbot certonly --webroot -w "${WEBROOT}" \
    -d "${DOMAIN}" -d "${WWW_DOMAIN}" \
    --non-interactive --agree-tos --force-renewal; then
    echo -e "${GREEN}--> Webroot SSL renewal succeeded!${NC}"
else
    echo -e "${YELLOW}--> Webroot validation failed; falling back to standalone renewal...${NC}"
    docker stop "${NGINX_CONTAINER}" || true
    sudo certbot renew --standalone --force-renewal || \
        sudo certbot certonly --standalone -d "${DOMAIN}" -d "${WWW_DOMAIN}" --non-interactive --agree-tos --force-renewal
    docker start "${NGINX_CONTAINER}"
fi

# 6. Reload Nginx inside Docker to pick up the new certificate immediately
echo -e "${GREEN}--> Reloading Nginx container to apply new SSL certificate...${NC}"
docker exec "${NGINX_CONTAINER}" nginx -s reload

# 7. Verify renewal timer and print certificate status
echo -e "${GREEN}--> Verifying certificate expiration date:${NC}"
sudo certbot certificates -d "${DOMAIN}"

echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN} SSL Certificate renewed and automatic renewal configured! ${NC}"
echo -e "${GREEN}==============================================================================${NC}"

