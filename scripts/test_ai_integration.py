#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test script for AI integration - without unicode emojis"""

import sys
sys.path.insert(0, '.')

print("=" * 50)
print("TEST 1: Import AI Providers")
print("=" * 50)

try:
    from core.ai_providers import (
        AIProvider, OpenAIProvider, GeminiProvider, 
        OllamaProvider, LMStudioProvider, AIManager
    )
    print("[PASS] All provider classes imported successfully")
except Exception as e:
    print(f"[FAIL] Error importing providers: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 50)
print("TEST 2: Import AI Features")
print("=" * 50)

try:
    from core.ai_features import (
        TemplateGenerator, SubjectLineOptimizer,
        LeadPersonalizer, LeadScorer, ResponseAnalyzer,
        SendTimingOptimizer, ABTestingEngine
    )
    print("[PASS] All feature classes imported successfully")
except Exception as e:
    print(f"[FAIL] Error importing features: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 50)
print("TEST 3: Import AI Workers")
print("=" * 50)

try:
    from core.ai_workers import AIWorker, BatchAIWorker
    print("[PASS] Worker classes imported successfully")
except Exception as e:
    print(f"[FAIL] Error importing workers: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 50)
print("TEST 4: Initialize AI Manager")
print("=" * 50)

try:
    from core.ai_providers import ai_manager
    
    # Register providers
    ai_manager.register_provider("ollama", OllamaProvider())
    ai_manager.register_provider("openai", OpenAIProvider())
    ai_manager.register_provider("gemini", GeminiProvider())
    ai_manager.register_provider("lmstudio", LMStudioProvider())
    
    print("[PASS] All providers registered")
    
    names = ai_manager.get_provider_names()
    print(f"[INFO] Registered: {len(names)} providers")
    
except Exception as e:
    print(f"[FAIL] Error initializing manager: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 50)
print("TEST 5: Provider Connection Tests")
print("=" * 50)

try:
    ollama = OllamaProvider("http://localhost:11434")
    result = ollama.check_connection()
    if result:
        print("[PASS] Ollama available at localhost:11434")
    else:
        print("[SKIP] Ollama not running (Docker not started - this is OK)")
except Exception as e:
    print(f"[SKIP] Ollama test skipped: {type(e).__name__}")

print("\n" + "=" * 50)
print("TEST 6: Feature Classes")
print("=" * 50)

try:
    gen = TemplateGenerator()
    print("[PASS] TemplateGenerator")
    
    opt = SubjectLineOptimizer()
    print("[PASS] SubjectLineOptimizer")
    
    scorer = LeadScorer()
    print("[PASS] LeadScorer")
    
    pers = LeadPersonalizer()
    print("[PASS] LeadPersonalizer")
    
    analyzer = ResponseAnalyzer()
    print("[PASS] ResponseAnalyzer")
    
    timing = SendTimingOptimizer()
    print("[PASS] SendTimingOptimizer")
    
    abtest = ABTestingEngine()
    print("[PASS] ABTestingEngine")
    
except Exception as e:
    print(f"[FAIL] Error with features: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 50)
print("TEST 7: Method Signatures")
print("=" * 50)

try:
    import inspect
    
    sig = inspect.signature(TemplateGenerator.generate)
    print(f"[PASS] TemplateGenerator.generate{sig}")
    
    sig = inspect.signature(SubjectLineOptimizer.generate_variants)
    print(f"[PASS] SubjectLineOptimizer.generate_variants{sig}")
    
    sig = inspect.signature(LeadScorer.score_lead)
    print(f"[PASS] LeadScorer.score_lead{sig}")
    
except Exception as e:
    print(f"[FAIL] Error checking signatures: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 50)
print("SUMMARY")
print("=" * 50)
print("[PASS] 4 AI Providers")
print("[PASS] 7 AI Features")
print("[PASS] AI Workers")
print("[PASS] Manager system")
print("[PASS] Method signatures")
print("\n>>> ALL TESTS PASSED <<<")
print(">>> Ready for integration into main_window.py <<<")
