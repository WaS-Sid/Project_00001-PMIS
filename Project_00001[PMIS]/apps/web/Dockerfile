# Multi-stage build for Next.js Web
# Build stage
FROM node:18-alpine as builder
WORKDIR /app

# Copy package files from apps/web
COPY apps/web/package.json apps/web/package-lock.json* apps/web/yarn.lock* apps/web/pnpm-lock.yaml* ./

# Install dependencies with peer deps flexibility
RUN npm install --legacy-peer-deps --force

# Copy source code from apps/web
COPY apps/web/ .

# Build Next.js app
RUN npm run build || yarn build || pnpm build

# Production stage
FROM node:18-alpine
WORKDIR /app

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init

# Copy built application and dependencies from builder
COPY --from=builder /app/package.json /app/package-lock.json* /app/yarn.lock* /app/pnpm-lock.yaml* ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.* ./

# Create non-root user
RUN addgroup -g 1000 nodejs && \
    adduser -S nextjs -u 1000 && \
    chown -R nextjs:nodejs /app
USER nextjs

EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/', (r) => { if (r.statusCode !== 200) throw new Error(r.statusCode) })"

# Use dumb-init to handle signals properly
ENTRYPOINT ["dumb-init", "--"]
CMD ["npm", "start"]
