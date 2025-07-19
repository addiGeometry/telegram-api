#!/bin/bash
set -e

echo "🧪 Running local tests (mimicking GitHub Actions)..."

# Install dependencies
echo "📦 Installing dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt

# Lint with flake8
echo "🔍 Running flake8..."
pip install flake8
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

# Test imports
echo "🔌 Testing imports..."
pip install pytest pytest-asyncio httpx
python -c "from app.main import app; print('✅ Main app import successful')"
python -c "from app.services.auth import auth_service; print('✅ Auth service import successful')"
python -c "from app.services.transcription import transcription_service; print('✅ Transcription service import successful')"
python -c "from app.storage.transcripts import transcript_storage; print('✅ Storage service import successful')"

echo "🎉 All tests passed!"