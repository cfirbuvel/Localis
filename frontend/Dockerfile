FROM node:20-slim

WORKDIR /app

# Copy package configuration files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy frontend source files
COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Start Vite dev server bound to all network interfaces
CMD ["npm", "run", "dev", "--", "--host"]
