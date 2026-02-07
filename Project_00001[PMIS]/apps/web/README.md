# PMIS Web UI (Next.js)

A modern, minimal Next.js UI for the PMIS (Package Management Information System). 

## Overview

The UI provides:

- **Chat Interface** (`/chat`): Natural language interactions with the PMIS agent
- **Package Management** (`/packages`, `/packages/[id]`): View packages and their details with audit timelines
- **Approvals Workflow** (`/approvals`): Review and approve/reject package change requests
- **Role-based Access Control**: Different views based on user role (admin, analyst, operator, viewer)

## Pages

### Home (`/`)
- Demo user selector (no credentials required)
- Choose from: Analyst, Operator, Admin, or Viewer role
- Links to main application pages

### Chat (`/chat`)
- Chat window to interact with the PMIS agent
- Send messages like "What is P-001?", "Mark P-001 as awarded", etc.
- View responses and resource creation confirmations
- Suggested prompts for quick testing

### Packages (`/packages`)
- Grid view of all packages
- Click any package to view details
- Shows package code, title, status, owner, and value

### Package Detail (`/packages/[id]`)
- Full package details
- Audit timeline showing all events (task created, approved, etc.)
- Click timestamps to expand event payload details
- Link to chat to propose changes

### Approvals (`/approvals`)
- List of all approval requests
- Filter by status: pending, approved, rejected
- **Admin only**: Approve or reject requests with optional reasons
- Shows proposed changes and who requested them
- Real-time status updates after decisions

## Architecture

### API Client (`lib/api.ts`)
- Centralized API client with typed methods
- Handles authentication headers (X-User-Id, X-User-Role, X-User-Name)
- No hardcoded URLs; configurable via environment variables
- Methods for all endpoints: chat, packages, approvals, audit

### User Context (`lib/useUser.tsx`)
- React Context for user state management
- Provides user info, role checking, and authentication headers
- Wraps entire app via `_app.tsx`

### Styling
- CSS Modules for component isolation
- Minimal, clean design with focus on usability
- Responsive layout (desktop and mobile)
- Color scheme: Blue/purple gradients with neutral grays

## Running the UI

### Prerequisites

Ensure the backend API is running:

```bash
cd apps/api
poetry install
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or use Docker Compose:

```bash
cd infra
docker-compose up
```

### Development

1. **Install dependencies:**
   ```bash
   cd apps/web
   npm install
   ```

2. **Start the development server:**
   ```bash
   npm run dev
   ```

   The UI will be available at `http://localhost:3000`

3. **Configure API URL (if needed):**
   
   By default, the UI connects to `http://localhost:8000`. To override:

   **Option A: Environment variable**
   ```bash
   NEXT_PUBLIC_API_URL=http://your-api-server:8000 npm run dev
   ```

   **Option B: .env.local file**
   ```
   # .env.local
   NEXT_PUBLIC_API_URL=http://your-api-server:8000
   ```

4. **Log in with a demo user** and start exploring!

### Production

1. **Build:**
   ```bash
   npm run build
   ```

2. **Start:**
   ```bash
   npm start
   ```

3. **With Docker:**
   ```bash
   docker build -f Dockerfile -t pmis-web .
   docker run -e NEXT_PUBLIC_API_URL=http://api:8000 -p 3000:3000 pmis-web
   ```

## Testing the Full Workflow

### Step 1: Log in as Analyst
1. Go to `http://localhost:3000`
2. Select "Alice (Analyst)"
3. Click "Login"

### Step 2: Create an Approval Request
1. Go to **Chat**
2. Type: "Mark P-001 as awarded"
3. The agent will create an approval request
4. You should see a confirmation with the approval ID

### Step 3: View the Approval
1. Go to **Approvals**
2. You should see the pending request from step 2
3. Note: As an analyst, you cannot approve (read-only)

### Step 4: Approve as Admin
1. Log out (click user menu > Logout)
2. Go to home and select "Charlie (Admin)"
3. Go to **Approvals**
4. Click **✓ Approve** on the pending request
5. Status should change to "approved"

### Step 5: Verify Status Change
1. Go to **Packages**
2. Click on "P-001"
3. Scroll to **Audit Timeline**
4. You should see:
   - `APPROVAL_CREATED` event from the analyst
   - `PACKAGE_PATCHED` event from the admin
   - `APPROVAL_DECIDED` event with the approve decision

## Role Permissions

| Role       | Chat | View Packages | Propose Changes | Approve/Reject |
|-----------|------|---------------|-----------------|----------------|
| **Admin**  | ✓    | ✓             | ✓               | ✓              |
| **Analyst**| ✓    | ✓             | ✓               | ✗              |
| **Operator** | ✓  | ✓             | ✓               | ✗              |
| **Viewer** | ✗    | ✓             | ✗               | ✗              |

## Troubleshooting

### "Connection refused" error
- Ensure the API server is running on `http://localhost:8000`
- Check `NEXT_PUBLIC_API_URL` environment variable
- Verify no firewall blocking connections

### "403 Insufficient permissions" in approvals
- Only admins can approve/reject
- Log in as admin user to test approval workflow
- Analysts can only propose changes

### No packages showing
- Create packages through the chat interface
- Try: "Create a new package P-TEST with title 'Test Package'"
- Check API logs for any parsing errors

### CORS errors
- API must be running on accessible endpoint
- Check that X-User-Id and X-User-Role headers are being sent correctly
- See `/lib/api.ts` for header injection logic

## Dev Commands

```bash
# Development
npm run dev

# Build for production
npm run build

# Run production build locally
npm start

# Lint code
npm run lint

# Format code
npm run format
```

## Environment Variables

| Variable              | Default                | Description                      |
|----------------------|------------------------|----------------------------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL (client-side) |

## File Structure

```
apps/web/
├── lib/
│   ├── api.ts                 # API client
│   └── useUser.tsx            # User context hook
├── components/
│   ├── Layout.tsx             # Main layout wrapper
│   └── Layout.module.css       # Layout styles
├── pages/
│   ├── _app.tsx               # App wrapper with UserProvider
│   ├── index.tsx              # Home/login page
│   ├── chat.tsx               # Chat interface
│   ├── approvals.tsx          # Approvals inbox
│   └── packages/
│       ├── index.tsx          # Package list
│       └── [id].tsx           # Package detail
├── styles/
│   ├── globals.css            # Global styles
│   ├── Home.module.css
│   ├── Chat.module.css
│   ├── Packages.module.css
│   ├── PackageDetail.module.css
│   └── Approvals.module.css
├── package.json
├── tsconfig.json
└── next.config.js
```

## Notes

- **No authentication secrets** are stored in the frontend; all auth is header-based
- API headers are stripped before being sent to the browser (never logged)
- Demo users are for testing only; in production, integrate with a real auth system
- All API errors are caught and displayed to the user
- Loading states prevent double submissions

## Next Steps

For a production deployment:

1. Integrate with a real authentication provider (OAuth, OIDC, etc.)
2. Store API base URL in a secure configuration
3. Add error tracking and analytics
4. Enhance accessibility (ARIA labels, keyboard navigation)
5. Add unit and integration tests
6. Set up CI/CD pipeline for automated deployments
7. Implement proper session management and token refresh
