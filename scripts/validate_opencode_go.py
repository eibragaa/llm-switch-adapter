#!/usr/bin/env python3
"""
Quick action script to validate OpenCode Go and discover models.
Run: python3 /root/repositorio/switch-adapter/scripts/validate_opencode_go.py
"""

import os
import sys
import json
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

def get_opencode_go_key() -> str:
    """Get OpenCode Go API key from Hermes auth.json or env."""
    # Try env first
    key = os.environ.get("OPENCODE_GO_API_KEY")
    if key:
        return key
    
    # Try auth.json
    auth_path = Path.home() / ".hermes" / "auth.json"
    if auth_path.exists():
        try:
            with open(auth_path) as f:
                data = json.load(f)
            creds = data.get("credential_pool", {}).get("opencode-go", [])
            if creds and isinstance(creds, list):
                # Find the one with status "ok" or from env
                for c in creds:
                    if c.get("last_status") == "ok" or c.get("source", "").startswith("env:"):
                        return c.get("access_token", "")
                # Fallback to first
                return creds[0].get("access_token", "")
        except Exception:
            pass
    return ""

def get_opencode_go_base_url() -> str:
    """Get base URL from auth.json."""
    auth_path = Path.home() / ".hermes" / "auth.json"
    if auth_path.exists():
        try:
            with open(auth_path) as f:
                data = json.load(f)
            creds = data.get("credential_pool", {}).get("opencode-go", [])
            if creds and isinstance(creds, list):
                for c in creds:
                    if c.get("base_url"):
                        return c["base_url"].rstrip("/")
        except Exception:
            pass
    return "https://opencode.ai/zen/go/v1"  # default from auth.json

def test_opencode_go(key: str, base_url: str, model: str = "deepseek-v4-flash") -> dict:
    """Test OpenCode Go API with a simple request."""
    import urllib.request
    import urllib.error
    
    # Test 1: Try models endpoint
    try:
        req = urllib.request.Request(
            f"{base_url}/models",
            headers={"Accept": "application/json", "Authorization": f"Bearer {key}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return {"models_ok": True, "models": json.load(resp)}
    except urllib.error.HTTPError as e:
        pass
    except Exception:
        pass
    
    # Test 2: Try chat completions
    try:
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "."}],
            "max_tokens": 1
        }).encode()
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                return {"chat_ok": True, "response": json.load(resp)}
    except urllib.error.HTTPError as e:
        return {"chat_ok": False, "status": e.code, "error": e.read().decode()[:200]}
    except Exception as e:
        return {"chat_ok": False, "error": str(e)[:200]}
    
    return {"models_ok": False, "chat_ok": False, "error": "All tests failed"}

def main():
    print("=" * 60)
    print("OpenCode Go Validation")
    print("=" * 60)
    
    key = get_opencode_go_key()
    base_url = get_opencode_go_base_url()
    
    if not key:
        print("❌ No OpenCode Go key found")
        print("   Set OPENCODE_GO_API_KEY or add to ~/.hermes/auth.json")
        print("   Expected structure:")
        print('   {"credential_pool": {"opencode-go": [{"access_token": "sk-..."}]}}')
        return 1
    
    print(f"✅ Key found: {key[:12]}...{key[-4:]}")
    print(f"📍 Base URL: {base_url}")
    
    # Test
    print("\nTesting API...")
    result = test_opencode_go(key, base_url)
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if result.get("models_ok"):
        models = result.get("models", {}).get("data", [])
        print(f"\n✅ Models endpoint works! Found {len(models)} models:")
        for m in models[:10]:
            print(f"   - {m.get('id', '?')}")
        if len(models) > 10:
            print(f"   ... and {len(models) - 10} more")
    elif result.get("chat_ok"):
        print("\n✅ Chat completions works (models endpoint 404)")
        print("   Need to discover models via CLI or docs")
    else:
        print(f"\n❌ API test failed: {result}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())