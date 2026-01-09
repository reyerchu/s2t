#!/bin/bash

# Exit on error
set -e

# Configuration
SERVICE_NAME="s2t"
DEPLOY_DIR="/var/www/defintek.io/public_html/${SERVICE_NAME}"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
START_SCRIPT="${DEPLOY_DIR}/start-${SERVICE_NAME}.sh"

# Create deployment directory if it doesn't exist
echo "Creating deployment directory..."
sudo mkdir -p ${DEPLOY_DIR}

# Build the frontend
echo "Building the frontend..."
cd frontend
npm install
npm run build
cd ..

# Copy frontend files to deployment directory
echo "Copying frontend files..."
sudo mkdir -p ${DEPLOY_DIR}/frontend
sudo cp -r frontend/* ${DEPLOY_DIR}/frontend/
sudo chown -R www-data:www-data ${DEPLOY_DIR}/frontend

# Copy backend files to deployment directory
echo "Copying backend files to deployment directory..."
sudo cp -r app ${DEPLOY_DIR}/
sudo cp -r requirements.txt ${DEPLOY_DIR}/

# Install Python dependencies
echo "Setting up Python virtual environment..."
sudo mkdir -p ${DEPLOY_DIR}/venv
sudo chown www-data:www-data ${DEPLOY_DIR}/venv
sudo -u www-data python3 -m venv ${DEPLOY_DIR}/venv
sudo -u www-data ${DEPLOY_DIR}/venv/bin/pip install --upgrade pip
sudo -u www-data ${DEPLOY_DIR}/venv/bin/pip install -r requirements.txt

# Create start script
echo "Creating start script..."
cat > start-${SERVICE_NAME}.sh << EOF
#!/bin/bash
cd /var/www/defintek.io/public_html/s2t

# Activate virtual environment for backend
source venv/bin/activate

# Start the backend server in the background
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload &

# Start the frontend server
cd frontend
npm start
EOF

# Make start script executable and copy it to deployment directory
echo "Installing start script..."
chmod +x start-${SERVICE_NAME}.sh
sudo cp start-${SERVICE_NAME}.sh ${DEPLOY_DIR}/

# Create systemd service file
echo "Creating systemd service file..."
cat > ${SERVICE_NAME}.service << EOF
[Unit]
Description=Speech to Text Service
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=${DEPLOY_DIR}
ExecStart=${START_SCRIPT}
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Copy service file to systemd directory
echo "Installing systemd service..."
sudo cp ${SERVICE_NAME}.service /etc/systemd/system/


# Reload systemd
echo "Reloading systemd..."
sudo systemctl daemon-reload

# Enable and start the service
echo "Enabling and starting the service..."
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl start ${SERVICE_NAME}

# Add Apache configuration to default-ssl.conf
#echo "Adding Apache configuration..."
#sudo cp s2t_apache.conf /etc/apache2/sites-available/

# Enable required Apache modules
echo "Enabling required Apache modules..."
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod rewrite

# Reload Apache
echo "Reloading Apache..."
sudo systemctl reload apache2

echo "Deployment completed successfully!"
echo "The s2t service is now available at https://defintek.io/s2t" 