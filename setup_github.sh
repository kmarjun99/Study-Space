#!/bin/bash

# GitHub Repository Setup Script
# This will help you connect your local repo to GitHub

set -e

echo "🚀 Setting up GitHub Repository for Study-Space"
echo "==============================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if git is initialized
if [ ! -d .git ]; then
    echo "Initializing git repository..."
    git init
    echo -e "${GREEN}✓ Git initialized${NC}"
else
    echo -e "${GREEN}✓ Git already initialized${NC}"
fi

# Check current remote
if git remote | grep -q origin; then
    echo ""
    echo -e "${YELLOW}⚠ Remote 'origin' already exists${NC}"
    echo "Current remote:"
    git remote -v
    echo ""
    read -p "Do you want to update it? (y/n): " update_remote
    if [ "$update_remote" = "y" ]; then
        git remote remove origin
        echo "Old remote removed"
    else
        echo "Keeping existing remote"
        exit 0
    fi
fi

# Add GitHub remote
echo ""
echo "Adding GitHub remote..."
git remote add origin https://github.com/kmarjun99/Study-Space.git
echo -e "${GREEN}✓ Remote added${NC}"

# Show remote
echo ""
echo "Current remote configuration:"
git remote -v

# Check for uncommitted changes
echo ""
if [ -n "$(git status --porcelain)" ]; then
    echo "You have uncommitted changes."
    echo ""
    read -p "Add and commit all changes? (y/n): " commit_changes
    if [ "$commit_changes" = "y" ]; then
        git add .
        echo ""
        read -p "Enter commit message (default: 'Initial commit for Render deployment'): " commit_msg
        commit_msg=${commit_msg:-"Initial commit for Render deployment"}
        git commit -m "$commit_msg"
        echo -e "${GREEN}✓ Changes committed${NC}"
    fi
fi

# Check if main branch exists
if ! git rev-parse --verify main >/dev/null 2>&1; then
    echo ""
    echo "Creating main branch..."
    git branch -M main
    echo -e "${GREEN}✓ Branch renamed/created to main${NC}"
fi

echo ""
echo "======================================"
echo "✨ Setup Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Create repository on GitHub:"
echo "   → Go to: https://github.com/new"
echo "   → Repository name: Study-Space"
echo "   → Keep it Public or Private"
echo "   → Don't initialize with README"
echo "   → Click 'Create repository'"
echo ""
echo "2. Push to GitHub:"
echo "   Run: git push -u origin main"
echo ""
echo "   If you get authentication error, use:"
echo "   → Personal Access Token (recommended)"
echo "   → Go to: https://github.com/settings/tokens"
echo "   → Generate new token (classic)"
echo "   → Select: repo (full control)"
echo "   → Use token as password when pushing"
echo ""
