# GitHub Actions Setup Guide for LoreVia

This guide will help you set up GitHub Actions CI/CD pipeline for your LoreVia project.

## 🚀 Quick Setup (Just Push!)

For the basic setup, you only need to:

1. **Push your code to GitHub**
   ```bash
   git add .
   git commit -m "Add screenplay support and CI/CD pipeline"
   git push origin main
   ```

2. **Add required secrets to your GitHub repository** (see below)

The workflows I've created will automatically run when you push to `main` or `develop` branches.

## 🔧 Required GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions → Repository secrets and add these:

### Database Secrets
```
STAGING_DATABASE_URL=postgresql://user:password@host:5432/lorevia_staging
PRODUCTION_DATABASE_URL=postgresql://user:password@host:5432/lorevia_production
```

### Docker Hub (for container deployment)
```
DOCKER_USERNAME=your_dockerhub_username
DOCKER_PASSWORD=your_dockerhub_access_token
```

### Slack Notifications (optional)
```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
```

### Staging/Production URLs (for integration tests)
```
STAGING_URL=https://staging.lorevia.com
STAGING_API_TOKEN=your_staging_api_token
```

## 📋 Workflow Overview

### 1. Main CI/CD Pipeline (`ci-cd.yml`)
**Triggers**: Push to `main`/`develop`, Pull Requests

**Jobs**:
- **backend-tests**: Python tests, linting, type checking
- **frontend-tests**: Node.js tests, linting, type checking
- **security-scan**: Trivy vulnerability scanning
- **build-and-push-docker**: Container builds (main branch only)
- **deploy-staging**: Deploy to staging (develop branch only)
- **deploy-production**: Deploy to production (main branch only)
- **integration-tests**: Post-deployment testing
- **notify-slack**: Slack notifications

### 2. Database Migrations (`database-migrations.yml`)
**Triggers**: Changes to migration files or models

**Jobs**:
- **test-migrations**: Test migration up/down on fresh database
- **auto-migrate-staging**: Auto-apply migrations to staging
- **migrate-production**: Safe production migrations with backup

### 3. Dependency Updates (`dependency-update.yml`)
**Triggers**: Weekly schedule (Mondays 2 AM UTC) or manual

**Jobs**:
- **update-python-dependencies**: Update pip requirements
- **update-node-dependencies**: Update npm packages
- **security-audit**: Vulnerability scanning
- **auto-pr**: Create pull requests for updates

## 🗄️ Supabase Database Setup

### 1. Get Your Supabase Connection String
From your Supabase project:
1. Go to Settings → Database
2. Find the "Connection string" under "Connection parameters"
3. Use the "URI" format: `postgresql://[user]:[password]@[host]:[port]/[database]`

### 2. Update Environment Variables
Add your Supabase connection string to GitHub secrets and your local `.env`:

```bash
# Local development
DATABASE_URL=postgresql://postgres:your_password@db.your-project.supabase.co:5432/postgres

# GitHub secrets
STAGING_DATABASE_URL=postgresql://postgres:your_password@db.your-project.supabase.co:5432/postgres
PRODUCTION_DATABASE_URL=postgresql://postgres:your_password@db.your-project.supabase.co:5432/postgres
```

### 3. Run Initial Migration
The screenplay support migration has been created. To apply it:

**Locally:**
```bash
cd backend
alembic upgrade head
```

**Via GitHub Actions:**
The migration will automatically run when you push to `develop` (staging) or `main` (production).

## 🔄 Migration Workflow

### Development
1. Make model changes
2. Generate migration: `alembic revision --autogenerate -m "Description"`
3. Push to `develop` branch
4. GitHub Actions tests and applies migrations to staging

### Production
1. Merge to `main` branch
2. GitHub Actions:
   - Creates database backup
   - Applies migrations
   - Verifies success
   - Deploys new code
   - Runs integration tests

### Manual Migration (if needed)
```bash
# Check current version
alembic current

# Upgrade to latest
alembic upgrade head

# Upgrade to specific version
alembic upgrade 20240424_screenplay_support

# Downgrade (careful!)
alembic downgrade -1
```

## 🐛 Troubleshooting

### Migration Issues
```bash
# Check migration history
alembic history

# Check current revision
alembic current

# Force upgrade (if stuck)
alembic stamp head
```

### GitHub Actions Failures
1. Check the "Actions" tab in your GitHub repo
2. Look at the specific job that failed
3. Common issues:
   - Missing secrets (add them in repo settings)
   - Database connection issues (check DATABASE_URL)
   - Dependency conflicts (check requirements.txt)

### Database Connection Issues
```bash
# Test connection locally
python -c "
from app.core.config import settings
print(f'Database URL: {settings.DATABASE_URL}')
"

# Test with psql
psql "postgresql://user:password@host:5432/database"
```

## 📊 Monitoring

### GitHub Actions Dashboard
- Go to your repository → Actions tab
- See workflow runs, success/failure rates
- Download artifacts (test reports, security scans)

### Database Migration Status
```bash
# Check applied migrations
alembic current

# View all migrations
alembic history

# Check database schema
psql $DATABASE_URL -c "\dt"
```

## 🎯 Best Practices

1. **Branch Strategy**: Use `develop` for staging, `main` for production
2. **Migration Safety**: Always test migrations on staging first
3. **Secrets Management**: Never commit secrets to the repository
4. **Monitoring**: Check Actions tab regularly for failures
5. **Rollback Plan**: Keep previous migrations for easy rollback

## 🚀 Next Steps

1. **Add GitHub Secrets** (required for deployment)
2. **Push to develop branch** to test staging deployment
3. **Test screenplay upload** feature in staging
4. **Merge to main** for production deployment

That's it! Your CI/CD pipeline is ready to go. The workflows will automatically handle testing, building, deploying, and monitoring your LoreVia application.
