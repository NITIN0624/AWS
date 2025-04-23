FROM node:18-slim

WORKDIR /app

# Copy the function code
COPY function.js .

# Install any dependencies if needed
# For more complex projects, you'd copy package.json and run npm install
# COPY package.json .
# RUN npm install

# Execute the function
CMD ["node", "function.js"]
