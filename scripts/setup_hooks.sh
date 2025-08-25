#!/usr/bin/env bash

echo "🛠️ Setting up Git hooks..."

# Reset hooks path to default
git config --unset core.hooksPath 2>/dev/null || true

# Install npm dependencies
if [ -f "package.json" ]; then
    echo "📥 Installing dependencies..."
    npm install
else
    echo "📥 Installing and saving dependencies..."
    npm install --save-dev @commitlint/config-conventional @commitlint/cli
fi

echo "✅ Dependencies installed successfully."

SETUP_SUCCESS=true

# Setup pre-commit if available
if command -v pre-commit &> /dev/null; then
    echo "🔧 Setting up pre-commit..."
    pre-commit install
else
    echo "❌ pre-commit not found - skipping pre-commit setup"
    echo "Check UV environment and ensure pre-commit is installed."
    SETUP_SUCCESS=false
fi

# Copy custom hooks
for hook in commit-msg pre-push; do
    if [ -f ".githooks/$hook" ]; then
        echo "Installing $hook hook..."
        cp ".githooks/$hook" ".git/hooks/$hook"
        chmod +x ".git/hooks/$hook"
        echo "✅ $hook copied successfully."
    fi
done

if [ "$SETUP_SUCCESS" = true ]; then
    echo "✅ Git hooks setup completed!"
else
    echo "❌ Git hooks setup failed."
fi
